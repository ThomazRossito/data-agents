# KB: Data Quality — Expectations

## Padrões de Validação

### 1. Null Check

```python
from pyspark.sql import functions as F

def check_not_null(df, columns: list[str], table_name: str) -> None:
    for col in columns:
        null_count = df.filter(F.col(col).isNull()).count()
        if null_count > 0:
            raise ValueError(
                f"[DQ] {table_name}.{col}: {null_count} nulls encontrados"
            )
```

### 2. Schema Validation

```python
from pyspark.sql.types import StructType

def validate_schema(df, expected: StructType, table_name: str) -> None:
    actual_fields = {f.name: str(f.dataType) for f in df.schema.fields}
    expected_fields = {f.name: str(f.dataType) for f in expected.fields}

    missing = set(expected_fields) - set(actual_fields)
    mismatched = {
        col for col in expected_fields
        if col in actual_fields and actual_fields[col] != expected_fields[col]
    }

    if missing or mismatched:
        raise ValueError(
            f"[DQ] {table_name}: schema inválido. "
            f"Faltando: {missing}, tipo errado: {mismatched}"
        )
```

### 3. Referential Integrity

```python
def check_referential_integrity(
    df_child: "DataFrame",
    df_parent: "DataFrame",
    fk_col: str,
    pk_col: str,
    table_name: str,
) -> None:
    orphans = (
        df_child
        .join(df_parent, df_child[fk_col] == df_parent[pk_col], "left_anti")
        .count()
    )
    if orphans > 0:
        raise ValueError(
            f"[DQ] {table_name}.{fk_col}: {orphans} registros órfãos"
        )
```

### 4. Freshness Check

```python
from datetime import datetime, timedelta

def check_freshness(df, ts_col: str, max_lag_hours: int, table_name: str) -> None:
    max_ts = df.agg(F.max(ts_col)).collect()[0][0]
    if max_ts is None:
        raise ValueError(f"[DQ] {table_name}: tabela vazia")

    lag = datetime.utcnow() - max_ts.replace(tzinfo=None)
    if lag > timedelta(hours=max_lag_hours):
        raise ValueError(
            f"[DQ] {table_name}: dado desatualizado "
            f"(último registro: {max_ts}, lag: {lag})"
        )
```

### 5. Duplicate Check

```python
def check_no_duplicates(df, key_cols: list[str], table_name: str) -> None:
    total = df.count()
    distinct = df.select(*key_cols).distinct().count()
    if total != distinct:
        raise ValueError(
            f"[DQ] {table_name}: {total - distinct} duplicatas nas chaves {key_cols}"
        )
```

## Regras

- Expectations críticas (nulls em PKs, schema) devem **lançar exceção** — não apenas logar
- Expectations de aviso (freshness, duplicatas em staging) — logar e continuar
- Executar DQ **antes** de promover para a próxima camada
- Guardar métricas de DQ em tabela de auditoria para trending
