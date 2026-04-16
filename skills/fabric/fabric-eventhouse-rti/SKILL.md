---
updated_at: "2026-04-16"
source: kb/fabric/concepts/rti-concepts.md + kb/fabric/patterns/rti-patterns.md + skills/fabric/kql-rti-optimizations.md
---

# SKILL: Microsoft Fabric — Real-Time Intelligence (Eventhouse, KQL, Eventstreams, Activator)

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric/real-time-intelligence) + KB interna
> **Atualizado:** Abril 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines de dados em tempo real no Fabric.

---

## Componentes do Real-Time Intelligence (RTI)

```
Fontes de Eventos
  (Kafka, Event Hub, IoT Hub, APIs, Change Data, Cosmos DB Change Feed)
         │
         ▼
  ┌─────────────┐
  │ EVENTSTREAM │  Ingestão e roteamento sem código
  └─────────────┘
     │         │         │
     ▼         ▼         ▼
EVENTHOUSE  LAKEHOUSE  ACTIVATOR
(KQL/Kusto)  (Delta)  (Alertas/Ações)
```

**Latência típica:** <1 segundo (vs. Lakehouse batch: minutos).

### Eventhouse

Container para múltiplos **KQL Databases** (Kusto). Otimizado para dados de séries temporais, logs, telemetria. Dados são automaticamente indexados por tempo de ingestão. Suporta hot cache (memória) + cold storage (OneLake Parquet).

### Eventstreams

Pipeline de streaming sem código. Conecta fontes (Event Hub, Kafka, IoT Hub, Custom Apps, Event Grid, Cosmos DB Change Feed) a múltiplos destinos simultaneamente (Eventhouse, Lakehouse, Activator). Suporta transformações inline (filter, aggregate, join).

### Activator

Motor de automação baseado em regras sobre dados em tempo real. Monitora Eventstreams ou Eventhouse e dispara ações (email, Teams, webhook, Power Automate) quando condições são atendidas.

---

## Decision Matrix: Lakehouse vs Eventhouse

Use esta matriz para decidir onde armazenar dados.

| Use Lakehouse quando...                          | Use Eventhouse quando...                        |
|--------------------------------------------------|-------------------------------------------------|
| Dados batch (diários, horários)                  | Streaming contínuo (eventos/logs)               |
| Schema estável, transformações complexas         | Real-time dashboards (<1s latência)             |
| BI/Reports com Direct Lake                       | Alertas automáticos via Activator               |
| Volume: 100 GB–10 TB histórico                   | Volume: 1M–10M+ eventos/dia com TTL curto       |
| Joins complexos com dimensões estáveis           | Séries temporais, telemetria, IoT, logs         |

---

## KQL — Kusto Query Language

### Sintaxe Fundamental

```kusto
// Tabela de eventos — KQL é orientado a pipe (|)
// REGRA #1: Sempre filtre por tempo na PRIMEIRA linha (predicate pushdown de partição)
eventos
| where ingestion_time() > ago(1h)        // Filtro temporal obrigatório primeiro
| where status == "error"
| project timestamp, source, message, level
| order by timestamp desc
```

### Comparação SQL → KQL

| SQL                                    | KQL                                                    |
|----------------------------------------|--------------------------------------------------------|
| `SELECT col FROM tbl WHERE x = 'y'`   | `tbl \| where x == 'y' \| project col`               |
| `GROUP BY col`                         | `\| summarize count() by col`                         |
| `COUNT(*) AS total`                    | `\| summarize total = count()`                        |
| `BETWEEN date1 AND date2`              | `\| where timestamp between (date1 .. date2)`         |
| `TOP 10`                               | `\| take 10` ou `\| top 10 by col`                   |
| `JOIN ON`                              | `\| join kind=inner (outra_tabela) on chave`          |
| `LIKE '%texto%'`                       | `\| where col contains "texto"` (case-insensitive)   |
| `DISTINCT col`                         | `\| distinct col` ou `\| summarize by col`            |
| `ORDER BY col DESC`                    | `\| order by col desc` ou `\| sort by col desc`      |
| `COUNT(DISTINCT col)`                  | `\| summarize dcount(col)`                            |

### Agregações e Séries Temporais

```kusto
// Contagem por janela de 5 minutos com métricas adicionais
telemetria
| where ingestion_time() > ago(24h)
| summarize
    total_eventos = count(),
    usuarios_unicos = dcount(user_id),
    erros = countif(level == "ERROR"),
    latencia_p99 = percentile(response_ms, 99),
    avg_latencia = avg(response_ms)
    by bin(timestamp, 5m), endpoint
| order by timestamp desc

// Render como gráfico de série temporal (Fabric RTI dashboard)
telemetria
| where ingestion_time() > ago(7d)
| summarize count() by bin(timestamp, 1h), event_type
| render timechart
```

### Detecção de Anomalias

```kusto
// Anomaly detection nativa do KQL
telemetria
| where ingestion_time() > ago(7d)
| make-series total = count() on timestamp from ago(7d) to now() step 1h
| extend anomalias = series_decompose_anomalies(total, 1.5)
| mv-expand timestamp, total, anomalias
| where anomalias != 0
| project timestamp, total, anomalias
```

### Join entre KQL Database e Lakehouse (OneLake)

```kusto
// External Table aponta para dados Delta no OneLake
// Configurar primeiro via .create external table
eventos_rt
| where ingestion_time() > ago(1h)
| join kind=leftouter (
    external_table("silver_clientes")  // tabela externa no OneLake
    | project customer_id, name, region
) on customer_id
| summarize eventos = count() by region
```

---

## Materialized Views

Materialized Views pré-computam agregações e são atualizadas incrementalmente. Use para queries recorrentes de alto custo.

```kusto
// Criar MV com agregação horária
.create materialized-view hourly_stats
  on table user_events
{
  user_events
  | summarize
      event_count = count(),
      unique_users = dcount(user_id),
      avg_value = avg(value)
      by bin(timestamp, 1h), event_type
}

// Query MV — resposta instantânea (dados pré-computados)
hourly_stats
| where timestamp > ago(24h)
| order by timestamp desc

// Verificar status da MV
.show materialized-view hourly_stats
```

**Quando usar:** agregações por janela de tempo consultadas repetidamente, dashboards de baixa latência, relatórios por hora/dia.

---

## Políticas de Retenção e Cache

### Configuração de Caching Policy

```kusto
// Hot cache: dados mantidos em memória para queries rápidas
// Cold storage: dados em OneLake (Parquet) — mais barato, mais lento

// Definir hot cache para 7 dias (padrão é 31 dias)
.alter table logs policy caching hot = 7d

// Para dados históricos que raramente são consultados:
.alter table historico policy caching hot = 1d

// Verificar política atual
.show table logs policy caching
```

### Retenção de Dados

```kusto
// Retenção com recoverability explícito (padrão recomendado)
.alter-merge table user_events policy retention
  softdelete = 365d recoverability = disabled

// Para tabelas de log de curta vida (30 dias)
.alter table audit_logs policy retention softdelete = 30d

// Verificar política de retenção
.show table user_events policy retention
```

### Tiering de Dados (Hot / Warm / Cold)

| Tier | Duração Típica | Latência de Query | Custo Relativo |
|------|----------------|-------------------|----------------|
| Hot  | 30–90 dias     | <1 s              | Normal         |
| Warm | 90–365 dias    | ~10 s             | Reduzido       |
| Cold | 365+ dias      | ~1 min            | Mínimo         |

---

## Eventstreams — Ingestão e Roteamento

### Fontes Suportadas

| Fonte          | Padrão                    | Nota                          |
|----------------|---------------------------|-------------------------------|
| Event Hub      | Connection string         | Azure nativo                  |
| Kafka          | Topic + Consumer Group    | Default em clouds             |
| IoT Hub        | Shared access policy      | Dispositivos IoT              |
| Event Grid     | Topic subscription        | Serverless                    |
| Cosmos DB      | Change Feed               | Eventos NoSQL                 |
| Custom Source  | HTTP POST / SDK           | APIs genéricas                |

### Padrão de Multi-Destino

```
EventHub "telemetria"
         │
    EVENTSTREAM
    ├── Destination 1: Eventhouse (KQL DB "telemetria_hot")  → análise RT
    ├── Destination 2: Lakehouse (tabela "bronze_telemetria") → histórico Delta
    └── Destination 3: Activator  → alertas automáticos
```

### Transformações Inline no Eventstream

O Eventstream suporta transformações sem código via interface visual:
- **Filter**: filtrar eventos por condição (ex: `level == "ERROR"`)
- **Aggregate**: agrupar por janela de tempo (tumbling/hopping/session windows)
- **Union**: combinar múltiplos streams
- **Expand**: expandir campos JSON aninhados
- **Group By**: agregar antes de enviar ao destino

### Ingestão via API (Custom Apps)

```python
# Python — envio de eventos para Eventstream via Event Hub SDK
from azure.eventhub import EventHubProducerClient, EventData
import json

producer = EventHubProducerClient.from_connection_string(
    conn_str="<EVENTSTREAM_CONNECTION_STRING>",
    eventhub_name="<EVENTSTREAM_NAME>"
)

with producer:
    event_data_batch = producer.create_batch()
    event_data_batch.add(EventData(json.dumps({
        "timestamp": "2026-01-15T10:30:00Z",
        "source": "api_orders",
        "level": "INFO",
        "message": "Order processed",
        "order_id": "ORD-12345",
        "amount": 150.00
    })))
    producer.send_batch(event_data_batch)
```

### Eventstream via REST API

```http
POST /workspaces/{workspace-id}/eventstreams
{
  "displayName": "user-events-stream",
  "type": "EventStream",
  "sources": [
    {
      "type": "EventHub",
      "connectionId": "{connection-id}",
      "eventHubName": "user-events",
      "consumerGroup": "$Default"
    }
  ],
  "destinations": [
    {
      "type": "Eventhouse",
      "eventhouseId": "{eventhouse-id}",
      "tableName": "user_events",
      "mappingType": "Json"
    }
  ]
}
```

---

## Eventhouse — Criação e Gerenciamento de Tabelas

```json
POST /workspaces/{workspace-id}/eventhouse/{eventhouse-id}/tables
{
  "tableName": "user_events",
  "schema": [
    {"columnName": "timestamp", "columnType": "datetime"},
    {"columnName": "user_id",   "columnType": "string"},
    {"columnName": "event_type","columnType": "string"},
    {"columnName": "value",     "columnType": "real"}
  ]
}
```

---

## Ingestão Direta via Python (kusto-ingest)

Para ingestão em lote fora do Eventstream (ex: backfill, scripts de carga):

```python
from azure.kusto.data import KustoConnectionStringBuilder
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties, DataFormat

kcsb = KustoConnectionStringBuilder.with_aad_application_key_authentication(
    connection_string="https://ingest-<cluster>.kusto.windows.net",
    aad_app_id="<app_id>",
    app_key="<app_key>",
    authority_id="<tenant_id>"
)

client = QueuedIngestClient(kcsb)

ingestion_props = IngestionProperties(
    database="<database>",
    table="<table_name>",
    data_format=DataFormat.JSON,
    ingestion_mapping_reference="json_mapping"
)

client.ingest_from_blob(
    "<blob_uri>?<sas_token>",
    ingestion_properties=ingestion_props
)
```

> Pacote: `azure-kusto-ingest` (substitui `kusto_client` descontinuado).

---

## Activator — Alertas e Automação

### Casos de Uso

| Condição                                   | Ação Configurável                           |
|--------------------------------------------|---------------------------------------------|
| Erros > 100 em 5 minutos                   | Alerta no Teams + email para on-call        |
| Latência P99 > 2000 ms                     | Webhook para PagerDuty / OpsGenie           |
| Pedido de alto valor recebido (> R$10 k)   | Notificação para equipe de vendas           |
| Sensor IoT fora do range                   | Disparo de Power Automate para manutenção   |
| Fraude detectada (score > 0.9)             | Bloqueio automático via API                 |
| Sem dados por 10 minutos (dead source)     | Alerta de ingestão parada                   |

### Tipos de Trigger no Activator

| Condição         | Exemplo                      | Resposta                    |
|------------------|------------------------------|-----------------------------|
| Threshold        | `count > 1000`               | Email SLA                   |
| Anomalia         | `stdev(value) > 3 * mean`    | Slack notification          |
| Dead source      | `count == 0 por 10 min`      | PagerDuty alert             |
| Degradação       | `latency > 5s`               | Dashboard highlight         |

### Configuração de Trigger via REST API

```http
POST /workspaces/{workspace-id}/activator/{activator-id}/triggers
{
  "displayName": "High Error Rate Alert",
  "query": "user_events | where event_type == 'error' | count",
  "condition": "count > 100",
  "timeWindow": "5m",
  "action": {
    "type": "Email",
    "recipients": ["ops@company.com"],
    "subject": "Error spike detected",
    "body": "Count: {result}"
  }
}
```

### Configuração de Trigger (formato JSON genérico)

```json
{
  "trigger_name": "high_error_rate_alert",
  "source": "eventstream/telemetria",
  "condition": {
    "field": "error_count_5m",
    "operator": "greater_than",
    "threshold": 100
  },
  "action": {
    "type": "send_teams_message",
    "channel": "oncall-alerts",
    "message": "ALERTA: Taxa de erros elevada ({error_count_5m} erros em 5 min)"
  },
  "cooldown_minutes": 15
}
```

---

## Troubleshooting — Comandos `.show`

```kusto
// Verificar falhas de ingestion
.show ingestion failures
| where Table == "user_events"
| order by FailedOn desc
| limit 10

// Tamanho total de uma tabela
.show table user_events extents
| summarize TotalSize = sum(ExtentSize)

// Listar todas as tabelas do database
.show tables

// Schema de uma tabela
.show table user_events columns

// Status de Materialized Views
.show materialized-views

// Verificar política de cache em vigor
.show table user_events policy caching

// Verificar operações de ingestion recentes
.show operations
| where Operation == "DataIngest"
| order by StartedOn desc
| limit 20
```

---

## Boas Práticas RTI

### KQL
- **Sempre filtre por tempo na primeira linha** — isso ativa predicate pushdown de partição temporal.
- Use `ingestion_time()` para filtros quando o campo de timestamp da payload for inconsistente.
- Prefira `summarize` a `extend + project` para agregações — é mais eficiente.
- Use `materialize()` para subqueries reutilizadas: `let t = materialize(tabela | where ...);`
- Limite `take` em vez de `limit` para desenvolvimento — `take` é mais rápido em Kusto.
- Use `dcount()` para contagem aproximada de distintos em alta cardinalidade (mais rápido que `count(distinct ...)`).
- Use `render timechart` em Fabric RTI Dashboards para visualizações de série temporal.
- KQL não suporta UPDATE/DELETE — use novo schema + materialized view para correções.

### Eventhouse
- Habilite **Always-On** apenas para Eventhouses de produção (reduz custo em dev/test).
- Configure caching policy por tabela — dados históricos não precisam de hot cache.
- Use **External Tables** para cruzar dados KQL com Delta do OneLake sem duplicar.
- Monitor consumption via `Fabric Capacity Metrics` — Eventhouse cobra por CU consumida.
- Crie **Materialized Views** para agregações recorrentes de alto custo (dashboards em tempo real).

### Eventstreams
- Um único Eventstream pode ter múltiplos destinos — use isso para fan-out sem duplicar fontes.
- Transformações inline reduzem volume enviado ao Eventhouse (filtros antes de persistir).
- Defina **schema explícito** no Eventstream para evitar inferência em tempo real.
- Para telemetria massiva, ajuste a Update Policy da tabela para controlar latência de batching.

---

## Checklist RTI

- [ ] Decision matrix Lakehouse vs Eventhouse aplicada
- [ ] Filtro temporal na primeira linha de todas as queries KQL
- [ ] Caching policy definida por tabela (hot vs cold)
- [ ] Retenção configurada explicitamente com `recoverability`
- [ ] Eventstream com schema explícito definido
- [ ] Eventstream com múltiplos destinos configurados (fan-out)
- [ ] Materialized Views criadas para agregações recorrentes
- [ ] Activator com cooldown para evitar flood de alertas
- [ ] `.show ingestion failures` monitorado via alerta
- [ ] External Tables configuradas para joins com OneLake (evitar duplicar dados)
- [ ] Biblioteca Python: usar `azure-kusto-ingest` (não `kusto_client`)

---

## Referências

- [Real-Time Intelligence overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/overview)
- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Eventstreams overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/overview)
- [KQL quick reference](https://learn.microsoft.com/en-us/azure/data-explorer/kql-quick-reference)
- [KQL language reference](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/)
- [Materialized views](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/management/materialized-views/materialized-view-overview)
- [Real-Time Intelligence consumption](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/real-time-intelligence-consumption)
- [Activator overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/data-activator/activator-introduction)
