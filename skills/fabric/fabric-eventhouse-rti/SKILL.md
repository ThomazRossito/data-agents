# SKILL: Microsoft Fabric — Real-Time Intelligence (Eventhouse, KQL, Eventstreams, Activator)

> **Fonte:** Microsoft Learn (learn.microsoft.com/fabric/real-time-intelligence)
> **Atualizado:** Janeiro 2026
> **Uso:** Leia este arquivo ANTES de projetar pipelines de dados em tempo real no Fabric.

---

## Componentes do Real-Time Intelligence (RTI)

```
Fontes de Eventos
  (Kafka, Event Hub, IoT Hub, APIs, Change Data)
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

### Eventhouse
Container para múltiplos **KQL Databases** (Kusto). Otimizado para dados de séries temporais, logs, telemetria. Dados são automaticamente indexados por tempo de ingestão. Suporta hot cache (memória) + cold storage (OneLake Parquet).

### Eventstreams
Pipeline de streaming sem código. Conecta fontes (Event Hub, Kafka, IoT Hub, Custom Apps) a múltiplos destinos simultaneamente (Eventhouse, Lakehouse, Activator). Suporta transformações inline (filter, aggregate, join).

### Activator
Motor de automação baseado em regras sobre dados em tempo real. Monitora Eventstreams ou Eventhouse e dispara ações (email, Teams, webhook, Power Automate) quando condições são atendidas.

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

### Agregações e Séries Temporais

```kusto
// Contagem por janela de 5 minutos (análise de séries temporais)
telemetria
| where ingestion_time() > ago(24h)
| summarize
    total_eventos = count(),
    erros = countif(level == "ERROR"),
    latencia_p99 = percentile(response_ms, 99)
    by bin(timestamp, 5m), endpoint
| order by timestamp desc
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
// Definir retenção total (hot + cold) de 365 dias
.alter table logs policy retention softdelete = 365d recoverability = disabled

// Para tabelas de log de curta vida (30 dias)
.alter table audit_logs policy retention softdelete = 30d
```

---

## Eventstreams — Ingestão e Roteamento

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

---

## Activator — Alertas e Automação

### Casos de Uso

| Condição                              | Ação Configurável                          |
|---------------------------------------|--------------------------------------------|
| Erros > 100 em 5 minutos              | Alerta no Teams + email para on-call       |
| Latência P99 > 2000ms                 | Webhook para PagerDuty / OpsGenie          |
| Pedido de alto valor recebido (> R$10k)| Notificação para equipe de vendas         |
| Sensor IoT fora do range              | Disparo de Power Automate para manutenção  |
| Fraude detectada (score > 0.9)        | Bloqueio automático via API                |

### Configuração de Trigger (via interface ou API)

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

## Boas Práticas RTI

### KQL
- **Sempre filtre por tempo na primeira linha** — isso ativa predicate pushdown de partição temporal.
- Use `ingestion_time()` para filtros quando o campo de timestamp da payload for inconsistente.
- Prefira `summarize` a `extend + project` para agregações — é mais eficiente.
- Use `materialize()` para subqueries reutilizadas: `let t = materialize(tabela | where ...);`
- Limite `take` em vez de `limit` para desenvolvimento — `take` é mais rápido em Kusto.

### Eventhouse
- Habilite **Always-On** apenas para Eventhouses de produção (reduz custo em dev/test).
- Configure caching policy por tabela — dados históricos não precisam de hot cache.
- Use **External Tables** para cruzar dados KQL com Delta do OneLake sem duplicar.
- Monitor consumption via `Fabric Capacity Metrics` — Eventhouse cobra por CU consumida.

### Eventstreams
- Um único Eventstream pode ter múltiplos destinos — use isso para fan-out sem duplicar fontes.
- Transformações inline reduzem volume enviado ao Eventhouse (filtros antes de persistir).
- Defina **schema explícito** no Eventstream para evitar inferência em tempo real.

---

## Checklist RTI

- [ ] Filtro temporal na primeira linha de todas as queries KQL
- [ ] Caching policy definida por tabela (hot vs cold)
- [ ] Retenção configurada explicitamente
- [ ] Eventstream com múltiplos destinos configurados
- [ ] Activator com cooldown para evitar flood de alertas
- [ ] Schema do evento documentado e aplicado no Eventstream
- [ ] External Tables configuradas para joins com OneLake (evitar duplicar dados)

---

## Referências

- [Eventhouse overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/eventhouse)
- [Eventstreams overview](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/event-streams/overview)
- [KQL quick reference](https://learn.microsoft.com/en-us/azure/data-explorer/kql-quick-reference)
- [Real-Time Intelligence consumption](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/real-time-intelligence-consumption)
