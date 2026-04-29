# Spark Patterns Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## Delta Lake Operations

| Operação | Sintaxe | Quando usar |
|----------|---------|------------|
| Upsert | `MERGE INTO target t USING source s ON ...` | SCD Tipo 1 e 2, deduplication |
| Vacuum | `VACUUM table RETAIN 168 HOURS` | Remover arquivos antigos após OPTIMIZE |
| Optimize | `OPTIMIZE table [ZORDER BY col]` | Após bulk inserts; semanal em prod |
| Liquid Clustering | `CLUSTER BY (col)` no DDL | Novas tabelas > 1 GB — preferir a ZORDER |
| Time travel | `SELECT * FROM table TIMESTAMP AS OF '...'` | Auditoria, rollback, comparação |
| Schema evolution | `.option("mergeSchema", "true")` | Adicionar colunas sem recriar tabela |

## Structured Streaming

| Configuração | Valor recomendado | Risco se omitir |
|-------------|------------------|-----------------|
| `checkpointLocation` | caminho em objeto storage | job reinicia do zero |
| `trigger(availableNow=True)` | batch incremental | streaming contínuo desnecessário |
| `watermark` | ≤ late arrival tolerance | OOM por estado ilimitado |
| `outputMode` | append / update / complete | dados duplicados ou incompletos |

## Particionamento

| Tamanho tabela | Estratégia | Coluna típica |
|---------------|-----------|--------------|
| < 1 GB | Sem partição | — |
| 1–100 GB | Liquid Clustering | data_date, region |
| > 100 GB | Partition + Liquid Clustering | data_date |
| Streaming | Partition por data de ingestão | ingest_date |

## Decision Matrix

| Use Case | Abordagem |
|----------|-----------|
| Ingestão com duplicatas | MERGE com chave natural |
| SCD Tipo 2 | MERGE com is_current + valid_to |
| Bronze → Silver | DLT / readStream → writeStream com checkpoint |
| Backfill histórico | `trigger(availableNow=True)` |
| Join com tabela pequena | `broadcast()` explícito < 10 MB |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| `.collect()` em DataFrames > 1M linhas | `.show()` ou `.write` ou `.toPandas()` com limit |
| `ZORDER` em tabelas novas | `CLUSTER BY` (Liquid Clustering) |
| Schema inference em CSV externo | Schema explícito no DDL |
| `INSERT OVERWRITE` para SCD | `MERGE INTO` |
| Sem `.coalesce()` antes de write pequeno | `.coalesce(1)` para arquivos únicos de export |

## Related

| Tópico | Arquivo |
|--------|---------|
| MERGE patterns | delta-lake.md |
| Streaming checkpoints | structured-streaming.md |
| Bronze→Silver pipeline | medallion-pipeline.md |
| Broadcast, AQE | performance.md |
