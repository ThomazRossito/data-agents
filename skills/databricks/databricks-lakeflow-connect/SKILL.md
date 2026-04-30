---
name: databricks-lakeflow-connect
description: "Patterns and best practices for LakeFlow Connect — Databricks native managed ingestion for streaming data from SaaS applications and databases into Unity Catalog. Use when setting up CDC from databases (PostgreSQL, MySQL, SQL Server, Oracle), ingesting from SaaS sources (Salesforce, ServiceNow, Workday, NetSuite), configuring incremental ingestion pipelines, monitoring connector health and lag, or troubleshooting ingestion failures."
updated_at: 2026-04-30
source: databricks_docs
---

# LakeFlow Connect

LakeFlow Connect is Databricks' **managed ingestion** product for streaming data from external sources into Unity Catalog using Delta Live Tables (DLT) pipelines. It is **GA** as of 2025, replacing the need for third-party ETL tools (Fivetran, Airbyte) for supported source types.

> LakeFlow Connect é diferente de LakeFlow Pipelines (DLT). Connect = ingestão de fontes externas. Pipelines = transformação Spark/SQL dentro do Databricks.

---

## When to Use

| Use Case | LakeFlow Connect |
|----------|-----------------|
| CDC de banco relacional (PostgreSQL, MySQL, SQL Server, Oracle) | ✓ Ideal |
| Ingestão de SaaS (Salesforce, ServiceNow, Workday, NetSuite) | ✓ Ideal |
| Streaming de eventos Kafka / Kinesis | ✗ Usar Auto Loader ou structured streaming diretamente |
| Arquivos em cloud storage (S3, ADLS, GCS) | ✗ Usar Auto Loader |
| APIs REST customizadas | ✗ Construir pipeline Python custom |

---

## Architecture Overview

```
Source (DB / SaaS)
       │
       ▼
LakeFlow Connect (managed connector)
       │  ← DLT pipeline gerenciado pela Databricks
       ▼
Bronze table (Unity Catalog) — raw / append-only
       │
       ▼
Silver table — via DLT transformation (opcional, mesmo pipeline)
```

- Connectors rodam como **DLT pipelines** no workspace Databricks
- Dados são escritos em **Delta tables no Unity Catalog**
- Suporte a **full refresh** e **incremental** (CDC via log-based replication)
- Monitoramento via **Pipeline Events** e métricas nativas do DLT

---

## Supported Sources (GA — Abril 2026)

### Database Sources (CDC via log-based replication)

| Source | CDC Method | Notes |
|--------|-----------|-------|
| PostgreSQL | Logical replication (pgoutput) | Requer `wal_level = logical` |
| MySQL | Binary log (binlog) | Requer `binlog_format = ROW` |
| SQL Server | CDC / change tracking | Requer SQL Server CDC habilitado |
| Oracle | LogMiner | Requer supplemental logging |

### SaaS Sources

| Source | Ingestion Type | Notes |
|--------|---------------|-------|
| Salesforce | Bulk API 2.0 + incremental | Objects e Custom Objects |
| ServiceNow | Table API incremental | Suporte a campos sys_updated_on |
| Workday | Raas Reports incremental | Requer Workday ISU |
| NetSuite | SuiteQL incremental | Requer token-based auth |
| Google Analytics 4 | Batch daily | 28 dias de lookback |
| HubSpot | REST API incremental | Deals, contacts, companies |

---

## Quick Start — Database CDC (PostgreSQL)

### 1. Pré-requisitos no PostgreSQL

```sql
-- No PostgreSQL, habilitar logical replication
ALTER SYSTEM SET wal_level = logical;
ALTER SYSTEM SET max_replication_slots = 10;
SELECT pg_reload_conf();

-- Criar usuário de replicação
CREATE USER lakeflow_user WITH REPLICATION LOGIN PASSWORD 'secure-password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO lakeflow_user;

-- Habilitar replicação para tabelas específicas
CREATE PUBLICATION lakeflow_pub FOR TABLE orders, customers, products;
```

### 2. Criar Connection no Databricks

```python
# Via Databricks SDK
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Criar connection para PostgreSQL
connection = w.connections.create(
    name="prod-postgresql",
    connection_type="POSTGRESQL",
    options={
        "host": "prod-db.example.com",
        "port": "5432",
        "database": "mydb",
        "user": "lakeflow_user",
        "password": "{{secrets/lakeflow/pg-password}}",  # usar Databricks Secrets
    }
)
print(f"Connection ID: {connection.name}")
```

### 3. Criar Ingestion Pipeline

```python
# Criar pipeline de ingestão LakeFlow Connect
pipeline = w.pipelines.create(
    name="postgresql-cdc-pipeline",
    ingestion_definition={
        "connection_name": "prod-postgresql",
        "objects": [
            {
                "schema": {
                    "source_catalog": None,  # não aplicável para DB sources
                    "source_schema": "public",
                    "destination_catalog": "main",
                    "destination_schema": "bronze_postgresql",
                }
            }
        ],
    },
    catalog="main",
    target="bronze_postgresql",
    channel="CURRENT",
    continuous=True,  # modo streaming contínuo
    development=False,
)
print(f"Pipeline ID: {pipeline.pipeline_id}")
```

### 4. Iniciar e Monitorar

```python
# Iniciar pipeline
w.pipelines.start_update(pipeline_id=pipeline.pipeline_id)

# Verificar status
import time
while True:
    status = w.pipelines.get(pipeline_id=pipeline.pipeline_id)
    print(f"State: {status.state} | Health: {status.health}")
    if status.state in ("RUNNING", "FAILED", "IDLE"):
        break
    time.sleep(10)
```

---

## Quick Start — SaaS Source (Salesforce)

### 1. Criar Connection Salesforce

```python
connection = w.connections.create(
    name="salesforce-prod",
    connection_type="SALESFORCE",
    options={
        "client_id": "{{secrets/salesforce/client-id}}",
        "client_secret": "{{secrets/salesforce/client-secret}}",
        "username": "integration@company.com",
        "password": "{{secrets/salesforce/password}}",
        "security_token": "{{secrets/salesforce/token}}",
        "instance_url": "https://company.my.salesforce.com",
        "api_version": "59.0",
    }
)
```

### 2. Criar Pipeline com objetos específicos

```python
pipeline = w.pipelines.create(
    name="salesforce-ingestion",
    ingestion_definition={
        "connection_name": "salesforce-prod",
        "objects": [
            {
                "table": {
                    "source_catalog": None,
                    "source_schema": None,
                    "source_table": "Opportunity",
                    "destination_catalog": "main",
                    "destination_schema": "bronze_salesforce",
                    "destination_table": "opportunity",
                }
            },
            {
                "table": {
                    "source_table": "Account",
                    "destination_catalog": "main",
                    "destination_schema": "bronze_salesforce",
                    "destination_table": "account",
                }
            },
            {
                "table": {
                    "source_table": "Lead",
                    "destination_catalog": "main",
                    "destination_schema": "bronze_salesforce",
                    "destination_table": "lead",
                }
            },
        ],
    },
    catalog="main",
    target="bronze_salesforce",
    channel="CURRENT",
    continuous=False,  # scheduled para SaaS (não tem CDC real-time)
)
```

---

## Monitoramento e Observabilidade

### Verificar lag de replicação (DB sources)

```sql
-- Consultar métricas do pipeline via system tables
SELECT
  pipeline_id,
  pipeline_name,
  timestamp,
  level,
  message
FROM system.lakeflow.pipeline_events
WHERE pipeline_name = 'postgresql-cdc-pipeline'
  AND timestamp > now() - INTERVAL 1 HOUR
ORDER BY timestamp DESC
LIMIT 50;
```

### Verificar tabelas ingeridas e row counts

```sql
-- Verificar tabelas no schema bronze
SHOW TABLES IN main.bronze_postgresql;

-- Row count de uma tabela ingerida
SELECT COUNT(*), MAX(_commit_timestamp) as last_cdc_event
FROM main.bronze_postgresql.orders;
```

### Alertas recomendados

```python
# Configurar alerta de pipeline via Databricks Jobs (wrapper)
w.jobs.create(
    name="lakeflow-connect-health-check",
    tasks=[{
        "task_key": "health_check",
        "notebook_task": {
            "notebook_path": "/pipelines/health_check",
        },
        "existing_cluster_id": "...",
    }],
    schedule={
        "quartz_cron_expression": "0 */15 * * * ?",  # a cada 15 minutos
        "timezone_id": "America/Sao_Paulo",
    },
    email_notifications={
        "on_failure": ["data-team@company.com"],
    }
)
```

---

## Transformações Downstream (Silver Layer)

LakeFlow Connect grava na camada Bronze. Use DLT para transformar para Silver no mesmo pipeline ou em pipeline separado:

```python
# Adicionar transformação Silver ao mesmo pipeline (DLT notebook)
import dlt
from pyspark.sql.functions import col, current_timestamp

@dlt.table(
    name="silver_orders",
    comment="Cleaned orders from PostgreSQL CDC",
    table_properties={"quality": "silver"},
)
@dlt.expect_or_drop("valid_order_id", "order_id IS NOT NULL")
@dlt.expect_or_drop("valid_amount", "amount > 0")
def silver_orders():
    return (
        dlt.read_stream("bronze_postgresql.orders")
        .filter(col("_change_type") != "delete")  # excluir deletes do CDC
        .select(
            col("order_id"),
            col("customer_id"),
            col("amount").cast("decimal(18,2)"),
            col("status"),
            col("created_at"),
            current_timestamp().alias("processed_at"),
        )
    )
```

---

## Schema Evolution

LakeFlow Connect suporta **schema evolution automático** por padrão:

| Evento | Comportamento padrão |
|--------|---------------------|
| Nova coluna no source | Adicionada automaticamente na tabela Delta |
| Coluna removida no source | Mantida na Delta com `NULL` para novos registros |
| Mudança de tipo (ex: INT → BIGINT) | Aceita se compatível (widening); falha se incompatível |
| Rename de coluna | Tratada como drop + add (coluna antiga com NULLs) |

Para desabilitar evolution automático:
```python
pipeline = w.pipelines.create(
    ...,
    ingestion_definition={
        ...,
        "schema_evolution_mode": "NONE",  # ou "ADD_COLUMNS_ONLY"
    }
)
```

---

## Troubleshooting

| Sintoma | Causa provável | Solução |
|---------|---------------|---------|
| Pipeline em `FAILED` com erro de replicação | `wal_level` não é `logical` no PostgreSQL | `ALTER SYSTEM SET wal_level = logical; SELECT pg_reload_conf();` |
| Lag crescente no CDC | Tabela source sem índice na PK | Adicionar índice primário + verificar replica identity |
| SaaS connector com `RATE_LIMITED` | Muitas requisições à API do SaaS | Reduzir frequência de polling em `schedule_interval` |
| Tabela com registros duplicados | Pipeline reiniciado sem checkpoint limpo | Verificar `_commit_version` e deduplificar com `MERGE` |
| Schema evolution falhou | Mudança de tipo incompatível (ex: BIGINT → INT) | Recriar tabela destino com novo schema |

---

## Boas Práticas

1. **Sempre usar Databricks Secrets** para credenciais — nunca hardcode em opções do connector
2. **Nomear connections** com ambiente: `postgresql-prod`, `salesforce-staging`
3. **Separar schemas Bronze por source**: `bronze_postgresql`, `bronze_salesforce` — facilita lineage
4. **Monitorar `_commit_timestamp`** nas tabelas Bronze para detectar lag de CDC
5. **Usar `continuous=True`** apenas para fontes com CDC real (DB). Para SaaS, usar scheduled com `continuous=False`
6. **Schema Bronze = append-only**: nunca atualizar tabelas Bronze diretamente — deixar o connector gerenciar
7. **Testar em desenvolvimento primeiro**: criar pipeline com `development=True` para validar configuração antes de produção

---

## Referências

- Databricks Docs: [LakeFlow Connect](https://docs.databricks.com/ingestion/lakeflow-connect/index.html)
- Databricks Docs: [Supported Sources](https://docs.databricks.com/ingestion/lakeflow-connect/sources/index.html)
- Skill relacionada: `skills/databricks/databricks-spark-declarative-pipelines/` — DLT para transformação Silver/Gold
- KB relacionada: `kb/pipeline-design/` — padrões Medallion e orquestração
- KB relacionada: `kb/databricks/` — Unity Catalog e Delta Lake
