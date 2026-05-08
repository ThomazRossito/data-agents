---
description: Scaffold de um novo agente especialista no registry (.md com frontmatter YAML) + atualização dos lugares que o loader NÃO resolve automaticamente.
---

# /add-agent — Scaffold de Novo Agente Especialista

Você está adicionando um novo agente ao sistema multi-agente `data-agents`. O loader
dinâmico (`agents/loader.py`) carrega qualquer `.md` válido em `agents/registry/`,
então o agente propriamente dito é **um único arquivo**. Os demais arquivos abaixo
precisam ser atualizados manualmente porque contêm listas hardcoded que o loader não
descobre sozinho.

## Argumento

**Nome do agente em kebab-case** (ex: `ml-ops-expert`, `data-catalog-steward`).
Se o usuário não passar, peça via AskUserQuestion antes de continuar.

## Passos (execute nesta ordem)

### 1. Coletar metadados do agente

Pergunte ao usuário via AskUserQuestion, em uma única chamada:
- **Descrição** (uma linha: "Use para: ...; Invoque quando: ...")
- **Tier** (T1 / T2 / T3) — padrão sugerido: T2
- **MCPs** (lista de chaves do `ALL_MCP_CONFIGS`, pode ser vazia)
- **Domínios de KB** (lista, pode ser vazia — injetado via `kb/<dominio>/index.md`)

### 2. Criar `agents/registry/<nome>.md`

Use o template em `agents/registry/_template.md` como base. Substitua:
- `name:` → kebab-case recebido
- `description:` → texto do passo 1
- `model:` → **sempre `claude-sonnet-4-6`** para T1/T2/T3; `claude-haiku-4-5` apenas para T0 (somente o agente `geral` usa T0)
- `tools:` → inclua `Read, Grep, Glob, Write` + aliases MCP (`databricks_readonly`, `fabric_all`, etc.)
- `mcp_servers:` → lista do passo 1
- `kb_domains:` → lista do passo 1
- `tier:` → T1/T2/T3

Preencha o corpo Markdown com as seções mínimas:
Identidade, Protocolo KB-First, Capacidades, Protocolo de Trabalho, Formato de Resposta, Restrições.

### 3. Atualizar `agents/prompts/supervisor_prompt.py`

Adicionar o novo agente na árvore de delegação descrita no system prompt do Supervisor.
Procure pelo bloco que lista os agentes por tier e insira o novo no tier correto.

### 4. Atualizar `agents/delegation_map.yaml`

Adicionar rotas para o novo agente: keywords que o Supervisor deve reconhecer como
trigger de delegação + situações de uso. Regenerar `kb/task_routing.md` após:

```bash
python3 -c "from agents.delegation import render_routing_table; print(render_routing_table())" \
  > kb/task_routing.md
```

### 5. Atualizar arquivos com listas hardcoded

Estes arquivos têm listas de agentes que **não são derivadas do registry dinamicamente**
e precisam de atualização manual:

**`ui/ui_config.py` → `AGENT_DISPLAY_NAMES`** (dict hardcoded — label de exibição na UI):
```python
AGENT_DISPLAY_NAMES: dict[str, str] = {
    ...,
    "<nome>": "<Nome Legível>",   # ← adicionar aqui
}
```

**`commands/party.py` → `PARTY_GROUPS["full"]`** (lista hardcoded — agentes do modo `/party --full`):
```python
"full": [
    ...,
    "<nome>",   # ← adicionar se o agente deve aparecer no party mode completo
],
```

**`commands/party.py` → `AGENT_PERSONAS`** (dict hardcoded — system prompt do agente no party mode):
```python
AGENT_PERSONAS: dict[str, str] = {
    ...,
    "<nome>": (
        "Você é um especialista em [domínio]. "
        "Seu foco: [especializações]. "
        "Responda com perspectiva de [papel]. "
        "Seja direto, técnico e objetivo. "
        "Always respond in English (EN-US)."
    ),
}
```

**`tests/test_functional.py` → `VALID_AGENTS`** (set hardcoded — valida que party mode só usa agentes conhecidos):
```python
VALID_AGENTS = {
    ...,
    "<nome>",   # ← adicionar aqui
}
```

> **Nota:** `AGENT_TIERS`, `KNOWN_AGENTS` e `_AGENT_TIERS` são derivados dinamicamente
> do registry via `config/agent_meta.py` — **não precisam de atualização manual**.

### 6. Atualizar contagem de agentes nos documentos

```bash
grep -rn "22 agentes\|22 especialistas\|22 agents" \
  .claude/CLAUDE.md README.md PRODUCT.md \
  "Manual_Relatorio_Tecnico_Projeto_Data_Agents.md" \
  wiki/index.md 2>/dev/null
```

Incrementar para o novo total em todos os arquivos encontrados.

### 7. Validar

Rode em paralelo:
```bash
python -c "
from agents.loader import load_all_agents
a = load_all_agents(available_mcp_servers=set())
print('ok:', len(a), 'agentes')
print(sorted(a.keys()))
"
make test
```

O novo agente deve aparecer na lista. Se não aparecer, o frontmatter YAML tem erro de parse.

## Checklist final (confirme antes de reportar pronto)

- [ ] `agents/registry/<nome>.md` criado com frontmatter YAML válido
- [ ] `agents/prompts/supervisor_prompt.py` referencia o novo agente no tier correto
- [ ] `agents/delegation_map.yaml` tem rotas para o novo agente
- [ ] `kb/task_routing.md` regenerado
- [ ] `ui/ui_config.py` → `AGENT_DISPLAY_NAMES` atualizado
- [ ] `commands/party.py` → `PARTY_GROUPS["full"]` atualizado (se aplicável)
- [ ] `commands/party.py` → `AGENT_PERSONAS` atualizado
- [ ] `tests/test_functional.py` → `VALID_AGENTS` atualizado
- [ ] `tests/test_agents.py` verificado (contagem explícita, se houver)
- [ ] Contagem de agentes atualizada em: `CLAUDE.md`, `README.md`, `PRODUCT.md`, `Manual_Relatorio_Tecnico_Projeto_Data_Agents.md`, `wiki/index.md`
- [ ] Loader reconhece o agente (smoke test do passo 7 passou)
- [ ] `make test` verde

Se algum passo falhar, **pare e reporte** em vez de tentar remendar silenciosamente.
