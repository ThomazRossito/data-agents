# pandas e polars — Padrões e Performance

## Quando Usar Cada Um

| Critério | pandas | polars |
|----------|--------|--------|
| Dataset < 1M rows | ✅ | ✅ |
| Dataset > 10M rows | ⚠️ (use chunking) | ✅ preferível |
| Ecossistema ML (sklearn, etc.) | ✅ nativo | ✅ via `.to_pandas()` |
| Performance pura | ⚠️ | ✅ (lazy, paralelo) |
| Código existente em pandas | ✅ | migrar gradualmente |

## pandas — Padrões Essenciais

```python
import pandas as pd

# Dtypes explícitos ao ler — evita inferência cara
df = pd.read_csv("file.csv", dtype={"id": "int32", "valor": "float32"})

# Prefer vectorized ops sobre apply
df["total"] = df["preco"] * df["qtd"]           # ✅
df["total"] = df.apply(lambda r: r.preco * r.qtd, axis=1)  # ❌ lento

# query() para filtros legíveis
resultado = df.query("status == 'ativo' and valor > 100")

# Cuidado com chained indexing
df.loc[df["status"] == "ativo", "score"] = 1.0  # ✅
df[df["status"] == "ativo"]["score"] = 1.0       # ❌ SettingWithCopyWarning

# Tipos categoricos para colunas de baixa cardinalidade
df["status"] = df["status"].astype("category")  # economiza memória

# Chunking para arquivos grandes
for chunk in pd.read_csv("big.csv", chunksize=100_000):
    process(chunk)
```

## polars — Padrões Essenciais

```python
import polars as pl

# Lazy API para pipelines otimizados automaticamente
resultado = (
    pl.scan_csv("file.csv")          # lazy
    .filter(pl.col("status") == "ativo")
    .select(["id", "nome", "valor"])
    .with_columns((pl.col("valor") * 1.1).alias("valor_ajustado"))
    .collect()                        # executa o plano
)

# Expressões em vez de apply
df.with_columns(
    pl.when(pl.col("idade") >= 18)
    .then(pl.lit("adulto"))
    .otherwise(pl.lit("menor"))
    .alias("categoria")
)

# Group by eficiente
resumo = df.group_by("categoria").agg(
    pl.col("valor").sum().alias("total"),
    pl.col("id").count().alias("contagem"),
)

# Joins tipados
resultado = df_left.join(df_right, on="id", how="left")
```

## Conversão pandas ↔ polars

```python
# polars → pandas
df_pandas = df_polars.to_pandas()

# pandas → polars
df_polars = pl.from_pandas(df_pandas)
```

## Anti-padrões

- ❌ `iterrows()` — use `.apply()` ou melhor: operações vetorizadas
- ❌ `df = df.append(row, ...)` — use `pd.concat` ou construa lista e converta
- ❌ `inplace=True` em pandas — cria confusão; atribua explicitamente
- ❌ `df.values` para acesso numpy — use `df.to_numpy()`
