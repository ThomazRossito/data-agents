---
name: pipeline-design
description: "Arquitetura Medallion (Bronze/Silver/Gold) com regras mandatórias por camada no Lakeflow/SDP, padrões cross-platform Fabric↔Databricks, JSON de Job Databricks e checklist de qualidade de pipeline. Use ao desenhar ou revisar um novo pipeline ETL/ELT."
---

# Skill: Design de Pipelines ETL/ELT

<!-- type: concept -->
## Arquitetura Medallion (Bronze → Silver → Gold)

```
Fonte (CSV / API / Stream)
        │
        ▼
  ┌─────────────┐
  │   BRONZE    │  STREAMING TABLE via cloud_files() (Auto Loader).
  │  (Raw Zone) │  Append-only, sem transformação. Formato: Delta.
  └─────────────┘  Metadados: _ingest_timestamp, _metadata.file_path
        │
        ▼
  ┌─────────────┐
  │   SILVER    │  STREAMING TABLE consumindo via stream(bronze_table).
  │ (Clean Zone)│  SCD Tipo 2 nativo via AUTO CDC INTO (CREATE FLOW).
  └─────────────┘  ⚠️ PROIBIDO: MATERIALIZED VIEW, LAG/LEAD manual, SHA2.
        │
        ▼
  ┌─────────────┐
  │    GOLD     │  MATERIALIZED VIEW para Star Schema e agregações.
  │ (Serve Zone)│  Otimizado para consulta (CLUSTER BY / Z-ORDER).
  └─────────────┘
```

<!-- type: constraint -->
### Regras Mandatórias por Camada (Lakeflow/SDP)

| Camada | Tipo SDP Obrigatório | Padrão de Ingestão | Proibido |
|--------|---------------------|--------------------|----------|
| **Bronze** | `STREAMING TABLE` | `cloud_files()` (Auto Loader) | `read_files`, batch reads, `schemaHints` |
| **Silver** | `STREAMING TABLE` + `CREATE FLOW` | `stream(bronze_table)` + `AUTO CDC INTO` | `MATERIALIZED VIEW`, Window Functions `LAG/LEAD` para SCD2 |
| **Gold** | `MATERIALIZED VIEW` | Leitura direta das tabelas Silver | — |

<!-- type: pattern -->
## Padrão de Pipeline Cross-Platform (Fabric → Databricks)

```
OneLake (Fabric)           Databricks
┌─────────────────┐        ┌─────────────────────────────┐
│  CSV / Parquet  │──────▶│  Bronze: ingestão via ABFSS  │
│  no Lakehouse   │        │  Silver: transformação Spark  │
└─────────────────┘        │  Gold: tabela Unity Catalog  │
                           └─────────────────────────────┘
```

Estratégias de conectividade:
1. **ABFSS path compartilhado**: ambas as plataformas acessam o mesmo Azure Data Lake.
2. **OneLake Shortcut**: Databricks monta o OneLake como volume externo.
3. **Export → Upload**: download do OneLake, upload para Volume Databricks.

<!-- type: example -->
## Configuração de Job Databricks (JSON Reference)

```json
{
  "name": "pipeline_vendas_daily",
  "tasks": [
    {
      "task_key": "ingest",
      "notebook_task": {
        "notebook_path": "/Workspace/pipelines/01_bronze_ingest",
        "source": "WORKSPACE"
      },
      "existing_cluster_id": "<cluster-id>"
    },
    {
      "task_key": "transform",
      "depends_on": [{"task_key": "ingest"}],
      "notebook_task": {
        "notebook_path": "/Workspace/pipelines/02_silver_transform"
      },
      "existing_cluster_id": "<cluster-id>"
    }
  ],
  "schedule": {
    "quartz_cron_expression": "0 0 6 * * ?",
    "timezone_id": "America/Sao_Paulo"
  },
  "max_retries": 2,
  "min_retry_interval_millis": 300000
}
```

<!-- type: constraint -->
## Checklist de Qualidade de Pipeline

- [ ] Schema de entrada validado antes da transformação
- [ ] Nulls tratados (drop obrigatórios, fill opcionais)
- [ ] Deduplicação aplicada (dropDuplicates ou MERGE)
- [ ] Tipos de dados corretos (sem inferSchema em produção)
- [ ] Particionamento definido para tabelas > 10GB
- [ ] OPTIMIZE/ZORDER agendado
- [ ] Monitoramento e alertas configurados
- [ ] Retry policy definida no job
- [ ] Credentials em secrets manager (nunca hardcoded)
- [ ] Testes de dados pós-carga
