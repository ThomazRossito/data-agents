---
description: Scaffold de um novo agente especialista no registry (.md com frontmatter YAML) + atualização dos 2 lugares que o loader NÃO resolve automaticamente.
---

# /add-agent — Scaffold de Novo Agente Especialista

Você está adicionando um novo agente ao sistema multi-agente `data-agents`. O loader
dinâmico (`agents/loader.py`) carrega qualquer `.md` válido em `agents/registry/`,
então o agente propriamente dito é **um único arquivo**. Os outros 2 arquivos são
bootstrap que o loader não descobre sozinho.

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
- `model:` → `bedrock/anthropic.claude-haiku-4-5` se T3 **conceitual** (sem MCP);
  `claude-sonnet-4-6` se T2; `claude-opus-4-6` se T1.
- `tools:` → inclua `Read, Grep, Glob, Write` + aliases MCP (`databricks_readonly`, `fabric_all`, etc.)
- `mcp_servers:` → lista do passo 1
- `kb_domains:` → lista do passo 1
- `tier:` → T1/T2/T3

Preencha o corpo Markdown com as seções mínimas:
Identidade, Protocolo KB-First, Capacidades, Protocolo de Trabalho, Formato de Resposta, Restrições.

### 3. Atualizar `agents/prompts/supervisor_prompt.py`

Adicionar o novo agente na árvore de delegação descrita no system prompt do Supervisor.
**Procure pelo comentário ou bloco que lista os agentes** e insira o novo no tier correto.

> Atenção: quando Sprint 2 entregar T2.1 + delegation_map.yaml, este passo passará a ser
> apenas um edit de YAML. Por enquanto, é Python mesmo.

### 4. Atualizar `tests/test_agents.py`

Verifique se há algum teste que conta agentes ou que valida invariantes específicas.
O loader cobre a maior parte via introspecção, mas contagens explícitas (ex: `assert len(agents) == 13`)
precisam ser incrementadas manualmente.

### 5. Validar

Rode em paralelo:
```bash
python -c "from agents.loader import load_all_agents; a = load_all_agents(available_mcp_servers=set()); print('ok:', len(a), 'agentes'); print(sorted(a.keys()))"
make test  # (ou: pytest tests/test_agents.py -x)
```

O novo agente deve aparecer na lista. Se não aparecer, o frontmatter YAML tem erro de parse.

### 6. Atualizar CLAUDE.md

Adicione o agente em 2 tabelas:
- **Arquitetura de Alto Nível** (linha na árvore do Supervisor)
- **MCPs por Agente (estado atual)** (linha na tabela)

## Checklist final (confirme antes de reportar pronto)

- [ ] `agents/registry/<nome>.md` criado com frontmatter YAML válido
- [ ] `agents/prompts/supervisor_prompt.py` referencia o novo agente
- [ ] `tests/test_agents.py` atualizado se necessário
- [ ] Loader reconhece o agente (smoke test do passo 5 passou)
- [ ] `CLAUDE.md` atualizado em 2 tabelas
- [ ] Contagem de agentes no CLAUDE.md atualizada (ex: "14 agentes")

Se algum passo falhar, **pare e reporte** em vez de tentar remendar silenciosamente.
