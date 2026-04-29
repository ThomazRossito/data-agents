# Pattern: Databricks Lakehouse Setup

## Pré-requisitos
- Workspace Databricks (Azure) com Unity Catalog habilitado
- ADLS Gen2 storage account
- Managed Identity ou Service Principal com Storage Blob Data Contributor

## Estrutura Unity Catalog
```
metastore (região — 1 por workspace por padrão)
└── catalog: prod / dev / test
    └── schema: <domain>_bronze / <domain>_silver / <domain>_gold
        └── table: <entity>_<suffix>
```

## Setup passo a passo

### 1. Storage Credential
```sql
CREATE STORAGE CREDENTIAL my_adls_cred
WITH AZURE_MANAGED_IDENTITY = 'managed-identity-resource-id';
```

### 2. External Location
```sql
CREATE EXTERNAL LOCATION bronze_location
URL 'abfss://bronze@mystorageaccount.dfs.core.windows.net/'
WITH (STORAGE CREDENTIAL my_adls_cred);

GRANT READ FILES, WRITE FILES ON EXTERNAL LOCATION bronze_location
TO `data-engineers`;
```

### 3. Catalog + Schema
```sql
CREATE CATALOG IF NOT EXISTS prod COMMENT 'Prod catalog';
USE CATALOG prod;

CREATE SCHEMA IF NOT EXISTS sales_bronze
    MANAGED LOCATION 'abfss://bronze@mystorageaccount.dfs.core.windows.net/sales/'
    COMMENT 'Raw ingestão vendas';

CREATE SCHEMA IF NOT EXISTS sales_silver COMMENT 'Dados curados vendas';
CREATE SCHEMA IF NOT EXISTS sales_gold   COMMENT 'Camada serving vendas';
```

### 4. Tabela Delta Managed
```sql
CREATE TABLE IF NOT EXISTS prod.sales_bronze.order_raw (
    order_id BIGINT,
    customer_id BIGINT,
    order_date DATE,
    amount DECIMAL(18,2),
    ingestion_ts TIMESTAMP DEFAULT current_timestamp()
)
USING DELTA
PARTITIONED BY (ingestion_date DATE)
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact'   = 'true'
);
```

### 5. Job Cluster (recomendado para produção)
```json
{
  "cluster_type": "job_cluster",
  "spark_version": "15.4.x-scala2.12",
  "node_type_id": "Standard_DS3_v2",
  "num_workers": 2,
  "spark_conf": {
    "spark.sql.shuffle.partitions": "auto",
    "spark.databricks.delta.optimizeWrite.enabled": "true"
  }
}
```

## Auto Loader (ingestão incremental)
```python
(
    spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("cloudFiles.schemaLocation", f"{CHECKPOINT_PATH}/schema")
    .load(SOURCE_PATH)
    .writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", CHECKPOINT_PATH)
    .trigger(availableNow=True)
    .toTable("prod.sales_bronze.order_raw")
)
```

## Anti-padrões
- NÃO usar `spark.read` sem checkpoint em streaming → perde linearity
- NÃO criar external tables em caminhos MANAGED → conflito de propriedade
- NÃO usar `INSERT OVERWRITE` em tabelas particionadas sem `replaceWhere`
