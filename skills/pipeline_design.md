# Skill: Design de Pipelines ETL/ELT

## Arquitetura Medallion (Bronze → Silver → Gold)

```
Fonte (CSV / API / Stream)
        │
        ▼
  ┌─────────────┐
  │   BRONZE    │  Raw data, sem transformação, particionado por data de ingestão.
  │  (Raw Zone) │  Formato: Delta / Parquet
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │   SILVER    │  Dados limpos, tipados, deduplicados, com schema validado.
  │ (Clean Zone)│  Qualidade de dados aplicada (expectations DLT).
  └─────────────┘
        │
        ▼
  ┌─────────────┐
  │    GOLD     │  Agregações, métricas de negócio, modelos dimensionais (Star/Snowflake).
  │ (Serve Zone)│  Otimizado para consulta (Z-ORDER, caching).
  └─────────────┘
```

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
