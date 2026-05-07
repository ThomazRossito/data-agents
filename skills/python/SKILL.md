---
name: python
description: "Índice de skills Python: FastAPI, pandas/polars, pytest, packaging, asyncio e CLIs. Use ao trabalhar com APIs REST, transformações de dados, testes, publicação de pacotes, código async ou ferramentas de linha de comando."
---

# Python Expert — Índice de Skills

Skills disponíveis para o python-expert. Leia os arquivos relevantes antes de executar.

## Quando Ler

| Arquivo | Quando usar |
|---------|-------------|
| `fastapi-patterns.md` | APIs REST com FastAPI, routers, middleware, Pydantic v2, autenticação |
| `pandas-polars-patterns.md` | Transformações de dados com pandas ou polars; performance, tipos, pipelines |
| `pytest-patterns.md` | Testes unitários e de integração, fixtures, mocking, cobertura |
| `python-packaging.md` | pyproject.toml, setup, entry points, publicação PyPI, pip install -e |
| `async-patterns.md` | asyncio, gather, Queue, cancelamento, httpx async, run_in_executor, Semaphore |
| `cli-patterns.md` | argparse, Typer, Rich output, stdin/stdout/pipe, entry points, exit codes |

## Regras Gerais

- Type hints em TUDO — sem `Any` a não ser que seja estritamente necessário
- PEP 8 + black/ruff formatting
- Dependências mínimas — prefira stdlib antes de adicionar dependências
- `pathlib.Path` ao invés de `os.path`
- `logging` ao invés de `print` em código de produção
- Docstrings apenas quando a interface não for autoevidente
