# ACID Transactions no Delta Lake

## As 4 propriedades
| Propriedade | Mecanismo no Delta |
|-------------|-------------------|
| **Atomicity** | Transaction Log (WAL) — toda operação ou commita tudo ou rollback tudo |
| **Consistency** | Schema enforcement + constraints + transaction log |
| **Isolation** | Snapshot Isolation — cada reader vê snapshot consistente |
| **Durability** | Transaction log persistido em storage durável (ADLS/S3/GCS) |

## Transaction Log (`_delta_log/`)
O coração do Delta Lake. É um WAL (Write-Ahead Log) com formato JSON + Parquet (checkpoints).

```
tabela/
├── _delta_log/
│   ├── 00000000000000000000.json   ← commit 0 (CREATE TABLE)
│   ├── 00000000000000000001.json   ← commit 1 (INSERT)
│   ├── 00000000000000000002.json   ← commit 2 (UPDATE via MERGE)
│   └── 00000000000000000010.checkpoint.parquet  ← checkpoint a cada 10 commits
└── part-00001-xxx.parquet
```

## Snapshot Isolation
```python
# Leitores veem snapshot no momento do início da query
# → Mesmo que um writer commit durante a leitura, o reader não vê a mudança

# Time Travel — ler histórico
df = spark.read.format("delta").option("versionAsOf", 5).load(path)
df = spark.read.format("delta").option("timestampAsOf", "2026-01-01").load(path)
```

## Concurrent Writes e Conflict Resolution
| Operação | Conflito se |
|----------|------------|
| INSERT | Raramente conflita |
| UPDATE / DELETE | Conflita se mesmas linhas modificadas concorrentemente |
| MERGE | Conflita se predicado ON casa com mesmas linhas |

Quando conflito é detectado, a segunda transação recebe `ConcurrentModificationException`.

## Schema Enforcement
```python
# Delta rejeita escrita com schema incompatível por padrão
df_wrong_schema.write.format("delta").mode("append").save(path)
# → AnalysisException: A schema mismatch detected...

# Schema evolution explícito
df_new_col.write.format("delta").option("mergeSchema", "true").mode("append").save(path)
```

## Checkpoints e VACUUM
```python
# Forçar checkpoint
delta_table.generate("symlink_format_manifest")

# Limpar arquivos antigos (não remove transaction log)
from delta.tables import DeltaTable
dt = DeltaTable.forPath(spark, path)
dt.vacuum(retentionHours=168)  # 7 dias (mínimo para Time Travel seguro)
```
