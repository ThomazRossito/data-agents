# Padrões de I/O e Processamento de Dados (sem Spark)

## Mapa de Decisão — Qual Biblioteca Usar

| Tamanho | Operação | Biblioteca |
|---------|----------|------------|
| < 500MB | Tabulares em memória, manipulação pandas-style | pandas |
| > 500MB | Lazy evaluation, sem carregar tudo em RAM | polars lazy API |
| Qualquer | SQL sobre arquivos locais/cloud | duckdb |
| Qualquer | I/O Parquet/Feather com schema enforcement | pyarrow |
| Qualquer | Abstração de filesystem (S3, ADLS, GCS, local) | fsspec |

## pandas — Padrões Eficientes

```python
import pandas as pd
from pathlib import Path

# Leitura com dtype explícito evita inferência cara
df = pd.read_parquet(
    "data/events.parquet",
    columns=["id", "event_type", "ts"],  # pushdown de colunas
    filters=[("ts", ">=", "2024-01-01")],  # pushdown de predicado
)

# Evitar iterrows — usar vetorização
# ❌
for _, row in df.iterrows():
    df.loc[row.name, "value"] = row["a"] * row["b"]

# ✅
df["value"] = df["a"] * df["b"]

# Groupby + agg eficiente
summary = (
    df.groupby("event_type", sort=False)
    .agg(count=("id", "count"), avg_duration=("duration", "mean"))
    .reset_index()
)

# Leitura de múltiplos arquivos
df = pd.concat(
    [pd.read_parquet(p) for p in Path("data/").glob("*.parquet")],
    ignore_index=True,
)
```

## polars — Lazy API para Grandes Volumes

```python
import polars as pl

# Lazy scan — não carrega em memória até collect()
lf = (
    pl.scan_parquet("data/events/**/*.parquet")
    .filter(pl.col("ts") >= "2024-01-01")
    .select(["id", "event_type", "ts", "duration"])
    .with_columns(
        pl.col("duration").cast(pl.Float64),
        pl.col("ts").str.to_datetime(),
    )
    .group_by("event_type")
    .agg(
        pl.count("id").alias("count"),
        pl.mean("duration").alias("avg_duration"),
    )
)

df = lf.collect()  # executa o plano otimizado

# Streaming para arquivos que não cabem em RAM
df = lf.collect(streaming=True)
```

## duckdb — SQL In-Process sobre Arquivos

```python
import duckdb

# Query direta sobre Parquet — sem carregar em memória
conn = duckdb.connect()

result = conn.execute("""
    SELECT
        event_type,
        COUNT(*) AS count,
        AVG(duration) AS avg_duration
    FROM read_parquet('data/events/**/*.parquet')
    WHERE ts >= '2024-01-01'
    GROUP BY event_type
    ORDER BY count DESC
""").df()  # retorna pandas DataFrame

# Integração com pandas
import pandas as pd
df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
conn.execute("SELECT * FROM df WHERE a > 1").df()

# Leitura de S3 (requer httpfs)
conn.execute("INSTALL httpfs; LOAD httpfs;")
conn.execute("SET s3_region='us-east-1';")
result = conn.execute("SELECT * FROM read_parquet('s3://bucket/key.parquet')").df()
```

## pyarrow — Schema Enforcement e I/O de Parquet

```python
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds

# Schema explícito — falha rápido se dados não conformam
schema = pa.schema([
    pa.field("id", pa.int64(), nullable=False),
    pa.field("name", pa.string()),
    pa.field("ts", pa.timestamp("us", tz="UTC")),
    pa.field("value", pa.float64()),
])

# Escrita com schema
table = pa.Table.from_pydict(data, schema=schema)
pq.write_table(table, "output.parquet", compression="snappy")

# Leitura de dataset particionado
dataset = ds.dataset("data/events/", partitioning="hive")
table = dataset.to_table(
    columns=["id", "ts"],
    filter=ds.field("event_type") == "click",
)
```

## fsspec — Abstração de Filesystem

```python
import fsspec

# Abertura transparente de arquivo em qualquer storage
with fsspec.open("s3://bucket/data.parquet", "rb") as f:
    table = pq.read_table(f)

with fsspec.open("abfss://container@account.dfs.core.windows.net/file.json", "r") as f:
    data = json.load(f)

# Glob em S3
fs = fsspec.filesystem("s3", anon=False)
files = fs.glob("s3://bucket/data/**/*.parquet")
```

## boto3 — AWS S3

```python
import boto3
from botocore.exceptions import ClientError

s3 = boto3.client("s3")

def upload_file(local_path: str, bucket: str, key: str) -> None:
    s3.upload_file(local_path, bucket, key)

def download_bytes(bucket: str, key: str) -> bytes:
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise FileNotFoundError(f"s3://{bucket}/{key}") from e
        raise
```

## Anti-Padrões

```python
# ❌ Ler arquivo inteiro em memória para filtrar
df = pd.read_parquet("huge.parquet")  # 10GB em RAM
df = df[df["country"] == "BR"]

# ✅ Pushdown de predicado
df = pd.read_parquet("huge.parquet", filters=[("country", "==", "BR")])
# ou duckdb/polars lazy

# ❌ pickle para persistência cross-process ou cross-versão
with open("data.pkl", "wb") as f:
    pickle.dump(df, f)

# ✅ Parquet com schema explícito
pq.write_table(pa.Table.from_pandas(df), "data.parquet")

# ❌ CSV para dados de produção com tipos variados
df.to_csv("output.csv")  # perde tipos, datas viram strings

# ✅ Parquet ou Delta para pipelines
pq.write_table(table, "output.parquet")
```
