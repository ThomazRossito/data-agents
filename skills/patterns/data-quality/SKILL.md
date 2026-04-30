---
name: data-quality
description: "Padrões de validação e qualidade de dados em pipelines PySpark/Delta — null checks, duplicatas, expectations do Lakeflow/SDP (dp.expect) e reconciliação fonte × destino. Use ao desenhar validações em camada Silver ou gates de qualidade pós-ingestão."
---

# Skill: Qualidade e Validação de Dados

<!-- type: example -->
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

<!-- type: constraint -->
## Expectations no Lakeflow/SDP (Spark Declarative Pipelines)

> ⚠️ NUNCA use `import dlt` — API DEPRECIADA. Use `from pyspark import pipelines as dp`.

<!-- type: pattern -->
### Python (API Moderna)
```python
from pyspark import pipelines as dp

@dp.table(name="silver_vendas")
@dp.expect("id_nao_nulo",    "id IS NOT NULL")
@dp.expect("valor_positivo", "valor >= 0")
@dp.expect_or_drop("data_valida", "data_evento IS NOT NULL")
@dp.expect_all({
    "categoria_valida": "categoria IN ('A', 'B', 'C')",
    "quantidade_positiva": "quantidade > 0"
})
def silver_vendas():
    return spark.readStream.table("bronze_vendas")
```

<!-- type: pattern -->
### SQL (Constraints nativos)
```sql
CREATE OR REFRESH STREAMING TABLE silver_vendas (
  CONSTRAINT id_nao_nulo EXPECT (id IS NOT NULL) ON VIOLATION FAIL UPDATE,
  CONSTRAINT valor_positivo EXPECT (valor >= 0) ON VIOLATION DROP ROW,
  CONSTRAINT data_valida EXPECT (data_evento IS NOT NULL) ON VIOLATION DROP ROW
)
AS SELECT * FROM stream(bronze_vendas);
```

<!-- type: example -->
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
