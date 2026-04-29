# KB: Spark — Delta Lake Patterns

## MERGE INTO (upsert idempotente)

```python
from delta.tables import DeltaTable

delta_table = DeltaTable.forName(spark, "catalog.schema.slv_customers")

delta_table.alias("target").merge(
    source=df_updates.alias("source"),
    condition="target.customer_id = source.customer_id"
).whenMatchedUpdateAll(
    condition="source.updated_ts > target.updated_ts"
).whenNotMatchedInsertAll().execute()
```

## Time Travel

```python
# Ler versão anterior
df = spark.read.format("delta").option("versionAsOf", 5).table("catalog.schema.raw_orders")

# Ler por timestamp
df = spark.read.format("delta").option("timestampAsOf", "2024-01-01").table("catalog.schema.raw_orders")

# Restaurar tabela para versão anterior
delta_table.restoreToVersion(5)
```

## Schema Evolution

```python
# Habilitar merge schema
df.write.format("delta") \
    .option("mergeSchema", "true") \
    .mode("append") \
    .saveAsTable("catalog.schema.raw_events")
```

## VACUUM e OPTIMIZE

```python
# Remover arquivos obsoletos (manter 7 dias de histórico)
spark.sql("VACUUM catalog.schema.raw_orders RETAIN 168 HOURS")

# Compactar small files + Z-ORDER
spark.sql("""
  OPTIMIZE catalog.schema.slv_orders
  ZORDER BY (customer_id, order_date)
""")
```

## Change Data Feed (CDF)

```python
# Habilitar CDF na tabela
spark.sql("""
  ALTER TABLE catalog.schema.slv_customers
  SET TBLPROPERTIES (delta.enableChangeDataFeed = true)
""")

# Ler mudanças incrementais
df_changes = spark.read.format("delta") \
    .option("readChangeFeed", "true") \
    .option("startingVersion", 0) \
    .table("catalog.schema.slv_customers")
```

## Regras

- `VACUUM` nunca com `RETAIN 0 HOURS` em produção (quebra time travel)
- `mergeSchema` habilitar apenas em ambientes controlados — pode esconder bugs
- CDF é pré-requisito para pipelines de streaming incremental downstream
- `OPTIMIZE` deve rodar fora dos horários de pico (job agendado, não inline)
