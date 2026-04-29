# Real-Time Intelligence no Fabric

## Componentes
| Componente | Função |
|-----------|--------|
| **Eventstream** | Captura, transforma e roteia eventos em tempo real |
| **KQL Database** | Storage + query de dados de série temporal (Kusto) |
| **Activator** | Trigger de ações baseado em condições de dados |
| **Real-Time Dashboard** | Visualização KQL em tempo real |

## Eventstream
- Fonte: Event Hub, IoT Hub, CDC Kafka, Change Event Streaming (GA abr/2026), Custom
- Destino: KQL Database, Lakehouse, OneLake, outro Eventstream
- Suporta transformações em stream: filter, aggregate, join

```
Fonte → [Eventstream] → KQL DB
                     → Lakehouse (Delta)
                     → Activator (alertas)
```

## Change Event Streaming (GA Abril/2026)
Captura mudanças em tabelas Lakehouse/Warehouse diretamente como eventos — CDC nativo do Fabric.
- Nenhuma infra externa necessária (sem Kafka, sem Debezium)
- Latência: segundos
- Use para: replicação em tempo real, event-driven pipelines

## KQL Database — Padrões
```kql
// Query básica — últimas 1h
MyTable
| where ingestion_time() > ago(1h)
| summarize count() by bin(timestamp, 5m)

// Join com dimensão estática
MyEvents
| join kind=leftkey DimDevice on device_id
| project timestamp, device_name, value
```

## Activator — Triggers
Activator dispara ações quando condições são atendidas em tempo real:
- **Condições**: valor > threshold, ausência de evento, mudança de estado
- **Ações**: Teams alert, Logic App, Power Automate, Fabric pipeline

```
KQL DB / Eventstream → Activator → Teams / Email / Pipeline
```

## Quando Usar RTI vs Batch
| Cenário | Usar |
|---------|------|
| Alertas em < 30s | Eventstream + Activator |
| Dashboard realtime | Eventstream → KQL DB |
| CDC para replicação | Change Event Streaming |
| Analytics histórico | Batch Lakehouse |
| ML scoring | Batch ou near-realtime |
