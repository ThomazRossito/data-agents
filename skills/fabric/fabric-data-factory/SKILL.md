# SKILL: Microsoft Fabric Data Factory — Pipelines, Copy Activity e Dataflows Gen2

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric/data-factory)
> **Atualizado:** Janeiro 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines de orquestração ou ingestão no Fabric.

---

## Guia de Decisão: Qual Ferramenta Usar?

| Cenário                                        | Ferramenta Recomendada      | Motivo                                              |
|------------------------------------------------|-----------------------------|-----------------------------------------------------|
| Mover > 1GB de dados de uma fonte externa      | **Copy Activity**           | Alta throughput, suporte a 100+ conectores          |
| Transformações low-code / SQL puro             | **Dataflows Gen2**          | Interface Power Query, query folding                |
| Orquestração de múltiplas atividades           | **Pipeline**                | DAG de atividades, parâmetros, triggers             |
| Transformações complexas em grande escala      | **Notebook Spark**          | PySpark full power, controle total                  |
| Dados em tempo real (streaming)                | **Eventstreams**            | Sem latência, multi-destino                         |
| Ingestão de tabelas relacionais (CDC)          | **Mirroring**               | Zero-ETL, sincronização automática                  |

---

## Pipelines — Orquestração

### Estrutura de um Pipeline

```
Pipeline: "pipeline_medallion_orders"
│
├── Activity 1: Copy Activity "ingest_bronze"
│     ├── Source: Azure SQL Database
│     └── Sink: Lakehouse Bronze (tabela "bronze_orders")
│
├── Activity 2: Notebook Activity "transform_silver"   [depends_on: Activity 1 Success]
│     └── Notebook: "nb_silver_orders" (PySpark MERGE)
│
├── Activity 3: Notebook Activity "build_gold"         [depends_on: Activity 2 Success]
│     └── Notebook: "nb_gold_fato_orders"
│
└── Activity 4: Dataflow Activity "refresh_semantic"   [depends_on: Activity 3 Success]
      └── Dataflow: "df_refresh_gold_model"
```

### JSON de Pipeline (referência via API REST)

```json
{
  "name": "pipeline_medallion_orders",
  "properties": {
    "activities": [
      {
        "name": "ingest_bronze",
        "type": "Copy",
        "dependsOn": [],
        "typeProperties": {
          "source": {
            "type": "AzureSqlSource",
            "sqlReaderQuery": "SELECT * FROM orders WHERE updated_at > '@{pipeline().parameters.last_run_date}'"
          },
          "sink": {
            "type": "LakehouseSink",
            "tableOption": "autoCreate",
            "writeBehavior": "Append"
          }
        }
      },
      {
        "name": "transform_silver",
        "type": "TridentNotebook",
        "dependsOn": [{"activity": "ingest_bronze", "dependencyConditions": ["Succeeded"]}],
        "typeProperties": {
          "notebookId": "<notebook-id>",
          "parameters": {
            "run_date": {"value": "@pipeline().parameters.run_date", "type": "string"}
          }
        }
      }
    ],
    "parameters": {
      "run_date": {"type": "string", "defaultValue": "@utcNow()"},
      "last_run_date": {"type": "string", "defaultValue": "1900-01-01"}
    }
  }
}
```

### Triggers — Tipos e Configuração

| Tipo                  | Quando usar                                    | Configuração                                |
|-----------------------|------------------------------------------------|---------------------------------------------|
| **Scheduled**         | Execução periódica (diária, horária)           | Cron expression ou UI                       |
| **Storage Event**     | Ao detectar novo arquivo no OneLake/ADLS       | Blob trigger via Event Grid                 |
| **Manual**            | Debug / reprocessamento pontual                | Botão Run Now ou API REST                   |
| **Tumbling Window**   | Processamento por janelas de tempo históricas  | Backfill automático com retentativas        |

```json
{
  "name": "trigger_daily_pipeline",
  "properties": {
    "type": "ScheduleTrigger",
    "typeProperties": {
      "recurrence": {
        "frequency": "Day",
        "interval": 1,
        "startTime": "2026-01-01T06:00:00Z",
        "timeZone": "E. South America Standard Time"
      }
    },
    "pipelines": [{"pipelineReference": {"name": "pipeline_medallion_orders"}}]
  }
}
```

---

## Copy Activity — Ingestão de Alto Volume

### Conectores mais usados

```python
# Fabric suporta 100+ conectores via Copy Activity
# Exemplos de configuração de Source:

# Azure SQL Database (incremental por watermark)
source_config = {
    "type": "AzureSqlSource",
    "sqlReaderQuery": "SELECT * FROM orders WHERE updated_at > '@{pipeline().parameters.watermark}'"
}

# REST API (paginação automática)
source_config = {
    "type": "RestSource",
    "httpRequestTimeout": "00:05:00",
    "additionalHeaders": {"Authorization": "Bearer @{activity('get_token').output.token}"}
}

# Parquet/CSV no ADLS Gen2
source_config = {
    "type": "ParquetSource",
    "storeSettings": {"type": "AzureBlobFSReadSettings", "recursive": True}
}
```

### Sink para Lakehouse (padrão recomendado)

```json
{
  "sink": {
    "type": "LakehouseSink",
    "rootFolder": "Tables",
    "tableOption": "autoCreate",
    "writeBehavior": "Upsert",
    "upsertSettings": {
      "useTempDB": false,
      "keys": ["order_id"]
    }
  }
}
```

### Performance do Copy Activity

```
Para máxima throughput:
- Habilitar "Parallel copy": até 32 threads por execução
- "Data Integration Units (DIU)": aumentar para volumes > 10GB (padrão: auto)
- Staging: usar Lakehouse como área de staging para cargas complexas
- "Enable staging" para fontes que não suportam escrita direta ao Lakehouse
```

---

## Dataflows Gen2 — Transformações Low-Code

### Quando usar Dataflows Gen2

- Limpeza e transformação sem código (interface Power Query M)
- Fontes relacionais com query folding (transformações empurradas à fonte)
- Substituição de SSIS/ADF Mapping Data Flows legados
- ETL para usuários não-Spark

### Fast Copy no Dataflows Gen2

O **Fast Copy** é ativado automaticamente quando o Dataflow Gen2 detecta que os dados podem ser transferidos sem transformações pesadas. Usa internamente o backend do Copy Activity:

```
Habilitação automática quando:
  - Fonte suporta query folding (ex: SQL Server, PostgreSQL, Snowflake)
  - Destino é Lakehouse ou Warehouse
  - Sem transformações que quebrem o folding (ex: custom functions complexas)

Configuração explícita:
  Em "Query Settings" → Enable Fast Copy → ON
```

### Staging no Dataflows Gen2

O staging evita problemas de memória em grandes volumes:

```
Sem Staging: Dataflow carrega tudo em memória → OOM para > 1GB
Com Staging: Dataflow usa Lakehouse como área temporária → suporta TB
  Configurar em: Home → Options → Staging → Enable staging
  Staging Lakehouse: selecionar workspace + Lakehouse destino
```

### Boas práticas Dataflows Gen2

```
1. Habilitar staging para transformações > 500MB
2. Preferir folding de queries (verificar "View Native Query")
3. Evitar custom M functions complexas que quebram o folding
4. Usar parâmetros para filtros incrementais (watermark por data)
5. Agendar via Pipeline (não diretamente no Dataflow) para retry automático
```

---

## Orquestração com Variáveis e Parâmetros

```json
// Passagem de parâmetros entre atividades no Pipeline
{
  "name": "get_last_watermark",
  "type": "Lookup",
  "typeProperties": {
    "source": {
      "type": "LakehouseSource",
      "query": "SELECT MAX(updated_at) AS watermark FROM silver.silver_orders"
    }
  }
},
{
  "name": "copy_incremental",
  "type": "Copy",
  "dependsOn": [{"activity": "get_last_watermark", "dependencyConditions": ["Succeeded"]}],
  "typeProperties": {
    "source": {
      "sqlReaderQuery": "SELECT * FROM orders WHERE updated_at > '@{activity('get_last_watermark').output.firstRow.watermark}'"
    }
  }
}
```

---

## Tratamento de Erros e Retentativas

```json
{
  "name": "transform_silver",
  "type": "TridentNotebook",
  "policy": {
    "timeout": "01:00:00",
    "retry": 2,
    "retryIntervalInSeconds": 60,
    "secureInput": false,
    "secureOutput": false
  },
  "onInactiveMarkAs": "Skipped"
}
```

### Atividade de Erro (If Condition + Fail Activity)

```json
{
  "name": "check_row_count",
  "type": "IfCondition",
  "typeProperties": {
    "expression": "@greater(activity('copy_orders').output.rowsRead, 0)",
    "ifFalseActivities": [
      {
        "name": "fail_empty_source",
        "type": "Fail",
        "typeProperties": {
          "message": "Nenhuma linha lida da fonte orders. Verifique a conexão.",
          "errorCode": "EMPTY_SOURCE"
        }
      }
    ]
  }
}
```

---

## Checklist Pipeline Fabric

- [ ] Triggers configurados com timezone correto (não UTC)
- [ ] Parâmetros de watermark para ingestão incremental
- [ ] Retry policy definida em atividades de transformação
- [ ] Logging de execução configurado (via Monitor do Fabric)
- [ ] Alertas de falha configurados (email/Teams via Data Activator ou Azure Monitor)
- [ ] Staging habilitado em Dataflows Gen2 para volumes > 500MB
- [ ] Fast Copy verificado para fontes com query folding
- [ ] Dependências entre atividades definidas com condição correta (Succeeded/Failed/Completed)

---

## Referências

- [Move and transform data with pipelines](https://learn.microsoft.com/en-us/fabric/data-factory/transform-data)
- [Decision guide: pipeline vs dataflow vs Spark](https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-pipeline-dataflow-spark)
- [Dataflow Gen2 performance best practices](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-performance-best-practices)
- [Fast copy in Dataflow Gen2](https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-fast-copy)
