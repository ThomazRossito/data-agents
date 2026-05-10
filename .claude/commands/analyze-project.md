---
description: Análise completa e profunda do projeto data-agents — varre todos os arquivos, diretórios e subdirectórios, lê cada módulo Python, agente, hook, config, teste, KB e skill, e produz um relatório técnico detalhado com todos os detalhes de programação, arquitetura, fluxos e dependências.
---

# /analyze-project — Análise Completa do Projeto

Você vai fazer uma varredura **total e sistemática** do projeto `data-agents`.
O objetivo é compreender cada arquivo, módulo, classe, função e configuração —
sem deixar nenhum diretório ou subdiretório de fora.

Ao final, você terá pleno contexto do projeto e produzirá um relatório técnico
completo salvo em `output/analyze-project/relatorio_projeto.md`.

---

## Argumento (opcional)

`/analyze-project [--focus <módulo>]` — sem argumento analisa tudo; com `--focus`
aprofunda em um módulo específico (ex: `--focus hooks`, `--focus memory`, `--focus agents`).

---

## Protocolo de Análise — Execute Nesta Ordem

### Fase 1 — Mapeamento Estrutural

Execute em paralelo via Bash:

```bash
# Árvore completa excluindo ruído
find . \
  -not -path '*/.git/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.ruff_cache/*' \
  -not -path '*/.mypy_cache/*' \
  -not -path '*/.pytest_cache/*' \
  -not -path '*/.chainlit/translations/*' \
  -not -path '*/.obsidian/*' \
  -not -name '*.pyc' \
  -not -name '.DS_Store' \
  -type f | sort

# Estatísticas gerais
echo "=== Contagem por extensão ===" && \
find . -not -path '*/.git/*' -not -path '*/__pycache__/*' -type f \
  | grep -oE '\.[^./]+$' | sort | uniq -c | sort -rn | head -20

# Linhas de código Python
find . -name "*.py" -not -path '*/__pycache__/*' | \
  xargs wc -l | sort -rn | head -30

# Agentes no registry
echo "=== Agentes registry ===" && \
ls -la agents/registry/*.md

# MCP servers disponíveis
echo "=== MCP servers ===" && \
ls -la mcp_servers/

# Skills disponíveis
echo "=== Skills count ===" && \
find skills/ -name "SKILL.md" | wc -l && \
find skills/ -name "SKILL.md" | sort

# KBs disponíveis
echo "=== KBs count ===" && \
find kb/ -name "*.md" | wc -l

# Testes
echo "=== Testes ===" && \
ls tests/test_*.py | wc -l && ls tests/test_*.py
```

### Fase 2 — Arquivos de Configuração e Entrada

Leia na seguinte ordem:

1. `pyproject.toml` — dependências, extras, ferramentas
2. `.env.example` — variáveis de ambiente disponíveis
3. `Makefile` — targets de build, test, health
4. `.mcp.json` — configuração de MCP servers para Claude Code Desktop
5. `.github/workflows/ci.yml` — pipeline CI
6. `.github/workflows/cd.yml` — pipeline CD
7. `databricks.yml` — bundle config DAB
8. `.pre-commit-config.yaml` — hooks de qualidade
9. `config/commands.yaml` — mapeamento de slash commands

### Fase 3 — Core do Sistema (leitura obrigatória e completa)

Leia cada arquivo completamente e anote: classes, funções, assinaturas, side effects.

**config/:**
- `config/settings.py` — todos os campos do `Settings(BaseSettings)`, validações, tier maps
- `config/mcp_servers.py` — `ALL_MCP_CONFIGS`, `ALWAYS_ACTIVE_MCPS`, `build_mcp_registry()`
- `config/exceptions.py` — hierarquia de exceções
- `config/logging_config.py` — setup de logging structlog
- `config/snapshot.py` — save/restore de config

**agents/:**
- `agents/loader.py` — `MCP_TOOL_SETS`, `preload_registry()`, `load_agent()`, `load_all_agents()`, `inject_memory_context()`, `_resolve_tools()`, `_load_kb_indexes()`, `_load_skills_index()`, `_load_cache_prefix()`
- `agents/supervisor.py` — `build_supervisor_options()`: como monta o ClaudeAgentOptions, quais hooks, quais tools do Supervisor
- `agents/prompts/supervisor_prompt.py` — system prompt completo do Supervisor
- `agents/delegation.py` — lógica de roteamento declarativo
- `agents/delegation_map.yaml` — mapeamento intent → agente
- `agents/mlflow_wrapper.py` — wrapper de logging com MLflow
- `agents/siftools_integration.py` — pruning semântico de tools
- `agents/cache_prefix.md` — prefixo compartilhado (prompt caching)

**main.py** — entry point completo: args, loop, session management

### Fase 4 — Todos os Agentes do Registry

Para cada arquivo em `agents/registry/` (exceto `_template.md`):

Leia o arquivo completo e extraia:
- `name`, `description`, `model`, `tier`, `tools[]`, `mcp_servers[]`, `kb_domains[]`, `skill_domains[]`, `max_turns`, `effort`
- Identidade e papel do agente
- Capacidades declaradas
- Protocolo de trabalho
- Restrições

Agentes a analisar:
- `agents/registry/business-analyst.md`
- `agents/registry/business-monitor.md`
- `agents/registry/data-quality-steward.md`
- `agents/registry/dbt-expert.md`
- `agents/registry/geral.md`
- `agents/registry/governance-auditor.md`
- `agents/registry/migration-expert.md`
- `agents/registry/pipeline-architect.md`
- `agents/registry/python-expert.md`
- `agents/registry/semantic-modeler.md`
- `agents/registry/spark-expert.md`
- `agents/registry/sql-expert.md`

### Fase 5 — Todos os Hooks

Leia completamente cada hook e anote: tipo (Pre/Post), trigger, comportamento exato, side effects:

- `hooks/security_hook.py` — 22 padrões bloqueados, regex de SELECT *
- `hooks/audit_hook.py` — schema do JSONL de auditoria, 6 categorias de erro
- `hooks/cost_guard_hook.py` — critérios HIGH/MEDIUM/LOW, threshold de alerta
- `hooks/output_compressor_hook.py` — estratégias de compressão, thresholds
- `hooks/workflow_tracker.py` — eventos rastreados, Clarity Checkpoint
- `hooks/memory_hook.py` — o que captura, quando faz flush
- `hooks/context_budget_hook.py` — cálculo de budget, percentuais de alerta
- `hooks/session_logger.py` — métricas registradas por sessão
- `hooks/session_lifecycle.py` — start/end handlers
- `hooks/checkpoint.py` — formato de serialização do estado
- `hooks/transcript_hook.py` — formato do transcript salvo

### Fase 6 — Sistema de Memória

- `memory/types.py` — dataclasses: `Memory`, `MemoryFact`, campos e tipos
- `memory/store.py` — API de persistência, formato JSON
- `memory/extractor.py` — como extrai fatos do transcript
- `memory/retrieval.py` — algoritmo de busca semântica, como chama Sonnet lateral
- `memory/compiler.py` — lógica de consolidação e deduplicação
- `memory/decay.py` — fórmula de decay temporal
- `memory/lint.py` — validações de integridade
- `memory/telemetry.py` — métricas coletadas

### Fase 7 — MCP Servers

Para cada diretório em `mcp_servers/` (exceto `_template/`):

Leia `server_config.py` e (se existir) `server.py`:
- Função de configuração: comando, args, env vars
- `MCP_TOOLS` e `MCP_READONLY_TOOLS` (lista completa de tool names)
- Para MCPs customizados (`server.py`): classes, endpoints, integrações

MCP servers a analisar:
`databricks/`, `databricks_genie/`, `fabric/`, `fabric_rti/`, `fabric_semantic/`,
`fabric_sql/`, `context7/`, `tavily/`, `github/`, `firecrawl/`, `postgres/`,
`memory_mcp/`, `migration_source/`

### Fase 8 — Comandos e Workflows

- `commands/parser.py` — `CommandRegistry`, como faz parse de args
- `commands/geral.py` — implementação do `/geral`
- `commands/monitor.py` — implementação do `/monitor`
- `commands/party.py` — flags `--quality`, `--arch`, `--engineering`, `--migration`, `--full`; como executa em paralelo
- `commands/sessions.py` — como lista e restaura sessões
- `commands/workflow.py` — como executa WF-01 a WF-05

- `workflow/dag.py` — estrutura do DAG, campos de WorkflowStep
- `workflow/executor.py` — context chain entre steps, como passa output de um step para o próximo
- `workflow/tracker.py` — formato de log de execução

### Fase 9 — Compressão, Evals e UI

- `compression/constants.py` — limites e thresholds
- `compression/strategies.py` — lógica de cada estratégia
- `compression/hook.py` — quando ativa cada estratégia
- `evals/runner.py` — como executa canonical_queries
- `evals/canonical_queries.yaml` — conjunto de queries de benchmark
- `ui/chainlit_app.py` — handlers de sessão e mensagem, streaming
- `ui/ui_config.py` — avatares, tema, labels por agente
- `monitoring/app.py` — métricas exibidas no Streamlit

### Fase 10 — Utilitários, Scripts e Tools

- `utils/frontmatter.py` — `parse_yaml_frontmatter()`: regex/parser
- `utils/tokenizer.py` — modelo de contagem de tokens, preços por modelo
- `utils/summarizer.py` — quando usa Haiku, como estrutura o prompt de sumarização
- `utils/monitor_alerter.py` — canais de alerta disponíveis
- `scripts/monitor_daemon.py` — frequência de checagem, formato de alertas
- `scripts/refresh_skills.py` — como chama Messages API diretamente
- `scripts/bootstrap.py` — o que valida no ambiente
- `scripts/analyze_tool_coverage.py` — métricas de cobertura de tools
- `tools/databricks_health_check.py` — checagens realizadas
- `tools/fabric_health_check.py` — checagens realizadas

### Fase 11 — Knowledge Bases (índices)

Leia o `index.md` de cada domínio da KB para entender o que está disponível:

```bash
find kb/ -name "index.md" | sort | xargs -I{} sh -c 'echo "=== {} ===" && head -30 {}'
```

Depois leia pelo menos um arquivo de `concepts/` e um de `patterns/` de cada domínio
para entender a profundidade do conhecimento disponível.

Leia também:
- `kb/constitution.md` — regras completas S1–S7
- `kb/collaboration-workflows.md` — protocolos de colaboração
- `kb/task_routing.md` — lógica de roteamento
- `kb/shared/anti-patterns.md` — anti-padrões

### Fase 12 — Skills (índice de SKILL.md)

Para cada domínio de skills, leia o `SKILL.md` raiz:

```bash
find skills/ -name "SKILL.md" -maxdepth 3 | sort | \
  xargs -I{} sh -c 'echo "=== {} ===" && head -20 {}'
```

Aprofunde nas skills mais relevantes ao foco atual (se `--focus` foi passado).

### Fase 13 — Testes

Leia cada arquivo de teste e documente:
- O que testa
- Fixtures e mocks usados
- Casos de borda cobertos
- Invariantes verificadas

```bash
# Ver cobertura atual
python -m pytest --co -q tests/ 2>/dev/null | head -100
```

### Fase 14 — Análise de Dependências e Fluxo

Após ler todos os arquivos:

1. **Mapa de importações circulares**: Verifique onde `settings` é importado; confirme que é sempre local.
2. **Grafo de dependências entre módulos**: Qual módulo depende de qual.
3. **Fluxo completo de uma query**: Trace do `main.py` até a resposta final, passando por cada componente.
4. **Fluxo de lifecycle de sessão**: Do `on_session_start` ao `on_session_end`.
5. **Fluxo de memória**: Captura → Decay → Retrieval → Injection.

---

## Saída Esperada

Ao final de todas as fases, crie o arquivo:

```
output/analyze-project/relatorio_projeto.md
```

Estrutura do relatório:

```markdown
# Relatório de Análise Completa — Data Agents
> Gerado em: <data>

## 1. Sumário Executivo
[Visão geral em 1 parágrafo]

## 2. Estatísticas do Projeto
- Total de arquivos Python: N
- Total de linhas de código: N
- Total de agentes: N
- Total de MCP servers: N
- Total de skills (SKILL.md): N
- Total de arquivos de KB: N
- Total de testes: N
- Cobertura de testes: N%

## 3. Arquitetura — Componentes e Responsabilidades
[Descrição de cada módulo principal com classes e funções chave]

## 4. Agentes — Matriz Completa
[Tabela: nome | tier | model | maxTurns | tools count | mcp_servers | kb_domains | skill_domains]

## 5. MCP Servers — Cobertura de Tools
[Tabela: servidor | tipo | tools count | tools readonly count | requer credencial]

## 6. Hooks — Pipeline de Interceptação
[Tabela: hook | tipo | quando dispara | o que faz | outputs gerados]

## 7. Sistema de Memória — Fluxo Completo
[Descrição do ciclo: extração → armazenamento → decay → retrieval → injeção]

## 8. Fluxo de uma Query — Trace Completo
[Passo a passo detalhado com módulos envolvidos]

## 9. Knowledge Bases — Cobertura por Domínio
[O que cada domínio de KB cobre]

## 10. Skills — Índice Operacional
[Tabela: skill | domínio | para que serve | quais agentes usam]

## 11. Testes — Matriz de Cobertura
[Tabela: módulo | arquivo de teste | casos cobertos | mocks usados]

## 12. Padrões de Código — Convenções Identificadas
[Padrões observados: imports, paths, naming, erros, etc.]

## 13. Dependências Externas
[Tabela: pacote | versão | extra | para que usa]

## 14. Potenciais Gaps e Observações
[O que está faltando, inconsistências encontradas, oportunidades]
```

---

## Modo `--focus`

Se o usuário passar `--focus <módulo>`, aprofunde especificamente:

- `--focus agents` → Leia cada agente do registry completo, extraia system prompt, analise capacidades e gaps
- `--focus hooks` → Trace o pipeline completo de hooks, teste padrões de regex, avalie thresholds
- `--focus memory` → Leia todo o sistema de memória, analise fórmulas de decay, métricas de retrieval
- `--focus mcp` → Analise cada MCP server, liste todas as tools, verifique configurações
- `--focus tests` → Rode os testes, analise cobertura, identifique gaps
- `--focus kb` → Leia todas as KBs, mapeie conceitos cobertos, identifique lacunas
- `--focus skills` → Leia todos os SKILL.md, avalie completude e profundidade
- `--focus workflows` → Analise WF-01 a WF-05, trace context chain, identifique gargalos

---

## Checklist Final

Antes de reportar concluído, confirme:

- [ ] Todos os 12+ agentes do registry foram lidos e documentados
- [ ] Todos os 13+ MCP servers foram analisados (server_config.py + server.py)
- [ ] Todos os 11 hooks foram lidos e comportamentos documentados
- [ ] Todo o sistema de memória (8 arquivos) foi analisado
- [ ] Todos os handlers de slash commands foram lidos
- [ ] Todos os módulos de config foram lidos
- [ ] Índices de KB foram lidos (ao menos um conceito e um pattern por domínio)
- [ ] Índice de skills foi gerado (pelo menos SKILL.md raiz de cada skill)
- [ ] Todos os 40+ arquivos de teste foram identificados e documentados
- [ ] Relatório salvo em `output/analyze-project/relatorio_projeto.md`
- [ ] Nenhum diretório ou subdiretório foi ignorado sem razão explícita

Se qualquer item estiver incompleto, **continue lendo** antes de reportar pronto.
