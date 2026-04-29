# Padrão: Spark Unit Tests

## Contexto

Testar transformações PySpark sem depender de cluster Databricks. A SparkSession local (`local[1]`) simula o comportamento do cluster para lógica pura de transformação.

## Solução

```python
# conftest.py — session-scoped: uma SparkSession por run de testes
import pytest
from pyspark.sql import SparkSession


@pytest.fixture(scope="session")
def spark():
    return (
        SparkSession.builder
        .master("local[1]")
        .appName("unit-tests")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )


# test_transformations.py
import pytest
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

SCHEMA = StructType([
    StructField("id", IntegerType(), nullable=False),
    StructField("name", StringType(), nullable=True),
])


@pytest.fixture
def sample_df(spark):
    return spark.createDataFrame([(1, "Alice"), (2, None), (3, "Bob")], schema=SCHEMA)


def test_no_nulls_after_filter(sample_df):
    result = sample_df.filter(F.col("name").isNotNull())
    assert result.count() == 2
    assert result.filter(F.col("name").isNull()).count() == 0


@pytest.mark.parametrize("input_data,expected_count", [
    ([(1, "Alice"), (1, "Alice")], 1),  # duplicatas
    ([(1, "Alice"), (2, "Bob")],   2),  # sem duplicatas
    ([],                            0),  # vazio
])
def test_dedup(spark, input_data, expected_count):
    df = spark.createDataFrame(input_data, schema=SCHEMA)
    result = df.dropDuplicates(["id"])
    assert result.count() == expected_count
```

## Tradeoffs

| Vantagem | Desvantagem |
|----------|------------|
| Rápido (sem cluster) | Não testa Delta MERGE, DLT, Unity Catalog real |
| Sem custo de DBU | Pequenas diferenças de comportamento vs cluster |
| Integra com qualquer CI/CD | SparkSession setup pode levar 3–8s |

## Related

- [integration-tests.md](integration-tests.md)
- [../specs/test-config.yaml](../specs/test-config.yaml)
