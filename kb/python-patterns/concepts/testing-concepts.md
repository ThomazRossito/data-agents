# Testes Python — pytest

## Estrutura de Projeto

```
project/
├── src/
│   └── mypackage/
│       ├── __init__.py
│       └── module.py
└── tests/
    ├── conftest.py          ← fixtures compartilhadas + plugins
    ├── unit/
    │   └── test_module.py
    └── integration/
        └── test_db.py
```

## Fixtures — Escopos e Uso Correto

```python
# conftest.py
import pytest
from mypackage.db import Database

@pytest.fixture(scope="session")    # criado UMA vez por sessão de teste
def db_engine():
    engine = Database.connect("postgresql://localhost/test")
    yield engine
    engine.close()

@pytest.fixture(scope="function")   # padrão — recriado para cada teste
def clean_table(db_engine):
    db_engine.execute("DELETE FROM events")
    yield db_engine
    db_engine.execute("ROLLBACK")

@pytest.fixture
def sample_data() -> list[dict]:
    return [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]
```

| Scope | Quando usar |
|-------|-------------|
| `function` (padrão) | Estado que muda por teste |
| `class` | Fixtures compartilhadas dentro de uma classe de testes |
| `module` | Setup caro por arquivo, sem side effects entre testes |
| `session` | Conexões de banco, containers Docker, arquivos grandes |

## Parametrize — Edge Cases

```python
import pytest

@pytest.mark.parametrize("value,expected", [
    (0,    True),
    (1,    True),
    (-1,   False),
    (None, False),
    ("",   False),
])
def test_is_valid(value, expected):
    assert is_valid(value) == expected
```

## Mocking — Princípio Fundamental

**Mockar apenas I/O externo real** — HTTP, banco, filesystem remoto, relógio do sistema.
Nunca mockar lógica de negócio ou transformações internas.

```python
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Mock de função HTTP
def test_fetch_user(requests_mock):         # via requests-mock plugin
    requests_mock.get("/users/1", json={"id": 1, "name": "Alice"})
    result = fetch_user(1)
    assert result.name == "Alice"

# Mock de função com patch
def test_save_calls_write(tmp_path):
    target = tmp_path / "output.json"
    save_result({"key": "value"}, target)
    assert target.exists()

# Mock de método de classe
@patch("mypackage.module.ExternalService.call")
def test_with_external(mock_call):
    mock_call.return_value = {"status": "ok"}
    result = process()
    mock_call.assert_called_once_with(timeout=30)
    assert result == "ok"

# Mock async
@pytest.mark.asyncio
async def test_async_fetch():
    with patch("mypackage.client.fetch", new_callable=AsyncMock) as mock:
        mock.return_value = b"data"
        result = await process_async()
    assert result == "data"
```

## pytest-cov — Cobertura

```bash
# Cobertura mínima 80% — falha se abaixo
pytest --cov=src --cov-report=term-missing --cov-fail-under=80

# Relatório HTML
pytest --cov=src --cov-report=html
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-fail-under=80"

[tool.coverage.run]
omit = ["tests/*", "src/mypackage/__main__.py"]
```

## hypothesis — Testes Baseados em Propriedades

Use para funções com invariantes matemáticas ou de formato:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(lst):
    sorted_once = sorted(lst)
    sorted_twice = sorted(sorted_once)
    assert sorted_once == sorted_twice

@given(st.text(min_size=1))
def test_parse_roundtrip(text):
    assert decode(encode(text)) == text
```

## Regras de Ouro

1. **Um módulo → um arquivo de teste**: `src/x/y.py` → `tests/unit/test_y.py`.
2. **Nomes descritivos**: `test_<o_que_faz>_when_<condição>_should_<resultado>`.
3. **AAA**: Arrange → Act → Assert. Um `assert` lógico por teste.
4. **Fixtures > setup/teardown**: evitar `setUp`/`tearDown` estilo unittest.
5. **`tmp_path` para arquivos temporários**: fixture built-in do pytest, sem cleanup manual.
6. **`caplog` para logging**: `assert "error" in caplog.text` em vez de mockar o logger.
