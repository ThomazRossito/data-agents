# pytest — Padrões de Teste

## Estrutura

```
tests/
  conftest.py          # fixtures compartilhadas
  unit/
    test_service.py    # testa lógica isolada (sem IO)
  integration/
    test_api.py        # testa endpoints via TestClient
  fixtures/
    sample_data.json
```

## Fixtures Essenciais

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def mock_db():
    with patch("app.services.user_service.db") as mock:
        yield mock

# Fixtures com escopo para setup caro
@pytest.fixture(scope="session")
def db_connection():
    conn = create_connection()
    yield conn
    conn.close()
```

## Testes de API com FastAPI

```python
def test_create_user(client: TestClient):
    response = client.post("/v1/users", json={"name": "João", "email": "j@test.com"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "João"

def test_create_user_invalid(client: TestClient):
    response = client.post("/v1/users", json={"name": ""})
    assert response.status_code == 422  # Pydantic validation error
```

## Mocking

```python
from unittest.mock import AsyncMock, patch

# Mock de função async
@pytest.mark.asyncio
async def test_fetch_data():
    with patch("app.services.fetch_remote", new_callable=AsyncMock) as mock:
        mock.return_value = {"status": "ok"}
        result = await fetch_data()
    assert result["status"] == "ok"

# Patch via pytest-mock (mais limpo)
def test_with_mocker(mocker):
    mock_fn = mocker.patch("app.module.function", return_value=42)
    assert my_function() == 42
    mock_fn.assert_called_once()
```

## Parametrize

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_upper(input: str, expected: str):
    assert input.upper() == expected
```

## Configuração (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=80"
asyncio_mode = "auto"

[tool.coverage.run]
omit = ["*/migrations/*", "*/tests/*"]
```

## Anti-padrões

- ❌ Testes que dependem de ordem de execução — cada teste deve ser independente
- ❌ `time.sleep()` em testes — use `freezegun` ou mocks
- ❌ Fixtures com efeitos colaterais persistentes sem cleanup
- ❌ Asserts sem mensagem em testes complexos — `assert val == expected, f"got {val}"`
- ❌ Mockar o que você não possui (stdlib, third-party) sem encapsular
