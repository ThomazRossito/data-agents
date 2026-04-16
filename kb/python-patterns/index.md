---
mcp_validated: "2026-04-16"
---

# KB: Padrões Python — Índice

**Domínio:** Python moderno para Engenharia de Software e Engenharia de Dados.
**Agentes:** python-expert

---

## Conteúdo Disponível

### Conceitos (`concepts/`)

| Arquivo | Conteúdo |
|---------|----------|
| `concepts/type-system.md` | Type hints, generics, Protocol, TypeVar, ParamSpec, mypy strict |
| `concepts/data-structures.md` | dataclasses, NamedTuple, TypedDict, Pydantic v2 — quando usar cada um |
| `concepts/concurrency.md` | asyncio, threading, multiprocessing, concurrent.futures — modelo mental |
| `concepts/testing-concepts.md` | pytest: fixtures, scopes, mocking, parametrize, hypothesis |

### Padrões (`patterns/`)

| Arquivo | Conteúdo |
|---------|----------|
| `patterns/data-io.md` | pandas, polars, duckdb, pyarrow, fsspec — leitura/escrita eficiente |
| `patterns/packaging.md` | pyproject.toml, entry_points, uv, publicação, importlib.metadata |
| `patterns/api-patterns.md` | FastAPI, Pydantic v2, dependency injection, error handlers, auth |
| `patterns/cli-patterns.md` | Typer, Click, Rich — CLIs robustas com output estruturado |

---

## Regras de Negócio Críticas

### Type Safety (Obrigatório)
- Type hints em TODAS as funções públicas: parâmetros + retorno.
- `mypy --strict` é o baseline mínimo para código de produção.
- Use `Protocol` para duck typing estrutural; evite `Any` exceto em boundaries de sistema.
- `TypedDict` para dicts com shape conhecido; `dataclass` para objetos com comportamento.

### Segurança
- NUNCA hardcode tokens, senhas ou API keys. Usar `os.environ` ou `pydantic.BaseSettings`.
- NUNCA usar `shell=True` em `subprocess.run` com input não sanitizado — risco de injeção de comando.
- Validar dados externos (APIs, arquivos, CLI args) com Pydantic antes de processar.

### Performance — Dados
- Evitar `iterrows` no pandas — sempre buscar operações vetorizadas ou `apply` com `axis=1`.
- Para DataFrames > 500MB: preferir polars lazy API ou duckdb em vez de pandas in-memory.
- Usar pyarrow para I/O de Parquet; nunca usar `pickle` para persistência entre processos.
- `duckdb.connect()` para SQL in-process sobre arquivos — muito mais rápido que pandas para agregações.

### Testes
- Coverage mínima de 80% para módulos novos.
- Fixtures de escopo `session` para recursos caros (conexões, arquivos grandes).
- Mocks apenas para I/O externo real (HTTP, banco, filesystem remoto) — nunca mockar lógica de negócio.
- `pytest.mark.parametrize` para cobrir edge cases: None, lista vazia, tipo errado, overflow.
