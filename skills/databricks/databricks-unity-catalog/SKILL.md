---
name: databricks-unity-catalog
description: "Unity Catalog system tables and volumes. Use when querying system tables (audit, lineage, billing) or working with volume file operations (upload, download, list files in /Volumes/)."
updated_at: 2026-04-23
source: web_search
---

# Unity Catalog

Guidance for Unity Catalog system tables, volumes, and governance.

> ⚠️ **Breaking change (2025):** Delta Live Tables (DLT) foi renomeado para **Lakeflow Spark Declarative Pipelines (SDP)**. Databricks Jobs agora é **Lakeflow Jobs**. Nenhuma migração de código é necessária — código DLT existente continua funcionando. Referências a `import dlt` ainda funcionam, mas a nomenclatura canônica nas docs oficiais mudou. Atualize links e comentários em pipelines.

> ⚠️ **Breaking change (dez/2025):** Contas Databricks criadas após **18 de dezembro de 2025** não têm acesso a DBFS root, mounts, Hive Metastore ou No-isolation shared compute. Essas contas usam exclusivamente Unity Catalog para governança.

> ℹ️ **Schema evolution em system tables:** Novas colunas podem ser adicionadas a qualquer momento sem aviso prévio. Queries que dependem de schema fixo podem quebrar. Se você escreve dados de system tables para outra tabela-destino, habilite schema evolution.

## When to Use This Skill

Use this skill when:
- Working with **volumes** (upload, download, list files in `/Volumes/`)
- Querying **lineage** (table dependencies, column-level lineage)
- Analyzing **audit logs** (who accessed what, permission changes)
- Monitoring **billing and usage** (DBU consumption, cost analysis)
- Tracking **compute resources** (cluster usage, warehouse metrics)
- Reviewing **job execution** (run history, success rates, failures)
- Analyzing **query performance** (slow queries, warehouse utilization)
- Profiling **data quality** (data profiling, drift detection, metric tables)
- Classifying **sensitive data** (PII detection, column-level data classification)
- Monitoring **workspaces** (workspace state, lifecycle, cross-workspace aggregation)

## Reference Files

| Topic | File | Description |
|-------|------|-------------|
| System Tables | [5-system-tables.md](5-system-tables.md) | Lineage, audit, billing, compute, jobs, query history |
| Volumes | [6-volumes.md](6-volumes.md) | Volume file operations, permissions, best practices |
| Data Profiling | [7-data-profiling.md](7-data-profiling.md) | Data profiling, drift detection, profile metrics |

## Quick Start

### Volume File Operations (MCP Tools)

| Tool | Usage |
|------|-------|
| `list_volume_files` | `list_volume_files(volume_path="/Volumes/catalog/schema/volume/path/")` |
| `get_volume_folder_details` | `get_volume_folder_details(volume_path="catalog/schema/volume/path", format="parquet")` - schema, row counts, stats |
| `upload_to_volume` | `upload_to_volume(local_path="/tmp/data/*", volume_path="/Volumes/.../dest")` |
| `download_from_volume` | `download_from_volume(volume_path="/Volumes/.../file.csv", local_path="/tmp/file.csv")` |
| `create_volume_directory` | `create_volume_directory(volume_path="/Volumes/.../new_folder")` |

> ℹ️ **Volumes SDK (2025):** O limite de 5 GB por arquivo para upload/download via Python SDK foi removido. O único limite agora é o do cloud provider (S3, ADLS, GCS). O limite de 5 GB ainda se aplica via UI do Catalog Explorer.

> ℹ️ **Runtime mínimo:** Volumes requerem **Databricks Runtime 13.3 LTS ou superior**. Em runtimes anteriores (≤12.2 LTS), operações em `/Volumes/` podem "funcionar" mas escrevem apenas em storage efêmero do cluster, sem persistência no UC.

### Enable System Tables Access

```sql
-- Grant access to system tables (metastore must be on Privilege Model v1.0)
GRANT USE CATALOG ON CATALOG system TO `data_engineers`;
GRANT USE SCHEMA ON SCHEMA system.access TO `data_engineers`;
GRANT SELECT ON SCHEMA system.access TO `data_engineers`;

-- Para novos schemas (billing, compute, lakeflow):
GRANT USE SCHEMA ON SCHEMA system.billing TO `data_engineers`;
GRANT SELECT ON SCHEMA system.billing TO `data_engineers`;
GRANT USE SCHEMA ON SCHEMA system.compute TO `data_engineers`;
GRANT SELECT ON SCHEMA system.compute TO `data_engineers`;
```

### Common Queries

```sql
-- Table lineage: What tables feed into this table?
SELECT source_table_full_name, source_column_name
FROM system.access.table_lineage
WHERE target_table_full_name = 'catalog.schema.table'
  AND event_date >= current_date() - 7;

-- Column lineage: rastrear origem de uma coluna específica
SELECT source_table_full_name, source_column_name, target_table_full_name, target_column_name
FROM system.access.column_lineage
WHERE target_table_full_name = 'catalog.schema.table'
  AND event_date >= current_date() - 7;

-- Audit: Recent permission changes
SELECT event_time, user_identity.email, action_name, request_params
FROM system.access.audit
WHERE action_name LIKE '%GRANT%' OR action_name LIKE '%REVOKE%'
ORDER BY event_time DESC
LIMIT 100;

-- Billing: DBU usage by workspace
SELECT workspace_id, sku_name, SUM(usage_quantity) AS total_dbus
FROM system.billing.usage
WHERE usage_date >= current_date() - 30
GROUP BY workspace_id, sku_name;

-- Workspaces: Estado atual de todos os workspaces ativos (novo em 2025)
SELECT workspace_id, workspace_name, workspace_status, cloud, region
FROM system.access.workspaces_latest
WHERE workspace_status = 'RUNNING';

-- Data Classification: Tabelas com colunas de dados sensíveis (novo em 2025)
SELECT catalog_name, schema_name, table_name, column_name, class_tag, confidence
FROM system.data_classification.results
WHERE confidence = 'HIGH'
ORDER BY catalog_name, schema_name, table_name;

-- Compute: Clusters com maior utilização de CPU
SELECT cluster_id, MAX(cpu_user_percent) AS peak_cpu
FROM system.compute.node_timeline
WHERE timestamp >= current_timestamp() - INTERVAL 7 DAYS
GROUP BY cluster_id
ORDER BY peak_cpu DESC
LIMIT 20;

-- Jobs (system.compute schema, não system.lakeflow):
SELECT job_id, run_id, result_state, start_time, end_time
FROM system.compute.job_run_timeline
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
  AND result_state = 'FAILED'
ORDER BY start_time DESC;

-- Pipelines (Lakeflow Spark Declarative Pipelines, ex-DLT):
SELECT pipeline_id, update_id, state, full_refresh, start_time
FROM system.compute.pipeline_update_timeline
WHERE start_time >= current_timestamp() - INTERVAL 7 DAYS
ORDER BY start_time DESC;

-- Streaming para system tables: use skipChangeCommits para evitar falhas
-- spark.readStream.option("skipChangeCommits", "true").table("system.billing.usage")
```

## System Tables — Mapa Completo

> ℹ️ Tabelas em **Public Preview** são gratuitas durante o preview, mas podem gerar cobrança no futuro. As tabelas `system.billing.usage` e `system.billing.list_prices` são sempre gratuitas.

| Schema | Tabela | Status | Descrição |
|--------|--------|--------|-----------|
| `system.access` | `audit` | GA | Logs de auditoria (quem fez o quê) |
| `system.access` | `table_lineage` | GA | Linhagem de tabelas |
| `system.access` | `column_lineage` | GA | Linhagem de colunas |
| `system.access` | `outbound_network` | GA | Tráfego de rede de saída |
| `system.access` | `workspaces_latest` | Public Preview | Estado atual de workspaces na conta |
| `system.billing` | `usage` | GA | Uso de DBUs por workspace/SKU |
| `system.billing` | `list_prices` | GA | Preços de lista de SKUs |
| `system.compute` | `clusters` | GA | Configurações de clusters (SCD) |
| `system.compute` | `node_types` | GA | Tipos de nós disponíveis |
| `system.compute` | `node_timeline` | GA | Utilização de recursos por minuto |
| `system.compute` | `warehouse_events` | GA | Eventos de SQL Warehouses |
| `system.compute` | `warehouses` | GA | Configurações de warehouses |
| `system.compute` | `jobs` | GA | Configurações de jobs (Lakeflow Jobs) |
| `system.compute` | `job_run_timeline` | GA | Histórico de execuções de jobs |
| `system.compute` | `job_task_run_timeline` | GA | Histórico de tasks de jobs |
| `system.compute` | `job_tasks` | GA | Configuração de tasks de jobs |
| `system.compute` | `pipelines` | GA | Configurações de pipelines (Lakeflow SDP) |
| `system.compute` | `pipeline_update_timeline` | GA | Histórico de updates de pipelines |
| `system.query` | `history` | GA | Histórico de queries SQL |
| `system.data_classification` | `results` | Public Preview | Detecção automática de dados sensíveis por coluna |
| `system.marketplace` | `listing_access_events` | GA | Acessos a listings do Marketplace |
| `system.marketplace` | `listing_funnel_events` | GA | Impressões e ações em listings |
| `system.information_schema` | *(múltiplas)* | GA | Metadados do catálogo (funciona diferente de system tables) |

> ⚠️ `system.compute.clusters` e `system.compute.node_timeline` **não contêm registros de serverless compute nem SQL Warehouses** — use `system.compute.warehouse_events` e `system.billing.usage` para esses casos.

## MCP Tool Integration

Use `mcp__databricks__execute_sql` for system table queries:

```python
# Query lineage
mcp__databricks__execute_sql(
    sql_query="""
        SELECT source_table_full_name, target_table_full_name
        FROM system.access.table_lineage
        WHERE event_date >= current_date() - 7
    """,
    catalog="system"
)

# Query data classification (novo)
mcp__databricks__execute_sql(
    sql_query="""
        SELECT catalog_name, schema_name, table_name, column_name, class_tag, confidence
        FROM system.data_classification.results
        WHERE confidence = 'HIGH'
        LIMIT 100
    """,
    catalog="system"
)
```

## Best Practices

1. **Filter by date** - System tables can be large; always use date filters
2. **Use appropriate retention** - Check your workspace's retention settings; each system table has its own free retention period (see docs for details per table)
3. **Grant minimal access** - System tables contain sensitive metadata
4. **Schedule reports** - Create scheduled queries for regular monitoring
5. **Enable schema evolution** - Se escrever dados de system tables para outra tabela, use `mergeSchema` ou `autoMerge` — novas colunas são adicionadas sem aviso
6. **Streaming com system tables** - Sempre use `.option("skipChangeCommits", "true")` para evitar falhas causadas por deletes internos
7. **Volumes: use managed por padrão** - Managed volumes são a escolha padrão; use external volumes apenas quando os dados já existem em storage externo ou são escritos por sistemas de terceiros
8. **Volumes: evite DBFS** - Use `/Volumes/` para qualquer dado não-tabular novo; DBFS root está desabilitado em contas criadas após dez/2025

## Nomenclatura Atualizada (2025)

| Nome antigo | Nome atual | Observação |
|-------------|-----------|------------|
| Delta Live Tables (DLT) | Lakeflow Spark Declarative Pipelines (SDP) | `import dlt` ainda funciona |
| Databricks Jobs | Lakeflow Jobs | Sem migração necessária |
| Shared access mode | Standard access mode | Clusters UC multi-user |
| Single user compute | Dedicated compute | Clusters UC single-user/grupo |

## Related Skills

- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - para pipelines (Lakeflow Spark Declarative Pipelines, ex-DLT) que escrevem em tabelas Unity Catalog
- **[databricks-jobs](../databricks-jobs/SKILL.md)** - para dados de execução de jobs (Lakeflow Jobs) visíveis em system tables
- **[databricks-synthetic-data-gen](../databricks-synthetic-data-gen/SKILL.md)** - para geração de dados armazenados em Unity Catalog Volumes
- **[databricks-aibi-dashboards](../databricks-aibi-dashboards/SKILL.md)** - para dashboards construídos sobre dados do Unity Catalog

## Resources

- [Unity Catalog System Tables Reference](https://docs.databricks.com/aws/en/admin/system-tables/)
- [Lineage System Tables](https://docs.databricks.com/aws/en/admin/system-tables/lineage)
- [Compute System Tables](https://docs.databricks.com/aws/en/admin/system-tables/compute)
- [Data Classification System Table](https://docs.databricks.com/aws/en/admin/system-tables/data-classification)
- [Workspaces System Table](https://docs.databricks.com/aws/en/admin/system-tables/workspaces)
- [Billing System Table](https://docs.databricks.com/aws/en/admin/system-tables/billing)
- [Unity Catalog Volumes](https://docs.databricks.com/aws/en/volumes/)
- [What happened to Delta Live Tables (DLT)?](https://docs.databricks.com/aws/en/ldp/where-is-dlt)
