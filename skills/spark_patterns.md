# Skill: Padrões PySpark para Engenharia de Dados

## Leitura de CSV com Schema Explícito

```python
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, DateType

schema = StructType([
    StructField("id", StringType(), nullable=False),
    StructField("data", DateType(), nullable=True),
    StructField("valor", DoubleType(), nullable=True),
])

df = (
    spark.read
    .schema(schema)
    .option("header", "true")
    .option("sep", ";")
    .option("dateFormat", "yyyy-MM-dd")
    .csv("abfss://<container>@<storage>.dfs.core.windows.net/path/file.csv")
)
```

## Normalização de Nomes de Colunas

```python
import re, unicodedata

def normalize_col(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^a-zA-Z0-9]", "_", name.strip().lower())
    return re.sub(r"_+", "_", name).strip("_")

for col in df.columns:
    df = df.withColumnRenamed(col, normalize_col(col))
```

## Limpeza de Nulos

```python
from pyspark.sql import functions as F

df_clean = (
    df
    .na.drop(subset=["id", "data"])                    # Obrigatórios
    .fillna({"valor": 0.0, "descricao": "N/A"})       # Opcionais com default
    .filter(F.col("valor") >= 0)                       # Filtro de sanidade
)
```

## Write para Delta Lake (Databricks Unity Catalog)

```python
(
    df_clean
    .withColumn("_ingestion_timestamp", F.current_timestamp())
    .write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable("catalog.schema.table_name")
)

# Otimização pós-escrita
spark.sql("OPTIMIZE catalog.schema.table_name ZORDER BY (data)")
```

## MERGE (Upsert) — SCD Type 1

```python
from delta.tables import DeltaTable

delta_target = DeltaTable.forName(spark, "catalog.schema.target")

(
    delta_target.alias("target")
    .merge(
        df_updates.alias("src"),
        "target.id = src.id"
    )
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute()
)
```

## Spark Declarative Pipelines (Lakeflow/SDP) — API Moderna

> ⚠️ NUNCA use `import dlt` — É a API legada e DEPRECIADA.

```python
from pyspark import pipelines as dp

# --- Bronze: Auto Loader (cloudFiles) ---
@dp.table(name="bronze_vendas", comment="Bronze: dados brutos do CSV")
def bronze_vendas():
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load("/Volumes/catalog/schema/volume/vendas/")
    )

# --- Silver: STREAMING TABLE consumindo via stream() ---
@dp.table(name="silver_vendas", comment="Silver: dados limpos")
@dp.expect_or_drop("id_nao_nulo", "id IS NOT NULL")
@dp.expect("valor_positivo", "valor >= 0")
def silver_vendas():
    return (
        spark.readStream.table("bronze_vendas")
        .withColumn("valor", F.col("valor").cast("double"))
        .na.fill({"descricao": "N/A"})
    )

# --- Silver: SCD Type 2 via AUTO CDC (dp.create_auto_cdc_flow) ---
dp.create_streaming_table("silver_clientes_history")
dp.create_auto_cdc_flow(
    target="silver_clientes_history",
    source="bronze_clientes",
    keys=["cliente_id"],
    sequence_by="sequenceNum",
    stored_as_scd_type=2,
)

# --- Gold: MATERIALIZED VIEW para agregação ---
@dp.materialized_view(name="gold_vendas_diarias", comment="Gold: agregação por dia")
def gold_vendas_diarias():
    return (
        spark.read.table("silver_vendas")
        .groupBy("data")
        .agg(F.sum("valor").alias("total_vendas"))
    )
```

## Broadcast Join para Tabelas Pequenas

```python
from pyspark.sql.functions import broadcast

df_result = df_large.join(
    broadcast(df_small),
    on="id_produto",
    how="left"
)
```
