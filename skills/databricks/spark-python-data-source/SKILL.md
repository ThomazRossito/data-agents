---
name: spark-python-data-source
updated_at: 2026-04-23
source: web_search
---

# spark-python-data-source

Build custom Python data sources for Apache Spark 4.0+ to read from and write to external systems in batch and streaming modes.

> ⚠️ **Novidades em Spark 4.1 / DBR 16.4 LTS (maio 2025):**
> - `DataSourceReader.pushFilters()` — filter pushdown para batch reads (veja seção [Filter Pushdown](#filter-pushdown-spark-41--dbr-164-lts)).
> - `SimpleDataSourceStreamReader` é agora a alternativa oficial para fontes de streaming de baixo throughput (sem particionamento).
> - Arrow Batch yield (`pyarrow.RecordBatch`) no `read()` oferece ganhos de até ~10× sobre tuplas (disponível desde Spark 4.0, mas agora documentado como padrão recomendado para alta performance).
> - PySpark 4.x exige **Python ≥ 3.10**. Python 3.8 e 3.9 não são mais suportados.
> - Databricks Runtime mínimo para a API: **DBR 15.4 LTS** (ou serverless environment v2). Spark 4.1 é incluído a partir do **DBR 18.0**.

## Instructions

You are an experienced Spark developer building custom Python data sources using the PySpark DataSource API. Follow these principles and patterns.

### Core Architecture

Each data source follows a flat, single-level inheritance structure:

1. **DataSource class** — entry point que retorna readers/writers
2. **Base Reader/Writer classes** — lógica compartilhada para opções e processamento de dados
3. **Batch classes** — herdam do base + `DataSourceReader`/`DataSourceWriter`
4. **Stream classes** — herdam do base + `DataSourceStreamReader` (ou `SimpleDataSourceStreamReader`) / `DataSourceStreamWriter`

Mapa de capabilities × classes a implementar:

| Capability | Método em `DataSource` | Classe a implementar |
|---|---|---|
| Batch read | `reader(schema)` | `DataSourceReader` |
| Batch write | `writer(schema, overwrite)` | `DataSourceWriter` |
| Stream read (particionado) | `streamReader(schema)` | `DataSourceStreamReader` |
| Stream read (simples) | `simpleStreamReader(schema)` | `SimpleDataSourceStreamReader` |
| Stream write | `streamWriter(schema, overwrite)` | `DataSourceStreamWriter` |

> `simpleStreamReader()` só é invocado quando `streamReader()` não está implementado. Use `SimpleDataSourceStreamReader` para fontes de baixo throughput que não precisam de particionamento.

See [implementation-template.md](references/implementation-template.md) for the full annotated skeleton covering all four modes (batch read/write, stream read/write).

### Spark-Specific Design Constraints

These are specific to the PySpark DataSource API and its driver/executor architecture — general Python best practices (clean code, minimal dependencies, no premature abstraction) still apply but aren't repeated here.

**Flat single-level inheritance only.** PySpark serializes reader/writer instances to ship them to executors. Complex inheritance hierarchies and abstract base classes break serialization and make cross-process debugging painful. Use one shared base class mixed with the PySpark interface (e.g., `class YourBatchWriter(YourWriter, DataSourceWriter)`).

**Import third-party libraries inside executor methods.** The `read()` and `write()` methods run on remote executor processes that don't share the driver's Python environment. Top-level imports from the driver won't be available on executors — always import libraries like `requests` or database drivers inside the methods that run on workers. Exemplo da documentação oficial:

```python
def read(self, partition):
    from pyspark import TaskContext
    context = TaskContext.get()
    ...
```

**Minimize dependencies.** Every package you add must be installed on all executor nodes in the cluster, not just the driver. Prefer the standard library; when external packages are needed, keep them few and well-known.

**No async/await** unless the external system's SDK is async-only. The PySpark DataSource API is synchronous, so async adds complexity with no benefit.

### Project Setup

Create a Python project using a packaging tool such as `uv`, `poetry`, or `hatch`. Examples use `uv` (substitute your tool of choice):

```bash
uv init your-datasource
cd your-datasource
uv add pyspark pytest pytest-spark
```

> PySpark 4.x requer Python ≥ 3.10. Certifique-se de que o ambiente virtual usa Python 3.10+.

```
your-datasource/
├── pyproject.toml
├── src/
│   └── your_datasource/
│       ├── __init__.py
│       └── datasource.py
└── tests/
    ├── conftest.py
    └── test_datasource.py
```

Run all commands through the packaging tool so they execute within the correct virtual environment:

```bash
uv run pytest                       # Run tests
uv run ruff check src/              # Lint
uv run ruff format src/             # Format
uv build                            # Build wheel
```

### Key Implementation Decisions

**Partitioning Strategy** — choose based on data source characteristics:
- Time-based: for APIs with temporal data
- Token-range: for distributed databases
- ID-range: for paginated APIs
- See [partitioning-patterns.md](references/partitioning-patterns.md) for implementations of each strategy

**Authentication** — support multiple methods in priority order:
- Databricks Unity Catalog credentials
- Cloud default credentials (managed identity)
- Explicit credentials (service principal, API key, username/password)
- See [authentication-patterns.md](references/authentication-patterns.md) for patterns with fallback chains

**Type Conversion** — map between Spark and external types:
- Handle nulls, timestamps, UUIDs, collections
- See [type-conversion.md](references/type-conversion.md) for bidirectional mapping tables and helpers

**Streaming Offsets** — design for exactly-once semantics:
- JSON-serializable offset class
- Non-overlapping partition boundaries
- See [streaming-patterns.md](references/streaming-patterns.md) for offset tracking and watermark patterns

**Error Handling** — implement retries and resilience:
- Exponential backoff for transient failures (network, rate limits)
- Circuit breakers for cascading failures
- See [error-handling.md](references/error-handling.md) for retry decorators and failure classification

### Arrow Batch Yield (Spark 4.0+)

Para fontes de alta performance, o `DataSourceReader` (e `DataSourceStreamReader`) aceita `pyarrow.RecordBatch` diretamente no `read()`. Isso evita a serialização row-by-row e pode entregar ganhos de até uma ordem de magnitude em datasets grandes.

```python
import pyarrow as pa
from pyspark.sql.datasource import DataSource, DataSourceReader, InputPartition

class ArrowBatchDataSource(DataSource):
    @classmethod
    def name(cls):
        return "arrowbatch"

    def schema(self):
        return "key int, value string"

    def reader(self, schema):
        return ArrowBatchReader(schema, self.options)

class ArrowBatchReader(DataSourceReader):
    def partitions(self):
        return [InputPartition()]

    def read(self, partition):
        # import dentro do executor!
        import pyarrow as pa
        keys = pa.array([1, 2, 3], type=pa.int32())
        values = pa.array(["a", "b", "c"], type=pa.string())
        schema = pa.schema([("key", pa.int32()), ("value", pa.string())])
        yield pa.RecordBatch.from_arrays([keys, values], schema=schema)
```

> Use Arrow Batch sempre que o sistema externo ofereça uma API columnar (ex.: BigQuery Storage API, Arrow Flight, bancos de dados com drivers PyArrow nativos). Para fontes row-oriented simples, tuplas ainda são a opção mais legível.

### Filter Pushdown (Spark 4.1+ / DBR 16.4 LTS)

> ⚠️ **Novo em Spark 4.1 / DBR 16.4 LTS:** `DataSourceReader.pushFilters()` permite que o query optimizer repasse predicados ao data source, reduzindo o volume de dados trafegado.

**Regras:**
- Implementar em `DataSourceReader`, **não** em `DataSource` nem em `DataSourceStreamReader`.
- Filter pushdown **só funciona para batch reads**; não é suportado em streaming reads.
- O método deve retornar os filtros que **não** foram absorvidos pelo data source (o Spark os aplicará após a leitura).
- A lista de filtros passada deve ser interpretada como AND lógico entre todos os elementos.
- Databricks recomenda implementar apenas para fontes que suportam filtragem nativa (ex.: bancos de dados, GraphQL APIs).

```python
from pyspark.sql.datasource import DataSourceReader, Filter
from typing import Iterable, List

class MyDatabaseReader(DataSourceReader):
    def __init__(self, schema, options):
        self.schema = schema
        self.options = options
        self._pushed_filters = []

    def pushFilters(self, filters: List[Filter]) -> Iterable[Filter]:
        """
        Recebe filtros do optimizer. Retorna os que NÃO foram absorvidos.
        Os absorvidos ficam em self._pushed_filters para uso no read().
        """
        remaining = []
        for f in filters:
            # Tenta transformar em cláusula SQL nativa da fonte:
            sql_clause = self._try_translate(f)
            if sql_clause:
                self._pushed_filters.append(sql_clause)
            else:
                remaining.append(f)
        return remaining

    def _try_translate(self, f):
        # Implemente a tradução para a linguagem de query do sistema externo
        ...

    def read(self, partition):
        # Use self._pushed_filters ao construir a query
        ...
```

### SimpleDataSourceStreamReader (Spark 4.0+)

Para fontes de streaming de **baixo throughput** que não precisam de particionamento paralelo, implemente `SimpleDataSourceStreamReader` em vez de `DataSourceStreamReader`. O método `simpleStreamReader()` só é invocado quando `streamReader()` não estiver implementado.

```python
from typing import Iterator, Tuple
from pyspark.sql.datasource import SimpleDataSourceStreamReader

class MySimpleStreamReader(SimpleDataSourceStreamReader):
    def initialOffset(self) -> dict:
        return {"offset": 0}

    def read(self, start: dict) -> Tuple[Iterator[Tuple], dict]:
        """
        Lê dados a partir de start e retorna (iterator, next_offset).
        Executado no driver — use apenas para fontes de baixo volume.
        """
        start_idx = start["offset"]
        it = iter([(i,) for i in range(start_idx, start_idx + 10)])
        return (it, {"offset": start_idx + 10})

    def readBetweenOffsets(self, start: dict, end: dict) -> Iterator[Tuple]:
        """
        Leitura determinística para replay em restart/failure.
        """
        return iter([(i,) for i in range(start["offset"], end["offset"])])

    def commit(self, end: dict) -> None:
        pass  # Libere recursos se necessário
```

> **Cuidado:** `SimpleDataSourceStreamReader` executa no **driver**, não nos executores. É adequado para webhooks, polling de APIs com baixo volume e fontes que não suportam paralelismo. Para alto throughput, use `DataSourceStreamReader` com particionamento.

### Testing

```python
import pytest
from unittest.mock import patch, Mock

@pytest.fixture
def spark():
    from pyspark.sql import SparkSession
    return (
        SparkSession.builder
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )

def test_data_source_name():
    assert YourDataSource.name() == "your-format"

def test_writer_sends_data(spark):
    with patch('requests.post') as mock_post:
        mock_post.return_value = Mock(status_code=200)

        df = spark.createDataFrame([(1, "test")], ["id", "value"])
        df.write.format("your-format").option("url", "http://api").save()

        assert mock_post.called

def test_arrow_batch_reader(spark):
    """Verifica que o reader produz Arrow batches corretamente."""
    spark.dataSource.register(ArrowBatchDataSource)
    df = spark.read.format("arrowbatch").load()
    assert df.count() == 3
    assert "key" in df.columns
```

See [testing-patterns.md](references/testing-patterns.md) for unit/integration test patterns, fixtures, and running tests.

### Reference Implementations

Study these for real-world patterns:
- [cyber-spark-data-connectors](https://github.com/alexott/cyber-spark-data-connectors) — Sentinel, Splunk, REST
- [spark-cassandra-data-source](https://github.com/alexott/spark-cassandra-data-source) — Token-range partitioning
- [pyspark-hubspot](https://github.com/dgomez04/pyspark-hubspot) — REST API pagination
- [pyspark-mqtt](https://github.com/databricks-industry-solutions/python-data-sources/tree/main/mqtt) — Streaming com TLS

## Example Prompts

```
Create a Spark data source for reading from MongoDB with sharding support
Build a streaming connector for RabbitMQ with at-least-once delivery
Implement a batch writer for Snowflake with staged uploads
Write a data source for REST API with OAuth2 authentication and pagination
Add filter pushdown to an existing DataSourceReader for a PostgreSQL source
Use Arrow batch yield to speed up a high-throughput custom reader
```

## Related

- databricks-testing: Test data sources on Databricks clusters
- databricks-spark-declarative-pipelines: Use custom sources in DLT pipelines
- python-dev: Python development best practices

## References

- [implementation-template.md](references/implementation-template.md) — Full annotated skeleton; read when starting a new data source
- [partitioning-patterns.md](references/partitioning-patterns.md) — Read when the source supports parallel reads and you need to split work across executors
- [authentication-patterns.md](references/authentication-patterns.md) — Read when the external system requires credentials or tokens
- [type-conversion.md](references/type-conversion.md) — Read when mapping between Spark types and the external system's type system
- [streaming-patterns.md](references/streaming-patterns.md) — Read when implementing `DataSourceStreamReader`, `SimpleDataSourceStreamReader`, or `DataSourceStreamWriter`
- [error-handling.md](references/error-handling.md) — Read when adding retry logic or handling transient failures
- [testing-patterns.md](references/testing-patterns.md) — Read when writing tests; covers unit, integration, and performance testing
- [production-patterns.md](references/production-patterns.md) — Read when hardening for production: observability, security, input validation
- [Official Databricks Documentation](https://docs.databricks.com/aws/en/pyspark/datasources)
- [Apache Spark Python DataSource Tutorial](https://spark.apache.org/docs/latest/api/python/tutorial/sql/python_data_source.html) — PySpark 4.1.1 docs
- [Spark 4.1 Release Notes — Databricks Blog](https://www.databricks.com/blog/introducing-apache-sparkr-41) — Filter pushdown, Arrow-native UDFs, Python worker logging
- [DBR 16.4 LTS Release Notes](https://docs.databricks.com/aws/en/release-notes/runtime/16.4lts) — pushFilters API details
- [awesome-python-datasources](https://github.com/allisonwang-db/awesome-python-datasources) — Directory of community implementations
