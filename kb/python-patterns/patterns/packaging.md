# Empacotamento Python Moderno

## pyproject.toml — Estrutura Completa

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "meu-pacote"
version = "1.2.0"
description = "Breve descrição do pacote"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
authors = [{ name = "Time de Dados", email = "dados@empresa.com" }]

dependencies = [
    "pydantic>=2.0",
    "httpx>=0.25",
    "pandas>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov", "ruff", "mypy"]
docs = ["mkdocs-material"]

[project.scripts]              # entry_points para CLIs
meu-cli = "meu_pacote.cli:app"

[project.urls]
Repository = "https://github.com/org/repo"

# --- Ferramentas ---

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["meu_pacote"]

[tool.mypy]
strict = true
python_version = "3.10"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-fail-under=80 -q"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*"]
```

## Estrutura de Diretórios — src layout (preferida)

```
meu-pacote/
├── pyproject.toml
├── README.md
├── src/
│   └── meu_pacote/
│       ├── __init__.py        ← exporta API pública via __all__
│       ├── core.py
│       ├── cli.py
│       └── py.typed           ← sinaliza que o pacote tem type hints (PEP 561)
└── tests/
    ├── conftest.py
    └── test_core.py
```

`__init__.py` com `__all__` explícito:

```python
# src/meu_pacote/__init__.py
from meu_pacote.core import Pipeline, run_pipeline
from meu_pacote._version import __version__

__all__ = ["Pipeline", "run_pipeline", "__version__"]
```

## uv — Gerenciador de Pacotes Moderno (recomendado)

```bash
# Criar projeto novo
uv init meu-pacote --python 3.12

# Instalar dependências (resolve + instala em <1s)
uv sync

# Instalar extras de dev
uv sync --extra dev

# Adicionar dependência
uv add httpx
uv add --dev pytest

# Rodar em virtualenv sem ativar
uv run pytest
uv run python -m meu_pacote

# Publicar no PyPI
uv build && uv publish
```

## entry_points — CLIs Instaláveis

```python
# src/meu_pacote/cli.py
import typer

app = typer.Typer()

@app.command()
def run(
    source: str = typer.Argument(help="Caminho de entrada"),
    output: str = typer.Option("output/", "--output", "-o"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Processa dados do SOURCE para OUTPUT."""
    ...

if __name__ == "__main__":
    app()
```

Após `uv sync`, o comando `meu-cli` fica disponível no PATH do virtualenv.

## importlib.metadata — Versão em Runtime

```python
from importlib.metadata import version, PackageNotFoundError

def get_version() -> str:
    try:
        return version("meu-pacote")
    except PackageNotFoundError:
        return "dev"
```

## Versionamento Semântico

```
MAJOR.MINOR.PATCH
  │     │     └── bug fix (compatível com versão anterior)
  │     └── nova feature (compatível com versão anterior)
  └── breaking change (incompatível com versão anterior)
```

Tags `alpha`, `beta`, `rc` para pré-releases: `1.2.0a1`, `1.2.0rc2`.

## Regras de Ouro

1. **src layout** — evita importação acidental do código fora do pacote instalado.
2. **`py.typed` sempre** — sinaliza suporte a mypy para downstream.
3. **`__all__` em `__init__.py`** — contrato explícito da API pública.
4. **Nunca commitar `uv.lock` em bibliotecas**, sempre em aplicações.
5. **`uv` > `pip` + `venv`** — resolve em paralelo, reprodutível, mais rápido.
