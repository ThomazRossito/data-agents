# Contributing to data-agents-copilot

Muito obrigado por querer contribuir! Este documento descreve como participar dos esforços de desenvolvimento.

## Código de Conduta

Somos dedicados a fornecer um ambiente acolhedor, independentemente de idade, corpo, deficiência, etnia, gênero, nível de experiência, nacionalidade, aparência pessoal, raça, religião, identidade sexual ou orientação sexual.

## Como Contribuir

### Relatando Bugs

- **Use o GitHub Issues** com o template `bug`.
- **Descrição clara** do problema.
- **Passos para reproduzir**.
- **Comportamento esperado vs observado**.
- **Ambiente** (Python version, VS Code version, agent usado).

### Sugerindo Melhorias

- **Use o GitHub Issues** com o template `enhancement`.
- **Use caso claro** — quando a melhoria seria útil?
- **Exemplos concretos** — antes e depois.

### Pull Requests

#### Pré-requisitos

1. Fork o repositório
2. Clone seu fork: `git clone https://github.com/YOUR-USERNAME/data-agents-copilot.git`
3. Crie branch: `git checkout -b feature/descricao`
4. Instale dependências: `pip install -e ".[dev]"`

#### Workflow

1. **Código**
   - Seguir style guide (veja abaixo)
   - Adicionar testes se apropriado
   - Atualizar docstrings em português

2. **Testes**
   ```bash
   pytest tests/ -v
   mypy --strict agents/
   ruff check agents/ config/ hooks/ ui/
   ```

3. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: adicionar Naming Guard"
   git push origin feature/descricao
   ```

4. **Pull Request**
   - Título descritivo em inglês ou português
   - Descrição clara do que muda
   - Reference related issues: `Closes #123`

### Alterações em Recursos Críticos

#### Naming Convention (`resources/naming convention.md`)

Se estiver atualizando a convenção de nomenclatura:

1. **Coloque em staging**: `resources/naming convention.md`
2. **Documente a mudança**:
   - Qual antiga regra muda?
   - Por quê?
   - Qual o prazo de transição?
3. **Teste com Naming Guard**:
   ```
   /naming CREATE TABLE nova_tabela (...)
   ```
4. **Notifique no CHANGELOG** com versão e data de deprecação (se houver).

#### Adicionando Novo Agente

1. Criar arquivo `agents/registry/novo_agente.md`
2. Adicionar ao `AGENT_COMMANDS` em `agents/loader.py`
3. Testes: `pytest tests/test_agents.py::test_novo_agente_loads`
4. Documentar em `README.md`

## Style Guide

### Python

- **PEP 8** — 88 caracteres por linha (Black)
- **Type hints** — Sempre (mypy strict mode)
- **Docstrings** — Google style em português
- **Imports** — Alphabetical, depois de sort

```python
"""Módulo para validação de nomes."""

from typing import Optional
from pathlib import Path
import re

def validate_name(name: str) -> bool:
    """Validar se nome segue snake_case.
    
    Args:
        name: Nome a validar.
        
    Returns:
        True se válido, False caso contrário.
        
    Raises:
        ValueError: Se nome None.
    """
    if name is None:
        raise ValueError("Nome não pode ser None")
    return bool(re.match(r'^[a-z][a-z0-9_]*$', name))
```

### Markdown

- **Headings** — `#`, `##`, `###`
- **Code blocks** — Sempre com language: ` ```python `
- **Links** — Relative whenever possible
- **Tables** — Algn center quando numérico

## Testing

- **71Covereage** ≥ 80% para módulos novos
- **Fixtures** — Use `conftest.py` para setup compartilhado
- **Nomenclatura** — `test_<funcao>_<cenario>.py`

```python
def test_naming_guard_detects_create_table(supervisor):
    """Test that naming guard triggers on CREATE TABLE."""
    result = supervisor.route("CREATE TABLE raw_customers (...)")
    assert "Naming Guard" in result.content
    assert "reprovado" in result.content or "aprovado" in result.content
```

## Commits

**Commit messages** em português, começando com:

- `feat:` — Nova feature
- `fix:` — Bug fix
- `docs:` — Documentação
- `test:` — Testes
- `refactor:` — Refatoração sem mudança funcional
- `perf:` — Otimização de performance
- `chore:` — Tasks, dependências, etc.

Exemplos:

```
feat: adicionar validação de nomenclatura automática

fix: corrigir detecção de _TABLE_CREATION_PATTERN em queries inline

docs: atualizar README com exemplos de Naming Guard

test: adicionar testes para agente geral
```

## Versioning

Seguimos **Semantic Versioning** (MAJOR.MINOR.PATCH):

- **MAJOR** — Breaking changes (incompatível com versão anterior)
- **MINOR** — Nova feature (backwards-compatible)
- **PATCH** — Bug fix

Tag format: `v1.0.0`

## Dúvidas?

- Abra uma Discussion no GitHub
- Mencione `@data-agents-copilot` em issues
- Consulte docs/ para decisões de arquitetura

---

**Obrigado por contribuir! 🙏**
