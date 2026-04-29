# Testing Quick Reference

> Tabelas de lookup rápido. Para exemplos completos ver arquivos linkados.

## pytest CLI

| Comando | Propósito |
|---------|-----------|
| `pytest` | Roda todos os testes |
| `pytest -k "spark"` | Filtra por nome (substring) |
| `pytest -m "unit"` | Filtra por marker |
| `pytest -x` | Para no primeiro erro |
| `pytest --tb=short` | Tracebacks curtos |
| `pytest -n auto` | Paralelo (requer pytest-xdist) |
| `pytest --co` | Lista testes sem executar |
| `pytest --cov=src --cov-report=term-missing` | Coverage report |

## Fixture Scopes

| Scope | Lifecycle | Use Case |
|-------|-----------|----------|
| `function` | Por test (default) | Estado independente |
| `class` | Por test class | Estado compartilhado na classe |
| `module` | Por .py file | Setup caro de módulo |
| `session` | Toda a run | SparkSession, conexões DB |

## Mock Patterns

| Padrão | Sintaxe | Use Case |
|--------|---------|----------|
| Patch função | `@mock.patch("module.func")` | Substituir função |
| Patch método | `@mock.patch.object(Class, "method")` | Substituir método |
| Return value | `mock.return_value = X` | Controlar output |
| Side effect | `mock.side_effect = [1, 2, 3]` | Retornos sequenciais |
| Env var | `monkeypatch.setenv("KEY", "val")` | Override env vars |
| Databricks token | `monkeypatch.setenv("DATABRICKS_TOKEN", "dummy")` | Off-cluster test |

## Decision Matrix

| Use Case | Escolha |
|----------|---------|
| Isolar uma transformação PySpark | Unit test + SparkSession `local[1]` |
| Testar MERGE / schema / Delta | Integration test + Databricks Connect |
| Mesmo código, múltiplos schemas | `@pytest.mark.parametrize` |
| Objetos de teste reutilizáveis | Factory fixture |
| Recurso externo lento | Mock ou `@pytest.mark.slow` |
| Boundary conditions (null, vazio) | Parametrize com casos extremos |

## Common Pitfalls

| Evite | Prefira |
|-------|---------|
| SparkSession nova por test | Session-scoped SparkSession fixture |
| Patch em módulo de definição | Patch em módulo de importação |
| Estado mutável entre testes | Function-scoped fixtures |
| Ignorar casos com NULL | Sempre incluir NULL nos parametrize |
| `spark.read.csv()` sem schema | Schema explícito via StructType no fixture |

## Related

| Tópico | Arquivo |
|--------|---------|
| SparkSession fixture + DataFrame assertions | patterns/spark-unit-tests.md |
| Databricks Connect + CI | patterns/integration-tests.md |
| Config pytest, markers, coverage | specs/test-config.yaml |
