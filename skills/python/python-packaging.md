# Python Packaging — pyproject.toml e Distribuição

## pyproject.toml Moderno (PEP 517/518/621)

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "meu-pacote"
version = "1.0.0"
description = "Descrição curta"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "MIT"}
authors = [{name = "Autor", email = "autor@email.com"}]

dependencies = [
    "httpx>=0.27",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff", "mypy"]
docs = ["mkdocs", "mkdocstrings"]

[project.scripts]
meu-cli = "meu_pacote.cli:main"

[project.urls]
Repository = "https://github.com/user/meu-pacote"
```

## Entry Points para CLIs

```python
# meu_pacote/cli.py
import click

@click.group()
def main():
    pass

@main.command()
@click.argument("nome")
@click.option("--verbose", "-v", is_flag=True)
def processar(nome: str, verbose: bool):
    if verbose:
        click.echo(f"Processando {nome}...")
```

## Instalação em Desenvolvimento

```bash
pip install -e ".[dev]"         # instala com extras dev
pip install -e ".[dev,docs]"    # múltiplos extras
```

## setuptools — Descoberta de Pacotes

```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["meu_pacote*"]
exclude = ["tests*"]
```

## Ferramentas de Qualidade

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "F", "I", "UP", "B", "S"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.ruff.lint.isort]
known-first-party = ["meu_pacote"]
```

## Build e Publicação PyPI

```bash
pip install build twine

python -m build                              # gera dist/*.whl + dist/*.tar.gz
twine check dist/*                           # valida antes de publicar
twine upload dist/*                          # sobe para PyPI
twine upload --repository testpypi dist/*   # sobe para TestPyPI primeiro
```

## Versionamento Semântico

- `MAJOR.MINOR.PATCH` — ex: `2.1.3`
- MAJOR: breaking changes
- MINOR: novos features (compatível)
- PATCH: bug fixes

Automatização com `bump2version` ou `python-semantic-release`.

## Anti-padrões

- ❌ `setup.py` legado para novos projetos — use `pyproject.toml`
- ❌ Pinning excessivo em libraries (`==`) — reserve para apps/deploys
- ❌ `requirements.txt` como substituto de `pyproject.toml`
- ❌ Publicar sem `twine check` — invalida distribuição no PyPI
