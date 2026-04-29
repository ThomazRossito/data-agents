# Pipeline Design Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## Responsabilidades por Camada Medalhão

| Camada | Input | Transformações permitidas | Rejeição |
|--------|-------|--------------------------|---------|
| Bronze (`brz_`) | Raw externo | Nenhuma além de tipo e timestamp de ingestão | Quarentena |
| Silver (`slv_`) | Bronze | Dedup, cast, join, limpeza, validação | Dead letter |
| Gold (`gld_`) | Silver | Regras de negócio, KPIs, agregações | Não rejeita |
| Mart (`mrt_`) | Gold | Pivots, formatação BI, serving | Não rejeita |

## Idempotência

| Técnica | Quando usar | Código-chave |
|---------|-------------|-------------|
| MERGE INTO | SCD Tipo 1/2, upsert | `WHEN MATCHED THEN UPDATE` |
| `availableNow` trigger | Streaming incremental | `trigger(availableNow=True)` |
| Checkpoint + watermark | Streaming contínuo | `checkpointLocation` obrigatório |
| `replaceWhere` | Particionamento por data, backfill | `.option("replaceWhere", "data_date=...")` |

## Retry / Error Handling

| Configuração | Valor recomendado | Risco se omitir |
|-------------|------------------|----------------|
| `max_retries` | 2–3 | Falhas transitórias não recuperadas |
| `retry_on_timeout` | true | Timeout de rede descartado silenciosamente |
| `on_failure_callback` | Notificação + alerta | Falha silenciosa sem visibilidade |
| Dead letter path | Definido por pipeline | Perda de registros inválidos |
| Timeout por task | 30–120 min | Job travado indefinidamente |

## Decision Matrix

| Use Case | Padrão |
|----------|--------|
| Ingestão incremental diária | `availableNow` trigger + MERGE |
| Streaming near-realtime | readStream + watermark + checkpoint |
| Backfill histórico | Partition replace (`replaceWhere`) |
| Migração cross-cloud | pipeline_architect + DABs |
| Orquestração multi-step | Databricks Workflows (DAG de tarefas) |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| `INSERT OVERWRITE` em Silver | MERGE INTO com chave natural |
| Schema inference em Bronze | Schema explícito no DDL |
| Sem retry em jobs externos | `max_retries` + `timeout` configurados |
| Lógica de negócio em Bronze | Subir para Silver ou Gold |
| Pipeline sem observabilidade | Métricas + alertas por camada |

## Related

| Tópico | Arquivo |
|--------|---------|
| Medalhão detalhado | medallion-pattern.md |
| Idempotência (código) | idempotency.md |
| Error handling e DLQ | error-handling.md |
