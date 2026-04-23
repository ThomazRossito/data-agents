---
name: databricks-iceberg
updated_at: "2026-04-23"
source: web_search
---

# Apache Iceberg on Databricks

Databricks provides multiple ways to work with Apache Iceberg: native managed Iceberg tables, UniForm for Delta-to-Iceberg interoperability, and the Iceberg REST Catalog (IRC) for external engine access.

---

## Critical Rules (always follow)

- **MUST** use Unity Catalog — all Iceberg features require UC-enabled workspaces
- **MUST NOT** install an Iceberg library into Databricks Runtime (DBR includes built-in Iceberg support; adding a library causes version conflicts)
- **MUST NOT** set `write.metadata.path` or `write.metadata.previous-versions-max` — Databricks manages metadata locations automatically; overriding causes corruption
- **MUST** determine which Iceberg pattern fits the use case before writing code — see the [When to Use](#when-to-use) section below
- **MUST** know that both `PARTITIONED BY` and `CLUSTER BY` produce the same Iceberg metadata for external engines — UC maintains an Iceberg partition spec with partition fields corresponding to the clustering keys, so external engines reading via IRC see a partitioned Iceberg table (not Hive-style, but proper Iceberg partition fields) and can prune on those fields; internally UC uses those fields as liquid clustering keys; the only differences between the two syntaxes are: (1) `PARTITIONED BY` is standard Iceberg DDL (any engine can create the table), while `CLUSTER BY` is DBR-only DDL; (2) `PARTITIONED BY` **auto-handles** DV/row-tracking properties, while `CLUSTER BY` requires manual TBLPROPERTIES on v2
- **MUST NOT** use expression-based partition transforms (`bucket()`, `years()`, `months()`, `days()`, `hours()`) with `PARTITIONED BY` on managed Iceberg tables — only plain column references are supported; expression transforms cause errors
- **MUST** disable deletion vectors and row tracking when using `CLUSTER BY` on Iceberg v2 tables — set `'delta.enableDeletionVectors' = false` and `'delta.enableRowTracking' = false` in TBLPROPERTIES (Iceberg v3 handles this automatically; `PARTITIONED BY` handles this automatically on both v2 and v3)

---

## Key Concepts

| Concept | Summary |
|---------|---------|
| **Managed Iceberg Table** | Native Iceberg table created with `USING ICEBERG` — full read/write in Databricks and via external Iceberg engines; Public Preview, DBR 16.4 LTS+ |
| **External Iceberg Reads (UniForm)** | Delta table that auto-generates Iceberg metadata — read as Iceberg externally, write as Delta internally; requires DBR 14.3 LTS+ |
| **Compatibility Mode** | UniForm variant for streaming tables and materialized views in SDP pipelines |
| **Iceberg REST Catalog (IRC)** | Unity Catalog's built-in REST endpoint implementing the Iceberg REST Catalog spec — lets external engines (Spark, PyIceberg, Snowflake) access UC-managed Iceberg data; Public Preview, DBR 16.4 LTS+ |
| **Iceberg v3** | Next-gen format (**Public Preview, DBR 18.0+**) — deletion vectors, VARIANT type, row lineage |
| **Foreign Iceberg Table** | Iceberg table managed by an external catalog (e.g. AWS Glue, Snowflake Horizon) — read-only in Databricks via Lakehouse Federation; Public Preview, DBR 16.4 LTS+ |

> ⚠️ **Atualização de versão em abril 2026:** Iceberg v3 **não é mais Beta** — passou a **Public Preview no DBR 18.0+** (atualizado em docs.databricks.com em 21/04/2026). O requisito mínimo anterior de DBR 17.3+ está desatualizado. Use `'format-version' = '3'` apenas em clusters com DBR 18.0+.

> ⚠️ **Atualização de versão de cliente em abril 2026:** Databricks recomenda oficialmente clientes Iceberg **1.9.2+** (antes citava-se 1.9.0+) para leitura e escrita via IRC.

---

## Quick Start

### Create a Managed Iceberg Table

```sql
-- No clustering
CREATE TABLE my_catalog.my_schema.events
USING ICEBERG
AS SELECT * FROM raw_events;

-- PARTITIONED BY (recommended for cross-platform): standard Iceberg syntax, works on EMR/OSS Spark/Trino/Flink
-- auto-disables DVs and row tracking — no TBLPROPERTIES needed on v2 or v3
CREATE TABLE my_catalog.my_schema.events
USING ICEBERG
PARTITIONED BY (event_date)
AS SELECT * FROM raw_events;

-- CLUSTER BY on Iceberg v2 (DBR-only syntax): must manually disable DVs and row tracking
CREATE TABLE my_catalog.my_schema.events
USING ICEBERG
TBLPROPERTIES (
  'delta.enableDeletionVectors' = false,
  'delta.enableRowTracking' = false
)
CLUSTER BY (event_date)
AS SELECT * FROM raw_events;

-- CLUSTER BY on Iceberg v3 (DBR-only syntax, requer DBR 18.0+ — Public Preview): no TBLPROPERTIES needed
CREATE TABLE my_catalog.my_schema.events
USING ICEBERG
TBLPROPERTIES ('format-version' = '3')
CLUSTER BY (event_date)
AS SELECT * FROM raw_events;

-- Iceberg v3 com Deletion Vectors habilitados explicitamente (requer DBR 18.0+)
CREATE TABLE catalog.schema.table (c1 INT)
USING ICEBERG
TBLPROPERTIES (
  'iceberg.enableDeletionVectors' = 'true'
);
```

### Enable UniForm on an Existing Delta Table

```sql
ALTER TABLE my_catalog.my_schema.customers
SET TBLPROPERTIES (
  'delta.columnMapping.mode' = 'name',
  'delta.enableIcebergCompatV2' = 'true',
  'delta.universalFormat.enabledFormats' = 'iceberg'
);
```

### Enable UniForm + Iceberg v3 (Delta table) — DBR 18.0+

```sql
-- Nova tabela Delta com UniForm e v3 habilitados
CREATE TABLE catalog.schema.table (c1 INT)
TBLPROPERTIES(
  'delta.enableDeletionVectors'            = 'true',
  'delta.enableIcebergCompatV3'            = 'true',
  'delta.universalFormat.enabledFormats'   = 'iceberg'
);

-- Upgrade de tabela Delta existente para IcebergCompatV3
ALTER TABLE catalog.schema.table
SET TBLPROPERTIES(
  'delta.enableIcebergCompatV3' = 'true',
  'delta.enableIcebergCompatV2' = 'false'
);
```

---

## Read/Write Capability Matrix

| Table Type | Databricks Read | Databricks Write | External IRC Read | External IRC Write |
|------------|:-:|:-:|:-:|:-:|
| Managed Iceberg (`USING ICEBERG`) | Yes | Yes | Yes | Yes |
| Delta + UniForm | Yes (as Delta) | Yes (as Delta) | Yes (as Iceberg) | No |
| Delta + Compatibility Mode | Yes (as Delta) | Yes | Yes (as Iceberg) | No |
| Foreign Iceberg Table | Yes (read-only) | No | Yes (via IRC, sem auto-refresh) | No |

---

## Reference Files

| File | Summary | Keywords |
|------|---------|----------|
| [1-managed-iceberg-tables.md](1-managed-iceberg-tables.md) | Creating and managing native Iceberg tables — DDL, DML, Liquid Clustering, Predictive Optimization, Iceberg v3, limitations | CREATE TABLE USING ICEBERG, CTAS, MERGE, time travel, deletion vectors, VARIANT |
| [2-uniform-and-compatibility.md](2-uniform-and-compatibility.md) | Making Delta tables readable as Iceberg — UniForm for regular tables, Compatibility Mode for streaming tables and MVs | UniForm, universalFormat, Compatibility Mode, streaming tables, materialized views, SDP |
| [3-iceberg-rest-catalog.md](3-iceberg-rest-catalog.md) | Exposing Databricks tables to external engines via the IRC endpoint — auth, credential vending, IP access lists | IRC, REST Catalog, credential vending, EXTERNAL USE SCHEMA, PAT, OAuth |
| [4-snowflake-interop.md](4-snowflake-interop.md) | Bidirectional Snowflake-Databricks integration — catalog integration, foreign catalogs, vended credentials | Snowflake, catalog integration, external volume, vended credentials, REFRESH_INTERVAL_SECONDS |
| [5-external-engine-interop.md](5-external-engine-interop.md) | Connecting PyIceberg, OSS Spark, AWS EMR, Apache Flink, and Kafka Connect via IRC | PyIceberg, OSS Spark, EMR, Flink, Kafka Connect, pyiceberg.yaml |

---

## When to Use

- **Creating a new Iceberg table** → [1-managed-iceberg-tables.md](1-managed-iceberg-tables.md)
- **Making an existing Delta table readable as Iceberg** → [2-uniform-and-compatibility.md](2-uniform-and-compatibility.md)
- **Making a streaming table or MV readable as Iceberg** → [2-uniform-and-compatibility.md](2-uniform-and-compatibility.md) (Compatibility Mode section)
- **Choosing between Managed Iceberg vs UniForm vs Compatibility Mode** → decision table in [2-uniform-and-compatibility.md](2-uniform-and-compatibility.md)
- **Exposing Databricks tables to external engines via REST API** → [3-iceberg-rest-catalog.md](3-iceberg-rest-catalog.md)
- **Integrating Databricks com Snowflake (any direction, including Azure storage)** → [4-snowflake-interop.md](4-snowflake-interop.md)
- **Connecting PyIceberg, OSS Spark, Flink, EMR, or Kafka** → [5-external-engine-interop.md](5-external-engine-interop.md)
- **Sharing foreign Iceberg tables externally** → use Delta Sharing (Public Preview, abril 2026) — providers add foreign Iceberg tables to a share; recipients access data in read-only format

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **No Change Data Feed (CDF)** | CDF is not supported on managed Iceberg tables. Use Delta + UniForm if you need CDF. |
| **UniForm async delay** | Iceberg metadata generation is asynchronous. After a write, there may be a brief delay before external engines see the latest data. Check status with `DESCRIBE EXTENDED table_name`. |
| **Compression codec change** | Managed Iceberg tables and tables with Iceberg reads enabled use `zstd` compression by default (not `snappy`). Older Iceberg readers that don't support zstd will fail. Verify reader compatibility or set `write.parquet.compression-codec` to `snappy`. |
| **Snowflake 1000-commit limit** | Snowflake processes at most 1000 Delta commit files per refresh cycle. High-frequency writers must compact metadata. Multiple refreshes can be chained — each continues from where the previous stopped. |
| **Deletion vectors with UniForm** | UniForm requires deletion vectors to be disabled (`delta.enableDeletionVectors = false`). If your table has deletion vectors enabled, run `REORG TABLE ... APPLY (PURGE)` before enabling UniForm. For Iceberg v3 + UniForm, use `delta.enableIcebergCompatV3 = 'true'` (DVs são suportados nesse caso). |
| **No shallow clone for Iceberg** | `SHALLOW CLONE` is not supported for Iceberg tables. Use `DEEP CLONE` or `CREATE TABLE ... AS SELECT` instead. |
| **Version mismatch with external engines** | Ensure external engines use an Iceberg library version compatible with the format version of your tables. Iceberg v3 tables require Iceberg library **1.9.2+** (recomendação oficial atualizada em abril 2026). |
| **No Structured Streaming sink** | Cannot use `writeStream` directly to write to Iceberg tables. Use `INSERT INTO` or `MERGE` in batch, or SDP streaming tables with Compatibility Mode for external reads. |
| **IP access list blocking IRC connections** | If workspace has IP access lists enabled, add the client egress CIDR to the allowlist. Symptoms: connection timeout or `403 Forbidden` even with valid credentials. |
| **Foreign Iceberg tables not auto-refreshed via IRC** | When reading foreign Iceberg tables through the Iceberg REST Catalog API, metadata is **not** automatically refreshed. Run `REFRESH FOREIGN TABLE` manually before querying to get the latest snapshot. |
| **Managed Iceberg table creation fails** | Managed Iceberg tables can only be created if **Predictive Optimization is enabled** for table maintenance at the catalog or schema level. |
| **Iceberg v2 row-level deletes fail** | Iceberg v2 position deletes and equality-based deletes are **not supported** on Databricks. Use Iceberg v3 with deletion vectors (`'iceberg.enableDeletionVectors' = 'true'`) for row-level deletions. |
| **Snowflake write to UC on Azure** | Snowflake write support para tabelas Iceberg gerenciadas por Unity Catalog no Azure é GA desde 06/04/2026 (suporte a Azure Data Lake Storage Gen2 com external volumes). |

---

## Related Skills

- **[databricks-unity-catalog](../databricks-unity-catalog/SKILL.md)** — catalog/schema management, governance, system tables
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** — SDP pipelines (streaming tables, materialized views with Compatibility Mode)
- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** — Python SDK and REST API for Databricks operations
- **[databricks-dbsql](../databricks-dbsql/SKILL.md)** — SQL warehouse features, query patterns

---

## Resources

- **[Iceberg Overview](https://docs.databricks.com/aws/en/iceberg/)** — main hub for Iceberg on Databricks (atualizado 21/04/2026)
- **[UniForm / External Iceberg Reads](https://docs.databricks.com/aws/en/delta/uniform.html)** — Delta Universal Format (previously called UniForm)
- **[Iceberg REST Catalog](https://docs.databricks.com/aws/en/external-access/iceberg)** — IRC endpoint and external engine access
- **[Compatibility Mode](https://docs.databricks.com/aws/en/external-access/compatibility-mode)** — UniForm for streaming tables and MVs
- **[Iceberg v3](https://docs.databricks.com/aws/en/iceberg/iceberg-v3)** — next-gen format features (Public Preview, DBR 18.0+)
- **[Foreign Tables](https://docs.databricks.com/aws/en/query-data/foreign-tables.html)** — reading external catalog data
- **[Managed Tables (Delta + Iceberg)](https://docs.databricks.com/aws/en/tables/managed)** — UC managed table concepts and DDL
