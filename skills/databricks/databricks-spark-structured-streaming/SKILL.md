---
name: databricks-spark-structured-streaming
description: "Comprehensive guide to Spark Structured Streaming for production workloads. Use when building streaming pipelines, working with Kafka ingestion, implementing Real-Time Mode (RTM), configuring triggers (processingTime, availableNow, realTime/RealTimeTrigger), handling stateful operations with watermarks, optimizing checkpoints, performing stream-stream or stream-static joins, writing to multiple sinks, or tuning streaming cost and performance."
updated_at: 2026-04-23
source: web_search
---

# Spark Structured Streaming

Production-ready streaming pipelines with Spark Structured Streaming. This skill provides navigation to detailed patterns and best practices.

## Quick Start

```python
from pyspark.sql.functions import col, from_json

# Basic Kafka to Delta streaming (micro-batch, classic compute)
df = (spark
    .readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "broker:9092")
    .option("subscribe", "topic")
    .load()
    .select(from_json(col("value").cast("string"), schema).alias("data"))
    .select("data.*")
)

df.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "/Volumes/catalog/checkpoints/stream") \
    .trigger(processingTime="30 seconds") \
    .start("/delta/target_table")
```

## Core Patterns

| Pattern | Description | Reference |
|---------|-------------|-----------|
| **Kafka Streaming** | Kafka to Delta, Kafka to Kafka, Real-Time Mode | See [kafka-streaming.md](kafka-streaming.md) |
| **Stream Joins** | Stream-stream joins, stream-static joins | See [stream-stream-joins.md](stream-stream-joins.md), [stream-static-joins.md](stream-static-joins.md) |
| **Multi-Sink Writes** | Write to multiple tables, parallel merges | See [multi-sink-writes.md](multi-sink-writes.md) |
| **Merge Operations** | MERGE performance, parallel merges, optimizations | See [merge-operations.md](merge-operations.md) |

## Configuration

| Topic | Description | Reference |
|-------|-------------|-----------|
| **Checkpoints** | Checkpoint management and best practices | See [checkpoint-best-practices.md](checkpoint-best-practices.md) |
| **Stateful Operations** | Watermarks, state stores, RocksDB configuration | See [stateful-operations.md](stateful-operations.md) |
| **Trigger & Cost** | Trigger selection, cost optimization, RTM | See [trigger-and-cost-optimization.md](trigger-and-cost-optimization.md) |

## Best Practices

| Topic | Description | Reference |
|-------|-------------|-----------|
| **Production Checklist** | Comprehensive best practices | See [streaming-best-practices.md](streaming-best-practices.md) |

---

## Triggers — Referência Rápida

> ⚠️ **Breaking change em DBR 11.3 LTS:** `Trigger.Once` está **deprecated**. Use `Trigger.AvailableNow` para todos os workloads de batch incremental.

> ⚠️ **Novo em DBR 16.4 LTS (GA em março/2026):** Real-Time Mode (RTM) com `RealTimeTrigger` / `.trigger(realTime="<intervalo>")`. Requer cluster **Dedicated**, sem autoscaling, sem Photon, e `spark.databricks.streaming.realTimeMode.enabled = true`.

### Tabela de triggers

| Trigger | Quando usar | Suporte Serverless | DBR mínimo |
|---------|-------------|-------------------|------------|
| `processingTime="N seconds"` | Streaming contínuo (micro-batch) | ❌ Não suportado | qualquer |
| `availableNow=True` | Batch incremental agendado | ✅ Recomendado | 11.3 LTS |
| `once=True` | _Deprecated_ — evite | ✅ Aceito (não recomendado) | qualquer |
| `realTime="N minutes"` (PySpark) / `RealTimeTrigger` (Scala) | Ultra-baixa latência (<1 s) — Kafka→Kafka, fraud detection | ❌ Não suportado | **16.4 LTS** |

### processingTime (micro-batch)

```python
df.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "/Volumes/catalog/checkpoints/stream") \
    .trigger(processingTime="30 seconds") \
    .start("/delta/target_table")
```

### availableNow (batch incremental — substitui Trigger.Once)

```python
# Processa todos os registros pendentes e encerra; seguro para jobs agendados
df.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "/Volumes/catalog/checkpoints/stream") \
    .trigger(availableNow=True) \
    .start("/delta/target_table")
```

### Real-Time Mode — RTM (GA desde março/2026, DBR ≥ 16.4 LTS)

> ⚠️ **Requisitos obrigatórios para RTM:**
> - DBR ≥ 16.4 LTS (recomendado: 18.1+)
> - Cluster **Dedicated** (não Standard, não serverless, não Lakeflow Pipelines)
> - Autoscaling **desativado**
> - Photon **desativado**
> - `spark.databricks.streaming.realTimeMode.enabled = true` no Spark config
> - `outputMode("update")` obrigatório

**PySpark:**
```python
# Em PySpark, o intervalo de checkpoint deve ser especificado explicitamente
query = (
    spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", broker_address)
        .option("subscribe", input_topic)
        .load()
    .writeStream
        .format("kafka")
        .option("kafka.bootstrap.servers", broker_address)
        .option("topic", output_topic)
        .option("checkpointLocation", checkpoint_location)
        .outputMode("update")
        .trigger(realTime="5 minutes")   # intervalo de checkpoint
        .start()
)
```

**Scala:**
```scala
import org.apache.spark.sql.execution.streaming.RealTimeTrigger

spark.readStream
  .format("kafka")
  .option("kafka.bootstrap.servers", brokerAddress)
  .option("subscribe", inputTopic)
  .load()
  .writeStream
  .format("kafka")
  .option("kafka.bootstrap.servers", brokerAddress)
  .option("topic", outputTopic)
  .option("checkpointLocation", checkpointLocation)
  .outputMode("update")
  .trigger(RealTimeTrigger.apply("5 minutes"))  // intervalo de checkpoint opcional
  .start()
```

**Por que RTM em vez de Continuous Processing?**
O modo *Continuous Processing* (experimental desde Spark 2.3) **não é suportado nem recomendado** pelo Databricks. Use RTM para casos de baixa latência — latência fim-a-fim típica em torno de 300 ms, mínima de 5 ms.

**RTM agora disponível também em Standard access mode** (além de Dedicated) em Python, a partir da GA em março/2026.

---

## Serverless Compute — Restrições de Trigger

> ⚠️ **Atenção ao usar serverless:** triggers contínuos (`processingTime`, `realTime`) não são suportados. Tentar usá-los lança `INFINITE_STREAMING_TRIGGER_NOT_SUPPORTED`.

- **Suportado:** `Trigger.AvailableNow()` (recomendado) e `Trigger.Once()` (deprecated, aceito)
- **Não suportado:** `processingTime`, `realTime`/`RealTimeTrigger`
- Para streaming contínuo em serverless, use **Lakeflow Spark Declarative Pipelines** em modo contínuo ou `AvailableNow` em *Run jobs continuously*.

```python
# Padrão correto para serverless
df.writeStream \
    .option("checkpointLocation", "/Volumes/catalog/checkpoints/stream") \
    .trigger(availableNow=True) \
    .toTable("catalog.schema.target_table")
```

---

## Kafka em Shared Access Mode

> ⚠️ **Novo (DBR 15.x+):** Em compute configurado com **shared access mode**, leituras e escritas batch do Kafka agora têm as **mesmas restrições** documentadas para Structured Streaming. Verifique [Streaming limitations](https://docs.databricks.com/aws/en/structured-streaming/stream-limitations.html) antes de migrar pipelines Kafka batch para shared mode.

---

## RocksDB State Store

```python
# Habilitar RocksDB como state store provider (recomendado para stateful ops)
spark.conf.set(
    "spark.sql.streaming.stateStore.providerClass",
    "com.databricks.sql.streaming.state.RocksDBStateStoreProvider"
)
```

A partir da manutenção de novembro/2025 (SPARK-53794), há nova opção para **limitar deleções por operação de manutenção** no RocksDB state provider — útil para controlar latência em state stores grandes.

---

## Production Checklist

- [ ] Checkpoint location é persistente (UC Volumes, **não** DBFS)
- [ ] Checkpoint único por stream
- [ ] Cluster de tamanho fixo (sem autoscaling para streaming micro-batch e RTM)
- [ ] Monitoramento configurado (input rate, lag, batch duration)
- [ ] Exactly-once verificado (txnVersion/txnAppId)
- [ ] Watermark configurado para operações stateful
- [ ] Left joins para stream-static (não inner)
- [ ] `Trigger.Once` substituído por `Trigger.AvailableNow` (deprecated desde DBR 11.3 LTS)
- [ ] RTM: Photon desativado, autoscaling desativado, `realTimeMode.enabled = true`, `outputMode("update")`
- [ ] Serverless: usar apenas `AvailableNow`; não usar `processingTime` ou `realTime`
- [ ] Kafka em shared access mode: revisar restrições de Structured Streaming antes de usar
