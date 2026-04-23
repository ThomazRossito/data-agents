---
skill: fabric-data-factory
domain: fabric
updated_at: 2026-04-23
version: "2.1"
source: web_search
sources:
  - https://learn.microsoft.com/en-us/fabric/data-factory/transform-data
  - https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-pipeline-dataflow-spark
  - https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-performance-best-practices
  - https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-fast-copy
  - https://learn.microsoft.com/en-us/fabric/data-factory/what-is-copy-job
  - https://learn.microsoft.com/en-us/fabric/data-factory/copy-job-activity
  - https://blog.fabric.microsoft.com/en-us/blog/modernizing-pipelines-new-activities-and-innovations-in-fabric-data-factory-pipelines
  - https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-overview
---

# SKILL: Microsoft Fabric Data Factory — Pipelines, Copy Activity, Copy Job e Dataflows Gen2

> **Fonte:** Microsoft Learn + Microsoft Fabric Blog
> **Atualizado:** 2026-04-23
> **Uso:** Leia este arquivo ANTES de projetar pipelines de orquestração ou ingestão no Fabric.

---

## ⚠️ Notas de Breaking Change / Renomeações Relevantes

> ⚠️ **Breaking change em abril/2026 — Dataflows Gen2 Classic descontinuado:**
> A opção de criar novos Dataflows Gen2 *sem* suporte a CI/CD e Git integration ("Dataflow Gen2 Classic") não está mais disponível. Todos os novos itens Dataflow Gen2 são criados com CI/CD e Git integration por padrão. Itens existentes continuam funcionando; para convertê-los, use o recurso **"Save As"**.

> ℹ️ **Renomeação em setembro/2025 — "Data pipeline" → "Pipeline":**
> O nome de exibição nos workspaces foi alterado de *"Data pipeline"* para simplesmente *"Pipeline"*, sem nenhum impacto em APIs, CICD ou definições JSON.

> ℹ️ **Expansão de conectores:** O Fabric Data Factory passou de 100+ para **170+ conectores nativos** (nov/2025).

---

## Guia de Decisão: Qual Ferramenta Usar?

| Cenário                                              | Ferramenta Recomendada         | Motivo                                                                       |
|------------------------------------------------------|--------------------------------|------------------------------------------------------------------------------|
| Mover > 1 GB de dados, controle granular de mapping  | **Copy Activity** (em Pipeline) | Alta throughput, 170+ conectores, configuração detalhada via JSON             |
| Ingestão simples sem pipeline, batch ou incremental  | **Copy Job** (standalone)      | Experiência guiada, incremental + CDC nativo, sem código                     |
| Copy Job dentro de orquestração maior                | **Copy Job Activity** (GA)     | Combina simplicidade do Copy Job com retry/dependências do Pipeline           |
| Transformações low-code / SQL puro                   | **Dataflows Gen2**             | Interface Power Query, query folding, agora sempre com CI/CD+Git              |
| Orquestração de múltiplas atividades                 | **Pipeline**                   | DAG de atividades, parâmetros, triggers (antes chamado "Data pipeline")       |
| Transformações complexas em grande escala            | **Notebook Spark**             | PySpark full power, controle total                                           |
| Dados em tempo real (streaming)                      | **Eventstreams**               | Sem latência, multi-destino                                                  |
| Ingestão de tabelas relacionais (CDC zero-ETL)       | **Mirroring**                  | Sincronização automática, agora com suporte a PostgreSQL, Snowflake, SAP      |
| Manutenção de Lakehouse (OPTIMIZE, VACUUM)           | **Lakehouse Maintenance Activity** (Preview) | Nativo em Pipeline, sem scripts externos                        |
| Refresh do SQL Endpoint do Lakehouse                 | **Refresh SQL Endpoint Activity** (Preview) | Garante que BI e relatórios leem o estado mais recente             |
| Orquestrar transformações dbt                        | **dbt Job Activity** (Preview) | Integração nativa em Pipelines sem trocar de ferramenta                      |

---

## Pipelines — Orquestração

> ℹ️ O tipo de item "Data pipeline" foi renomeado para **"Pipeline"** na UI do Fabric (set/2025). Nenhum impacto em APIs ou CI/CD — o campo `"type"` no JSON permanece o mesmo.

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
├── Activity 4: Semantic Model Refresh "refresh_semantic"  [depends_on: Activity 3 Success]
│     └── Power BI Semantic Model: "sm_gold_orders"       ← agora GA; prefira a este em vez de Dataflow Activity
│
└── Activity 5: Lakehouse Maintenance "optimize_bronze"   [depends_on: Activity 1 Success, Preview]
      └── Lakehouse: "lh_bronze" (OPTIMIZE + VACUUM automático)
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

| Tipo                  | Quando usar                                    | Configuração                                             |
|-----------------------|------------------------------------------------|----------------------------------------------------------|
| **Scheduled**         | Execução periódica (diária, horária)           | Cron expression ou UI                                    |
| **Storage Event**     | Ao detectar novo arquivo no OneLake/ADLS       | Blob trigger via Event Grid                              |
| **Pipeline Event**    | Ao concluir outro Pipeline (GA)                | Encadear workflows sem polling manual                    |
| **Lakehouse Folder Event** | Ao detectar evento em pasta específica do Lakehouse | Trigger nativo no Fabric, sem Event Grid externo  |
| **Manual**            | Debug / reprocessamento pontual                | Botão Run Now ou API REST                                |
| **Tumbling Window**   | Processamento por janelas de tempo históricas  | Backfill automático com retentativas                     |

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

## Copy Activity — Ingestão de Alto Volume (Controle Granular)

> **Use Copy Activity quando precisar de:** mapeamento de colunas explícito, transformações inline, controle de DIU/paralelismo, ou fontes/sinks que o Copy Job ainda não suporta como destino avançado.

### Conectores mais usados (seleção — 170+ disponíveis)

```python
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

## Copy Job — Ingestão Simplificada (Sem Código) ✨ NOVO

> **Copy Job é a escolha preferida para ingestão direta** quando não há necessidade de orquestração complexa ou mapeamento manual. Para usá-lo dentro de um Pipeline, utilize a **Copy Job Activity** (GA desde nov/2025).

### Modos de cópia suportados

```
Copy Job suporta nativamente três modos de entrega:

1. Full Copy      — copia todos os dados a cada execução
2. Incremental Copy (GA) — primeira execução faz full copy;
                           execuções seguintes copiam apenas dados novos/alterados.
                           Gerencia watermark automaticamente.
                           Suporta reset por tabela individual (útil para reconciliação).
3. CDC Replication — replica inserts, updates e deletes via Change Data Capture.
                     Suporte a SQL Server, PostgreSQL, Snowflake, SAP, BigQuery, CosmosDB.
```

### Tipos de coluna watermark suportados em incremental copy

```
- ROWVERSION  → ideal para SQL com alto throughput transacional
- Datetime    → LastUpdatedDatetime, ModifiedAt — precisão de timestamp
- Date        → LastUpdatedDate — aplica extração com delay automático para evitar perda de dados
```

### Copy Job Activity dentro de um Pipeline

```json
{
  "name": "copy_orders_incremental",
  "type": "CopyJob",
  "dependsOn": [],
  "typeProperties": {
    "copyJobReference": {
      "type": "CopyJobReference",
      "referenceName": "cj_orders_bronze"
    }
  },
  "policy": {
    "timeout": "02:00:00",
    "retry": 2,
    "retryIntervalInSeconds": 60
  }
}
```

> **Vantagem sobre Copy Activity puro:** Copy Job Activity incorpora batch + incremental + CDC com telemetria embutida e sem configuração manual de watermark. Use Copy Activity quando precisar de controle granular de mapeamento ou transformações inline.

### Auto-partitioning (Preview — abr/2026)

```
Copy Job agora pode particionar automaticamente tabelas grandes durante o movimento de dados,
entregando ganhos de throughput sem configuração manual.

Habilitação: Advanced Settings → Auto-partitioning → ON
Modo suportado: Watermark-based incremental copy (full + incremental)

Bônus independente de configuração:
  - Escrita para Lakehouse Tables é 2× mais rápida por padrão (sem ação necessária).
```

### Upsert em múltiplos destinos

```
Copy Job agora suporta upsert (merge) diretamente para:
  - Fabric Lakehouse Table
  - Salesforce / Salesforce Service Cloud
  - Dataverse / Dynamics 365 / Dynamics CRM
  - Azure Cosmos DB for NoSQL
```

---

## Dataflows Gen2 — Transformações Low-Code

> ⚠️ **Breaking change em abril/2026:** Novos Dataflows Gen2 são criados **exclusivamente** com CI/CD e Git integration. O modo "Classic" (sem CI/CD) não está mais disponível para novos itens. Use `Save As` para migrar itens existentes.

### Quando usar Dataflows Gen2

- Limpeza e transformação sem código (interface Power Query M)
- Fontes relacionais com query folding (transformações empurradas à fonte)
- Substituição de SSIS/ADF Mapping Data Flows legados
- ETL para usuários não-Spark
- Cenários com CI/CD, versionamento Git e deploy via Deployment Pipelines

### Novidades relevantes (2025–2026)

```
CI/CD e Git integration (agora padrão):
  - Versionamento via Git (branching, merging, rollback)
  - Deploy automatizado via Deployment Pipelines do Fabric
  - Variable Library integration (GA): valores de configuração centralizados,
    resolvidos em runtime — ideal para parametrizar ambientes (dev/homolog/prod)

AI Function Transforms (Preview):
  - Aplicar transformações de IA diretamente no Dataflow:
    entity extraction, sentiment analysis, language detection
  - Sem necessidade de código customizado

Modern Query Evaluation Engine (Preview):
  - Motor de avaliação mais rápido para Dataflow Gen2 (CI/CD)
  - Habilitado em: Options → Scale tab → Modern Evaluator → ON
  - Suporte inicial: Azure Blob Storage, ADLS, Fabric Lakehouse, Fabric Warehouse,
    OData, SharePoint, Web e outros

Incremental Refresh:
  - Disponível via right-click na query → "Incremental Refresh"
  - Reduz tempo de atualização para grandes volumes sem reprocessar tudo

Multitasking:
  - Múltiplos Dataflows Gen2 podem estar abertos simultaneamente com outras
    experiências do Fabric
```

### Fast Copy no Dataflows Gen2 (GA)

O **Fast Copy** usa internamente o backend do Copy Activity para ingerir grandes volumes:

```
Habilitação manual:
  Home → Options → Scale tab → "Allow use of fast copy connectors" → ON

Indicador de uso:
  Verifique os "fast copy indicators" na query — quando ativo, o Engine type
  exibe "CopyActivity". Após o refresh, confirme em "Refresh history".

Destino suportado pelo Fast Copy diretamente:
  Apenas Lakehouse. Para outros destinos: stage a query primeiro e
  referencie-a em outra query com o destino desejado.

Forçar fast copy (debug):
  Right-click na query → "Require fast copy"

Suporte a arquivos (ADLS/Blob):
  Apenas .csv e .parquet são suportados via fast copy.
```

### Staging no Dataflows Gen2

```
Sem Staging: Dataflow carrega tudo em memória → OOM para > 1GB
Com Staging: Dataflow usa Lakehouse como área temporária → suporta TB,
             com compute do Warehouse para transformações em larga escala.

Configurar em: Home → Options → Staging → Enable staging
Staging Lakehouse: provisionado automaticamente ao criar o primeiro Dataflow
                   Gen2 no workspace. NÃO deletar estes artefatos.

Atenção: staging nem sempre melhora performance — avalie por caso.
Para volumes menores ou dataflows simples, o overhead pode superar o benefício.
```

### Boas práticas Dataflows Gen2

```
1. Migrar Dataflows Gen2 Classic para CI/CD usando "Save As" (abril/2026 obrigatório para novos)
2. Habilitar staging para transformações > 500MB
3. Preferir query folding (verificar "View Native Query")
4. Evitar custom M functions complexas que quebram o folding
5. Usar parâmetros para filtros incrementais (watermark por data)
6. Agendar via Pipeline (não diretamente no Dataflow) para retry automático
7. Usar Variable Library para separar configurações de ambiente (dev/prod)
8. Habilitar Modern Evaluator Engine em Dataflows Gen2 CI/CD para ganho de performance
```

---

## Lakehouse Utility Suite — Novas Atividades de Pipeline (Preview) ✨ NOVO

> Introduzidas no FabCon Atlanta 2026 (março/2026). Evitam a necessidade de scripts externos ou notebooks separados para manutenção do Lakehouse.

### Lakehouse Maintenance Activity

```
Finalidade: automatizar tarefas de manutenção rotineiras do Lakehouse
            (OPTIMIZE, VACUUM, atualização de estatísticas).
Uso típico: agendar após ingestão de bronze para compactar arquivos Delta.
Configuração: adicionar à canvas do pipeline → selecionar Lakehouse →
              configurar operações desejadas.
Docs: aka.ms/LakehouseMaintenanceDocs
```

### Refresh SQL Endpoint Activity

```
Finalidade: forçar o refresh do SQL Endpoint do Lakehouse on demand ou
            em schedule, garantindo que camadas de BI/relatórios leiam
            o estado mais recente após ingestão ou transformação.
Uso típico: adicionar ao final do pipeline, após a atividade de build_gold,
            antes de qualquer refresh de Semantic Model.
Docs: aka.ms/RSQLDocs
```

---

## dbt Job Activity — Orchestração de Transformações dbt (Preview) ✨ NOVO

> Anunciado no Ignite 2025 (nov/2025), disponível em preview em Pipelines.

```
Finalidade: executar dbt jobs diretamente dentro de Pipelines do Fabric,
            sem trocar de ferramenta ou usar notebooks como wrapper.
Benefícios:
  - Combinar ingestão (Copy Activity/Copy Job) + transformação (dbt) +
    consumo (Semantic Model Refresh) em um único pipeline end-to-end.
  - Manter versionamento, testes e documentação do dbt nativamente.
  - Governança e monitoramento unificados no Monitor Hub do Fabric.

Exemplo de encadeamento:
  Copy Job Activity → dbt Job Activity → Refresh SQL Endpoint → Semantic Model Refresh
```

---

## Semantic Model Refresh Activity (GA) ✨ NOVO

> Tornou-se **GA em maio/2025**. Prefira esta atividade ao invés de usar Dataflow Activity para refresh de modelos Power BI.

```json
{
  "name": "refresh_semantic_model",
  "type": "SemanticModelRefresh",
  "dependsOn": [{"activity": "build_gold", "dependencyConditions": ["Succeeded"]}],
  "typeProperties": {
    "datasetId": "<semantic-model-id>",
    "workspaceId": "<workspace-id>"
  },
  "policy": {
    "timeout": "01:00:00",
    "retry": 1,
    "retryIntervalInSeconds": 60
  }
}
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

> **Alternativa sem gestão manual de watermark:** Use **Copy Job Activity** com modo `Incremental Copy` — o watermark é gerenciado automaticamente, inclusive com suporte a reset por tabela individual.

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

### Copilot para Expressões de Pipeline (Preview)

```
O Pipeline Expression Builder agora conta com Copilot integrado (preview):
  - Gere expressões descrevendo sua intenção em linguagem natural
  - Explique expressões existentes em linguagem simples
  - Acesso: diretamente no Expression Builder, via ícone Copilot
```

---

## Checklist Pipeline Fabric

- [ ] Triggers configurados com timezone correto (não UTC cru)
- [ ] Usar **Copy Job Activity** para ingestão incremental/CDC sem gestão manual de watermark
- [ ] Usar **Copy Activity** apenas quando precisar de mapeamento granular ou fontes não suportadas pelo Copy Job
- [ ] Retry policy definida em atividades de transformação
- [ ] Logging de execução configurado (via Monitor Hub do Fabric, com hierarquia de runs)
- [ ] Alertas de falha configurados (email/Teams via Data Activator ou Azure Monitor)
- [ ] Staging habilitado em Dataflows Gen2 para volumes > 500MB (avaliar caso a caso)
- [ ] Fast Copy verificado para fontes com query folding (checar "fast copy indicators")
- [ ] Modern Evaluator Engine habilitado em Dataflows Gen2 CI/CD
- [ ] Variable Library configurada para separar parâmetros de ambiente (dev/prod)
- [ ] Dataflows Gen2 Classic migrados para CI/CD via "Save As" (breaking change abr/2026)
- [ ] **Lakehouse Maintenance Activity** agendada após ingestões de alto volume (preview)
- [ ] **Refresh SQL Endpoint Activity** adicionada antes de Semantic Model Refresh (preview)
- [ ] **Semantic Model Refresh Activity** (GA) substituindo Dataflow Activity para refresh de modelos
- [ ] Dependências entre atividades definidas com condição correta (Succeeded/Failed/Completed)
- [ ] Notebooks executados via Service Principal para workloads de produção

---

## Referências

- [Move and transform data with pipelines](https://learn.microsoft.com/en-us/fabric/data-factory/transform-data)
- [Decision guide: pipeline vs dataflow vs Spark](https://learn.microsoft.com/en-us/fabric/fundamentals/decision-guide-pipeline-dataflow-spark)
- [Dataflow Gen2 performance best practices](https://learn.microsoft.com/en-us/fabric/data-factory/dataflow-gen2-performance-best-practices)
- [Fast copy in Dataflow Gen2](https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-fast-copy)
- [What is Copy job in Data Factory](https://learn.microsoft.com/en-us/fabric/data-factory/what-is-copy-job)
- [Copy Job Activity in Data Factory Pipelines](https://learn.microsoft.com/en-us/fabric/data-factory/copy-job-activity)
- [Differences between Dataflow Gen1 and Gen2 (CI/CD change)](https://learn.microsoft.com/en-us/fabric/data-factory/dataflows-gen2-overview)
- [Lakehouse Maintenance Activity docs](https://aka.ms/LakehouseMaintenanceDocs)
- [Refresh SQL Endpoint Activity docs](https://aka.ms/RSQLDocs)
- [Copy activity reference](https://learn.microsoft.com/en-us/fabric/data-factory/copy-data-activity)
