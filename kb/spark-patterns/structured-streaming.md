# KB: Spark — Structured Streaming

## Pipeline Incremental Básico

```python
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

schema = StructType([
    StructField("event_id",   StringType(),    False),
    StructField("event_type", StringType(),    False),
    StructField("payload",    StringType(),    True),
    StructField("event_ts",  TimestampType(), False),
])

# Leitura incremental de tabela Delta
df_stream = (
    spark.readStream
    .format("delta")
    .option("maxFilesPerTrigger", 1000)
    .table("catalog.bronze.raw_events")
)

# Transformação
df_clean = (
    df_stream
    .filter(F.col("event_type").isNotNull())
    .withColumn("event_date", F.to_date("event_ts"))
    .withColumn("processed_ts", F.current_timestamp())
)

# Escrita incremental com checkpoint
query = (
    df_clean.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/mnt/checkpoints/events_silver")
    .trigger(availableNow=True)          # processa tudo disponível e para
    .toTable("catalog.silver.slv_events")
)
query.awaitTermination()
```

## Watermark para Late Data

```python
df_with_watermark = (
    df_stream
    .withWatermark("event_ts", "2 hours")   # tolera até 2h de atraso
    .groupBy(
        F.window("event_ts", "1 hour"),
        "event_type"
    )
    .agg(F.count("*").alias("event_count"))
)
```

## Trigger Modes

```python
# Micro-batch contínuo (baixa latência)
.trigger(processingTime="30 seconds")

# Processa tudo disponível e para (batch incremental agendado)
.trigger(availableNow=True)

# Uma vez (deprecated — use availableNow)
.trigger(once=True)
```

## Monitoramento

```python
# Métricas do stream
query = df.writeStream.start()
print(query.lastProgress)   # batch mais recente
print(query.status)         # estado atual
```

## Regras

- `checkpointLocation` **obrigatório** — sem isso o stream não é fault-tolerant
- `trigger(availableNow=True)` preferível a `once=True` (mais robusto)
- Watermark obrigatório em aggregations com dados externos (Kafka, Event Hub)
- `maxFilesPerTrigger` para controlar throughput em ingestão de arquivos
- Nunca usar `.collect()` em transformações de streaming
