# Skill: Qualidade e Validação de Dados

## Validações Básicas com PySpark

```python
from pyspark.sql import DataFrame, functions as F
from pyspark.sql.types import StructType

def validate_dataframe(df: DataFrame, required_cols: list[str]) -> dict:
    """Executa checagens de qualidade e retorna relatório."""
    total = df.count()
    report = {"total_rows": total, "issues": []}

    # 1. Verificar colunas obrigatórias
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        report["issues"].append(f"Colunas faltando: {missing}")

    # 2. Nulos em colunas obrigatórias
    for col in required_cols:
        if col in df.columns:
            null_count = df.filter(F.col(col).isNull()).count()
            if null_count > 0:
                pct = round(null_count / total * 100, 2)
                report["issues"].append(f"'{col}': {null_count} nulos ({pct}%)")

    # 3. Duplicatas
    dup_count = total - df.dropDuplicates().count()
    if dup_count > 0:
        report["issues"].append(f"Duplicatas: {dup_count}")

    report["passed"] = len(report["issues"]) == 0
    return report
```

## Expectations no DLT (Spark Declarative Pipelines)

```python
import dlt

@dlt.table
@dlt.expect("id_nao_nulo",    "id IS NOT NULL")
@dlt.expect("valor_positivo", "valor >= 0")
@dlt.expect_or_drop("data_valida", "data_evento IS NOT NULL")
@dlt.expect_all({
    "categoria_valida": "categoria IN ('A', 'B', 'C')",
    "quantidade_positiva": "quantidade > 0"
})
def silver_vendas():
    return dlt.read_stream("bronze_vendas")
```

## Reconciliação Fonte × Destino

```sql
-- Verificar contagem e soma após carga
SELECT
    'fonte'   AS origem, COUNT(*) AS total, SUM(valor) AS soma_valor
FROM staging.vendas_raw
UNION ALL
SELECT
    'destino' AS origem, COUNT(*) AS total, SUM(valor) AS soma_valor
FROM catalog.schema.vendas_final;
```
