# Padrão: Integration Tests com Databricks

## Contexto

Testes que precisam de Delta Lake real, Unity Catalog, DLT ou outros recursos Databricks. Usam Databricks Connect quando disponível; fallback para SparkSession local em CI offline.

## Solução

```python
# conftest.py — Databricks Connect ou local por variável de ambiente
import os

import pytest
from pyspark.sql import SparkSession


def _is_databricks_connect() -> bool:
    return bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN"))


@pytest.fixture(scope="session")
def spark():
    if _is_databricks_connect():
        from databricks.connect import DatabricksSession
        return DatabricksSession.builder.getOrCreate()
    return (
        SparkSession.builder
        .master("local[1]")
        .appName("integration-tests-local")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )


# test_delta.py — testa MERGE real (só executa em CI com Databricks Connect)
import pytest


@pytest.mark.integration
def test_merge_upsert(spark, tmp_path):
    target_path = str(tmp_path / "target")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS delta.`{target_path}` (
            id INT NOT NULL,
            val STRING
        ) USING DELTA
    """)
    spark.sql(f"INSERT INTO delta.`{target_path}` VALUES (1, 'original')")

    spark.sql(f"""
        MERGE INTO delta.`{target_path}` AS t
        USING (SELECT 1 AS id, 'updated' AS val) AS s
        ON t.id = s.id
        WHEN MATCHED THEN UPDATE SET val = s.val
        WHEN NOT MATCHED THEN INSERT *
    """)

    result = spark.sql(f"SELECT val FROM delta.`{target_path}` WHERE id = 1")
    assert result.collect()[0]["val"] == "updated"
```

## Tradeoffs

| Vantagem | Desvantagem |
|----------|------------|
| Testa Delta MERGE, schema, RLS real | Requer Databricks Connect ou cluster |
| Detecta regressões de plataforma | Lento (5–30s por test) |
| Ambiente idêntico à produção | Custo de DBU em CI |

## Related

- [spark-unit-tests.md](spark-unit-tests.md)
- [../specs/test-config.yaml](../specs/test-config.yaml)
