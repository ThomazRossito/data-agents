# Data Agents — Guia para Claude Code

Sistema multi-agente construído sobre o **Claude Agent SDK** da Anthropic com integração
nativa via MCP ao **Databricks** e **Microsoft Fabric**. Orquestra 13 agentes especialistas
em Engenharia, Qualidade, Governança e Análise de Dados.

---

## Como Rodar

```bash
# Setup (uma vez)
pip install -e ".[dev,ui,monitoring]"
cp .env.example .env   # preencher credenciais

# Execução
python main.py                        # CLI interativo
python main.py "liste tabelas silver" # single-query
./start.sh                            # Web UI (Chat + Monitoring)
./start.sh --chat-only                # Só o chat Chainlit (porta 8503)

# Qualidade
make test        # pytest com cobertura (mínimo 80%)
make lint        # ruff check
make format      # ruff format
make type-check  # mypy
make health-databricks
make health-fabric
```

---

## Arquitetura de Alto Nível

```
Usuário → main.py / ui/chainlit_app.py
  └─► Supervisor (claude-opus-4-6, sem MCP direto)
        ├─► business-analyst   [T3] — intake de requisitos, /brief
        ├─► sql-expert         [T1] — SQL, schemas, catálogos
        ├─► spark-expert       [T1] — PySpark, DLT, Delta Lake
        ├─► python-expert      [T1] — Python puro: pacotes, APIs, CLIs, testes
        ├─► pipeline-architect [T1] — ETL/ELT cross-platform
        ├─► migration-expert   [T1] — Migração SQL Server/PostgreSQL → Databricks/Fabric
        ├─► dbt-expert         [T2] — dbt Core: models, testes, snapshots
        ├─► data-quality-steward [T2] — validação, profiling, SLA
        ├─► governance-auditor   [T2] — auditoria, LGPD, linhagem
        ├─► semantic-modeler     [T2] — modelos semânticos, DAX, Genie
        ├─► business-monitor     [T2] — Q&A interativo sobre alertas (daemon em `scripts/monitor_daemon.py`)
        └─► geral                [T3] — perguntas conceituais, zero MCP (Haiku 4.5)
```

**Regra central:** O Supervisor **nunca** executa código, acessa MCP ou gera SQL/PySpark.
Sempre delega. Agentes especialistas executam com seus MCPs pré-configurados.

---

## Estrutura de Diretórios (críticos)

```
agents/
  registry/       ← definições declarativas dos agentes (.md + YAML frontmatter)
  loader.py       ← carrega agentes do registry, resolve tool aliases
  supervisor.py   ← monta ClaudeAgentOptions com todos os agentes + hooks + MCPs
  prompts/        ← system prompt do Supervisor
  cache_prefix.md ← prefixo byte-idêntico injetado em TODOS os agentes (prompt caching)

mcp_servers/
  databricks/     ← MCP oficial Databricks (50+ tools)
  databricks_genie/ ← MCP customizado: Genie Conversation API
  fabric/         ← MCP oficial Microsoft Fabric
  fabric_community/ ← MCP comunidade: linhagem, dependências
  fabric_sql/     ← MCP customizado: SQL Analytics Endpoint via TDS
  fabric_rti/     ← MCP Fabric Real-Time Intelligence (KQL/Kusto)
  context7/       ← Docs atualizadas de bibliotecas (free, sem credenciais)
  tavily/         ← Busca web para LLMs (free: 1k créditos/mês)
  github/         ← GitHub: repos, issues, PRs (free via PAT)
  firecrawl/      ← Web scraping estruturado (free: 500 créditos/mês)
  postgres/       ← Queries readonly em PostgreSQL (free, open source)
  memory_mcp/     ← Knowledge graph de entidades (free, sem credenciais)
  migration_source/ ← MCP customizado: DDL/schema extraction de SQL Server/PostgreSQL
  _template/      ← Template para novos MCPs

config/
  settings.py     ← Pydantic BaseSettings — todas as credenciais + validação
  mcp_servers.py  ← Registry centralizado de MCP servers (ALL_MCP_CONFIGS)

hooks/            ← Hooks PreToolUse / PostToolUse
kb/               ← Knowledge Bases (referência, lida pelos agentes)
skills/           ← Skills operacionais (playbooks, lidos pelos agentes)
tests/            ← pytest — atualizar quando adicionar agentes/MCPs
```

---

## Como Adicionar um Novo Agente

**Crie `agents/registry/<nome>.md`** — o loader carrega automaticamente, sem tocar código Python.

```yaml
---
name: nome-do-agente
description: "Descrição objetiva. Use para: [casos de uso]. Invoque quando: [trigger]."
model: claude-sonnet-4-6        # ou claude-opus-4-6 para T1 complexo
tools: [Read, Write, Grep, Glob, databricks_readonly, context7_all]
mcp_servers: [databricks, context7]
kb_domains: [databricks, sql-patterns]   # injeta index.md automaticamente
skill_domains: [databricks, patterns]    # injeta índice de SKILL.md disponíveis
tier: T2                                  # T1 | T2 | T3
---
# Nome do Agente

## Identidade e Papel
...
```

**Tiers:**
| Tier | Modelo padrão | maxTurns | Effort | Uso |
|------|---------------|----------|--------|-----|
| T1 | claude-opus-4-6 | 20 | high | Core: pipelines complexos, multi-platform |
| T2 | claude-sonnet-4-6 | 12 | medium | Especializados: qualidade, governança, semântica |
| T3 | claude-opus-4-6 | 5 | low | Conversacionais: sem MCP, intake de requisitos |

**Após criar o agente:**
1. Adicionar ao `SUPERVISOR_SYSTEM_PROMPT` em `agents/prompts/supervisor_prompt.py`
2. Atualizar testes em `tests/test_agents.py` se houver invariantes específicas

---

## Como Adicionar um Novo MCP

Seguir os 5 passos abaixo **sempre na mesma ordem**:

### Passo 1 — Criar `mcp_servers/<nome>/`
```bash
mkdir mcp_servers/<nome>
touch mcp_servers/<nome>/__init__.py
```

### Passo 2 — Criar `mcp_servers/<nome>/server_config.py`
```python
def get_<nome>_mcp_config() -> dict:
    from config.settings import settings  # importação local — evita circular import
    return {
        "<nome>": {
            "type": "stdio",
            "command": "uvx",          # ou "npx"
            "args": ["pacote-mcp"],
            "env": {"API_KEY": settings.<campo>},
        }
    }

MCP_TOOLS = ["mcp__<nome>__tool_name", ...]
MCP_READONLY_TOOLS = [...]  # subconjunto opcional
```

### Passo 3 — Registrar em `config/mcp_servers.py`
```python
from mcp_servers.<nome>.server_config import get_<nome>_mcp_config, MCP_TOOLS

ALL_MCP_CONFIGS = {
    ...,
    "<nome>": get_<nome>_mcp_config,
}
```
> Se o MCP não requer credenciais (ex: context7, memory_mcp), adicionar ao `ALWAYS_ACTIVE_MCPS` em `build_mcp_registry()`.

### Passo 4 — Adicionar credenciais em `config/settings.py`
```python
# Dentro da classe Settings:
meu_mcp_api_key: str = ""
```
E adicionar à validação em `validate_platform_credentials()` e ao `startup_diagnostics()`.

### Passo 5 — Adicionar aliases em `agents/loader.py` → `MCP_TOOL_SETS`
```python
"<nome>_all": MCP_TOOLS,
"<nome>_readonly": MCP_READONLY_TOOLS,  # se houver
```

**E também:** atualizar `tests/test_settings.py` — se o MCP não requer credenciais, adicionar ao `CREDENTIAL_FREE_MCPS` nos testes.

---

## Convenção de Nomes de Tools MCP

Formato: `mcp__<server_key>__<tool_name>`

O `<server_key>` é a chave usada em `ALL_MCP_CONFIGS`. Exemplos:
- `mcp__databricks__execute_sql`
- `mcp__fabric_sql__fabric_sql_list_tables`
- `mcp__context7__get-library-docs`   ← hífens preservados
- `mcp__memory_mcp__read_graph`

---

## Tool Aliases Disponíveis (agents/loader.py → MCP_TOOL_SETS)

Use estes aliases no frontmatter `tools:` dos agentes em vez de listar cada tool:

| Alias | Descrição |
|-------|-----------|
| `databricks_all` | Todas as tools do Databricks |
| `databricks_readonly` | Só leitura: list_, get_, describe_, sample_, export_, read_ |
| `databricks_aibi` | Genie + Dashboards + KA + MAS |
| `databricks_serving` | Model Serving endpoints |
| `databricks_compute` | Clusters, execute_code, wait_for_run |
| `databricks_genie_all` | Genie Conversation + Space Management |
| `databricks_genie_readonly` | Genie só leitura |
| `fabric_all` | Fabric REST API + Community MCP |
| `fabric_readonly` | Fabric só leitura |
| `fabric_rti_all` | RTI/Kusto: todas |
| `fabric_rti_readonly` | RTI só leitura |
| `fabric_sql_all` | SQL Analytics Endpoint: todas |
| `fabric_sql_readonly` | SQL Analytics só leitura |
| `context7_all` | resolve-library-id + get-library-docs |
| `tavily_all` | tavily-search + tavily-extract |
| `github_all` | Acesso completo: repos, issues, PRs |
| `github_readonly` | GitHub só leitura |
| `firecrawl_all` | Scrape, crawl, search, extract |
| `postgres_all` | query (SELECT readonly) |
| `memory_mcp_all` | Knowledge graph: leitura + escrita |
| `memory_mcp_readonly` | Knowledge graph: só leitura |
| `fabric_semantic_all` | Fabric Semantic Models: introspecção TMDL, DAX, RLS |
| `fabric_semantic_readonly` | Fabric Semantic Models: só leitura |
| `migration_source_all` | SQL Server/PostgreSQL: DDL, views, procedures, stats |

---

## MCPs por Agente (estado atual)

| Agente | MCPs Configurados |
|--------|-------------------|
| business-analyst | tavily, firecrawl |
| spark-expert | context7 |
| sql-expert | databricks, databricks_genie, fabric, fabric_community, fabric_sql, fabric_rti, context7, postgres |
| pipeline-architect | databricks, databricks_genie, fabric, fabric_community, fabric_sql, fabric_rti, context7, github, firecrawl, memory_mcp |
| dbt-expert | context7, postgres |
| data-quality-steward | databricks, fabric, fabric_community, fabric_rti, postgres |
| governance-auditor | databricks, fabric, fabric_community, tavily, postgres, memory_mcp |
| semantic-modeler | databricks, databricks_genie, fabric, fabric_community, fabric_semantic, fabric_sql, context7 |
| migration-expert | migration_source, databricks, fabric, fabric_sql, context7 |
| python-expert | context7 |
| geral | *(nenhum — resposta direta sem MCP)* |

> MCPs sem credenciais (context7, memory_mcp) são ativados automaticamente.
> Os demais requerem variáveis de ambiente configuradas no `.env`.
>
> **Nota:** refresh de Skills (`/skill`) não é mais um agente. Rodar via
> `scripts/refresh_skills.py` — Anthropic Messages API direta + tool nativo
> `web_search` (sem MCP).

---

## Hooks (hooks/)

| Hook | Tipo | O que faz |
|------|------|-----------|
| `security_hook.py` | PreToolUse (Bash) | Bloqueia 22 padrões destrutivos (rm -rf, DROP, git reset --hard, etc.) |
| `security_hook.py` | PreToolUse (all) | Detecta SELECT * sem WHERE/LIMIT |
| `audit_hook.py` | PostToolUse | Loga todas as tool calls no JSONL de auditoria (6 categorias de erro) |
| `workflow_tracker.py` | PostToolUse | Rastreia delegações de agentes e Clarity Checkpoint |
| `cost_guard_hook.py` | PostToolUse | Classifica operações HIGH/MEDIUM/LOW e alerta após 5 HIGH |
| `output_compressor_hook.py` | PostToolUse | Comprime outputs verbosos antes de enviar ao modelo |
| `session_logger.py` | PostToolUse | Registra métricas finais de custo/turns/duração por sessão |
| `memory_hook.py` | PostToolUse | Captura contexto da sessão para memória persistente |
| `context_budget_hook.py` | PostToolUse | Monitora tokens acumulados; avisa a 80% e 95% do limite |
| `checkpoint.py` | — | Save/restore do estado da sessão para retomada |
| `session_lifecycle.py` | SessionStart/End | Injeção de memórias, config snapshot e flush ao encerrar |

---

## Sistema de Memória (dois layers)

**Layer 1 — `memory/` (episódica, existente):**
Captura fatos da sessão automaticamente via hook. Aplica decay temporal. Retrieval semântico
antes de cada query ao Supervisor. Foco: "o que aconteceu nesta conversa/projeto".

**Layer 2 — `memory_mcp/` (knowledge graph, novo):**
Grafo persistente de entidades nomeadas (tabelas, pipelines, times, decisões) e suas relações.
Gerenciado manualmente pelos agentes. Foco: "o que existe e como se relaciona".
Persistência: `memory.json` no diretório de execução.

Controle via `.env`:
```
MEMORY_ENABLED=true
MEMORY_RETRIEVAL_ENABLED=true
MEMORY_CAPTURE_ENABLED=true
```

---

## Slash Commands Disponíveis

| Comando | Agente Alvo | Uso |
|---------|-------------|-----|
| `/brief <texto>` | business-analyst | Converte transcript/briefing em backlog estruturado |
| `/sql <query>` | sql-expert | SQL direto sem passar pelo Supervisor |
| `/spark <tarefa>` | spark-expert | PySpark/DLT direto |
| `/pipeline <tarefa>` | pipeline-architect | Pipeline ETL direto |
| `/dbt <tarefa>` | dbt-expert | dbt Core direto: models, testes, snapshots, docs |
| `/fabric <tarefa>` | pipeline-architect | Foco em Fabric |
| `/plan <objetivo>` | Supervisor + DOMA Full | Planejamento com thinking habilitado (8k tokens) |
| `/quality <tarefa>` | data-quality-steward | Qualidade de dados direta |
| `/governance <tarefa>` | governance-auditor | Governança/auditoria direta |
| `/semantic <tarefa>` | semantic-modeler | Modelagem semântica direta |
| `/migrate <fonte> para <destino>` | migration-expert | Assessment e migração de banco relacional para Databricks/Fabric |
| `/python <tarefa>` | python-expert | Python puro: pacotes, testes, APIs, CLIs, automação |
| `/genie <tarefa>` | semantic-modeler | Criar/atualizar Genie Spaces no Databricks |
| `/dashboard <tarefa>` | semantic-modeler | Criar/publicar AI/BI Dashboards |
| `/monitor <pergunta>` | business-monitor | Q&A sobre alertas do daemon de monitoramento |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/health` | — | Status das plataformas configuradas |
| `/status` | — | Estado da sessão atual |
| `/memory <query>` | — | Consulta memória persistente |
| `/sessions [all\|<id>]` | — | Lista sessões registradas (transcript + checkpoint) |
| `/resume [last\|<id>]` | — | Retoma sessão anterior reconstruindo contexto do transcript |
| `/party <query>` | — | Multi-agente paralelo: perspectivas independentes (flags: --quality, --arch, --engineering, --migration, --full) |
| `/workflow <wf-id> <query>` | — | Executa workflow colaborativo pré-definido (WF-01 a WF-05) com context chain |
| `/geral <pergunta>` | — | Resposta direta sem Supervisor (zero agentes, ~95% mais barato) |

---

## Convenções de Código

**Importações circulares:** Sempre importar `settings` localmente dentro das funções:
```python
def get_mcp_config() -> dict:
    from config.settings import settings  # ← sempre local
    return {"key": settings.value}
```

**Novos campos em `Settings`:** Adicionar com default `""` e documentar com comentário
explicando: o que é, como obter, plano gratuito se houver.

**Agentes:** Tier T1 usa `claude-opus-4-6`, tiers T2/T3 usam `claude-sonnet-4-6`
(salvo override via `TIER_MODEL_MAP` no `.env`).

**Testes:** Ao adicionar um agente, verificar se algum teste em `test_agents.py` precisa
de atualização. Ao adicionar um MCP sem credenciais, adicionar ao `CREDENTIAL_FREE_MCPS`
em `test_settings.py`.

**Cache prefix (`agents/cache_prefix.md`):** NUNCA adicionar timestamps, IDs de sessão
ou qualquer conteúdo dinâmico. O arquivo deve ser byte-idêntico a cada execução.

---

## Constituição — Regras Invioláveis (resumo)

| ID | Regra |
|----|-------|
| S1 | Supervisor nunca gera SQL/PySpark diretamente |
| S2 | Supervisor nunca acessa MCP diretamente |
| S3 | KB-First: consultar `kb/` ANTES de planejar qualquer tarefa |
| S4 | Apresentar plano ao usuário ANTES de delegação múltipla |
| S5 | Nunca expor tokens/secrets em artefatos ou respostas |
| S6 | Qualidade → data-quality-steward. Governança → governance-auditor. NUNCA pipeline-architect. |
| S7 | Clarity Checkpoint antes de tarefas complexas (score mínimo 3/5) |

Arquivo completo: `kb/constitution.md`

---

## Variáveis de Ambiente (.env)

Copiar `.env.example` e preencher. Variáveis críticas:

```bash
ANTHROPIC_API_KEY=sk-ant-...      # obrigatório
DATABRICKS_HOST=https://adb-...   # obrigatório para Databricks
DATABRICKS_TOKEN=dapi...
AZURE_TENANT_ID=...               # obrigatório para Fabric
FABRIC_WORKSPACE_ID=...

# MCPs externos (opcionais mas recomendados)
TAVILY_API_KEY=tvly-...           # busca web
GITHUB_PERSONAL_ACCESS_TOKEN=...  # repos e PRs
FIRECRAWL_API_KEY=fc-...          # web scraping
POSTGRES_URL=postgresql://...     # banco PostgreSQL

# context7 e memory_mcp: sem credenciais, ativos automaticamente
```

---

## Mapa Completo de Arquivos e Módulos

> Use esta seção como guia de navegação. Antes de qualquer tarefa que envolva código,
> leia os arquivos relevantes listados abaixo. Para uma varredura total do projeto,
> execute o slash command `/analyze-project`.

### Raiz do Projeto

| Arquivo | Propósito |
|---------|-----------|
| `main.py` | Entry point CLI — inicializa Supervisor, lida com args, gerencia sessão e loop |
| `start.sh` / `start_chainlit.sh` | Scripts que sobem Chainlit + processo de monitoramento |
| `pyproject.toml` | Dependências, extras `[dev]` `[ui]` `[monitoring]`, config ruff/mypy/pytest |
| `Makefile` | Targets: `test`, `lint`, `format`, `type-check`, `health-databricks`, `health-fabric` |
| `chainlit.md` | Página de boas-vindas do Chat UI (Chainlit) |
| `databricks.yml` | Bundle config para Databricks Asset Bundles (DAB) |
| `.env.example` | Template de variáveis de ambiente |
| `.mcp.json` | MCP servers para uso direto no Claude Code Desktop |
| `.pre-commit-config.yaml` | Hooks de pre-commit: ruff, mypy, pytest smoke |
| `README.md` | Documentação pública com badges, quickstart e overview |
| `PRODUCT.md` | Visão de produto, roadmap e decisões estratégicas |
| `CHANGELOG.md` | Histórico de versões e mudanças |

### agents/ — Orquestração e Carregamento

| Arquivo | Classes / Funções chave | Propósito |
|---------|------------------------|-----------|
| `loader.py` | `AgentMeta`, `preload_registry()`, `load_agent()`, `load_all_agents()`, `inject_memory_context()`, `MCP_TOOL_SETS` | Carrega `.md` do registry, resolve aliases, injeta KB + Skills + cache prefix |
| `supervisor.py` | `build_supervisor_options()` | Monta `ClaudeAgentOptions` com agentes + hooks + MCPs + thinking config |
| `delegation.py` | `DelegationRouter`, `route_to_agent()` | Roteamento declarativo de delegações |
| `delegation_map.yaml` | — | YAML: padrões de intent → agente alvo |
| `mlflow_wrapper.py` | `MLflowAgentWrapper` | Wrapper para logging de experimentos com MLflow |
| `cache_prefix.md` | — | Prefixo byte-idêntico injetado em TODOS os agentes (prompt caching -40% custo) |
| `prompts/supervisor_prompt.py` | `SUPERVISOR_SYSTEM_PROMPT` | System prompt do Supervisor: regras, tiers, delegação |
| `registry/*.md` | Frontmatter YAML + corpo Markdown | Definição declarativa de cada agente |
| `registry/_template.md` | — | Template para criar novos agentes |

**13 agentes no registry:** `business-analyst`, `business-monitor`, `data-quality-steward`,
`dbt-expert`, `geral`, `governance-auditor`, `migration-expert`, `pipeline-architect`,
`python-expert`, `semantic-modeler`, `spark-expert`, `sql-expert`.

### config/ — Configuração Central

| Arquivo | Classes / Funções chave | Propósito |
|---------|------------------------|-----------|
| `settings.py` | `Settings(BaseSettings)`, `validate_platform_credentials()`, `startup_diagnostics()` | Todas as credenciais, tier maps, feature flags via Pydantic |
| `mcp_servers.py` | `ALL_MCP_CONFIGS`, `ALWAYS_ACTIVE_MCPS`, `build_mcp_registry()` | Registry de todos os MCP servers; detecta quais têm credenciais |
| `commands.yaml` | — | Mapeamento slash commands → handlers Python |
| `exceptions.py` | `DataAgentsError`, `MCPConnectionError`, `AgentDelegationError` | Hierarquia de exceções |
| `logging_config.py` | `setup_logging()` | structlog JSONL → `logs/app.jsonl` |
| `snapshot.py` | `ConfigSnapshot`, `save_snapshot()`, `load_snapshot()` | Estado de configuração entre sessões |

**Campos críticos em `Settings`:** `default_model`, `tier_model_map`, `tier_turns_map`,
`tier_effort_map`, `max_turns`, `max_budget_usd`, `agent_permission_mode`,
`memory_enabled`, `memory_retrieval_enabled`, `memory_capture_enabled`,
`inject_kb_index`.

### mcp_servers/ — Servidores MCP

Cada subdiretório: `__init__.py` + `server_config.py` (+ `server.py` para MCPs customizados).

| Diretório | Tipo | Ferramentas representativas |
|-----------|------|-----------------------------|
| `databricks/` | Oficial (uvx) | `execute_sql`, `list_catalogs`, `create_job`, `get_cluster` — 50+ tools |
| `databricks_genie/` | Customizado (Python FastAPI-MCP) | `create_space`, `ask_question`, `get_conversation` |
| `fabric/` | Oficial (dotnet) | Workspace, Lakehouse, Pipeline, Semantic Model ops |
| `fabric_rti/` | Oficial (uvx) | KQL/Kusto queries em Real-Time Intelligence |
| `fabric_sql/` | Customizado (Python pyodbc) | SQL Analytics Endpoint via TDS |
| `fabric_semantic/` | Customizado (Python) | Introspecção TMDL, DAX INFO functions, RLS |
| `context7/` | Público (npx) | `resolve-library-id`, `get-library-docs` — sem credenciais |
| `tavily/` | Público (uvx) | `tavily-search`, `tavily-extract` |
| `github/` | Público (uvx) | Repos, issues, PRs, commits |
| `firecrawl/` | Público (uvx) | Scrape, crawl, search, extract |
| `postgres/` | Público (npx) | Queries SELECT readonly |
| `memory_mcp/` | Público (npx) | Knowledge graph persistente — sem credenciais |
| `migration_source/` | Customizado (Python) | DDL + schema extraction de SQL Server/PostgreSQL |

### hooks/ — Interceptadores de Tool Calls

| Arquivo | Tipo | Função principal | Comportamento |
|---------|------|-----------------|---------------|
| `security_hook.py` | PreToolUse | `block_destructive_commands()` | Bloqueia 22 padrões (rm -rf, DROP TABLE, git reset --hard, etc.) |
| `security_hook.py` | PreToolUse | `check_sql_cost()` | Detecta SELECT * sem WHERE/LIMIT em qualquer tool |
| `audit_hook.py` | PostToolUse | `audit_tool_usage()` | Loga em `logs/audit.jsonl`: agente, tool, status, duração |
| `cost_guard_hook.py` | PostToolUse | `log_cost_generating_operations()` | HIGH/MEDIUM/LOW; alerta após 5 HIGH consecutivos |
| `output_compressor_hook.py` | PostToolUse | `compress_tool_output()` | Reduz outputs acima do threshold antes de enviar ao modelo |
| `workflow_tracker.py` | Pre+Post | `pre_track_workflow_events()`, `track_workflow_events()` | Rastreia delegações, Clarity Checkpoint, progress callbacks |
| `memory_hook.py` | PostToolUse | `capture_session_context()` | Acumula fatos da sessão; flush ao encerrar |
| `context_budget_hook.py` | PostToolUse | `track_context_budget()` | Avisa a 80% e ERROR a 95% do context window |
| `session_logger.py` | PostToolUse | `log_session_metrics()` | Custo, turns, duração por sessão em `logs/sessions.jsonl` |
| `session_lifecycle.py` | SessionStart/End | `on_session_start()`, `on_session_end()` | Injeta memórias no início; config snapshot; flush ao encerrar |
| `checkpoint.py` | — | `save_checkpoint()`, `load_checkpoint()` | Serializa/restaura estado da sessão |
| `transcript_hook.py` | PostToolUse | `save_transcript()` | Persiste transcript em `logs/sessions/<id>.jsonl` |

### memory/ — Memória Episódica (Layer 1)

| Arquivo | Classes / Funções chave | Propósito |
|---------|------------------------|-----------|
| `store.py` | `MemoryStore`, `save()`, `list_all()`, `get()` | Persistência de memórias em JSON |
| `retrieval.py` | `retrieve_relevant_memories()`, `format_memories_for_injection()` | Busca semântica via Sonnet lateral |
| `extractor.py` | `extract_facts_from_session()` | Extrai fatos estruturados do transcript |
| `compiler.py` | `compile_memories()` | Consolida e deduplica memórias |
| `decay.py` | `apply_decay()` | Reduz peso de memórias antigas (temporal decay) |
| `types.py` | `Memory`, `MemoryStore`, `MemoryFact` | Dataclasses e tipos do sistema |
| `telemetry.py` | `log_memory_event()` | Métricas de uso da memória |
| `lint.py` | `lint_memories()` | Valida integridade das memórias salvas |

### commands/ — Handlers de Slash Commands

| Arquivo | Handler | Slash Command |
|---------|---------|---------------|
| `parser.py` | `parse_command()`, `CommandRegistry` | Parsing genérico de qualquer `/comando <args>` |
| `geral.py` | `handle_geral()` | `/geral` — resposta direta sem Supervisor (~95% mais barato) |
| `monitor.py` | `handle_monitor()` | `/monitor` — Q&A sobre alertas do daemon |
| `party.py` | `handle_party()` | `/party` — multi-agente paralelo com flags: --quality, --arch, --engineering, --full |
| `sessions.py` | `handle_sessions()`, `handle_resume()` | `/sessions` + `/resume` — listagem e retomada |
| `workflow.py` | `handle_workflow()` | `/workflow` — executa workflows WF-01 a WF-05 |

### compression/ — Compressão de Outputs de Tool

| Arquivo | Classes / Funções chave | Propósito |
|---------|------------------------|-----------|
| `hook.py` | `compress_tool_output()` | Hook que detecta e comprime outputs grandes |
| `strategies.py` | `TruncationStrategy`, `SummaryStrategy`, `JSONPruningStrategy` | Estratégias por tipo de output |
| `metrics.py` | `CompressionMetrics`, `log_compression_event()` | Métricas de compressão |
| `constants.py` | `MAX_OUTPUT_TOKENS`, `COMPRESSION_THRESHOLD` | Limites e thresholds |

### workflow/ — Workflows Colaborativos (WF-01 a WF-05)

| Arquivo | Classes / Funções chave | Propósito |
|---------|------------------------|-----------|
| `dag.py` | `WorkflowDAG`, `WorkflowStep`, `build_dag()` | Grafo acíclico de dependências entre steps |
| `executor.py` | `WorkflowExecutor`, `execute_workflow()` | Executa steps com context chain entre agentes |
| `tracker.py` | `WorkflowTracker`, `log_step()` | Rastreia execução em `logs/workflows.jsonl` |

### ui/ — Interface Web (Chainlit)

| Arquivo | Funções chave | Propósito |
|---------|--------------|-----------|
| `chainlit_app.py` | `@cl.on_chat_start`, `@cl.on_message` | App principal: sessão, streaming, slash commands na UI |
| `ui_config.py` | `UIConfig`, `THEME`, `AVATAR_MAP` | Tema, avatares por agente, labels |
| `exporter.py` | `export_session()`, `to_markdown()`, `to_html()` | Exporta sessão para download |

### utils/ — Utilitários Compartilhados

| Arquivo | Funções chave | Propósito |
|---------|--------------|-----------|
| `frontmatter.py` | `parse_yaml_frontmatter()` | Parser de YAML frontmatter dos `.md` dos agentes |
| `tokenizer.py` | `count_tokens()`, `estimate_cost()` | Contagem de tokens e estimativa de custo |
| `summarizer.py` | `summarize_text()` | Sumarização via Haiku para compressão de contexto |
| `monitor_alerter.py` | `send_alert()`, `AlertChannel` | Envio de alertas do daemon de monitoramento |

### tests/ — Cobertura de Testes (mínimo 80%)

| Arquivo de Teste | O que cobre |
|-----------------|-------------|
| `test_agents.py` | Carregamento de agentes, campos obrigatórios, model routing por tier |
| `test_supervisor.py` | Build de ClaudeAgentOptions, hooks registrados, MCP registry |
| `test_hooks.py` | Security (22 padrões), audit, cost guard, output compressor |
| `test_settings.py` | Credenciais, CREDENTIAL_FREE_MCPS, tier maps |
| `test_mcp_configs.py` | Formato de configuração de todos os MCPs |
| `test_memory_store.py` | Persistência de memórias |
| `test_memory_retrieval.py` | Busca semântica de memórias |
| `test_memory_decay.py` | Temporal decay de memórias |
| `test_memory_extractor.py` | Extração de fatos do transcript |
| `test_memory_compiler.py` | Consolidação e deduplicação |
| `test_memory_lint.py` | Validação de integridade |
| `test_commands.py` | Parser e handlers de slash commands |
| `test_workflow.py` | DAG, executor, tracker |
| `test_functional.py` | Integração end-to-end (smoke tests) |
| `test_delegation.py` | Roteamento declarativo de delegações |
| `test_checkpoint.py` | Save/restore de sessão |
| `test_sessions_command.py` | Listagem e retomada de sessões |
| `test_agent_preload.py` | Fase rápida de preload (AgentMeta) |
| `test_*_server.py` | MCPs customizados: genie, fabric_sql, fabric_semantic, migration_source |

### kb/ — Knowledge Bases

Estrutura: `kb/<domain>/index.md` + `concepts/*.md` + `patterns/*.md`

| Domínio | Conteúdo |
|---------|---------|
| `databricks/` | Unity Catalog, Delta Lake, Jobs, Compute, AI/ML |
| `fabric/` | Lakehouse, RTI, Direct Lake, cross-platform |
| `data-quality/` | Expectations, profiling, drift detection, SLA |
| `governance/` | Acesso, auditoria, compliance LGPD, linhagem, PII |
| `pipeline-design/` | Medallion, ETL/ELT, orquestração multi-plataforma |
| `spark-patterns/` | Delta Lake, streaming, performance, SDP rules, LakeFlow |
| `sql-patterns/` | DDL, dialetos, star schema, query optimization |
| `semantic-modeling/` | DAX, Direct Lake, Metric Views, modelos semânticos |
| `python-patterns/` | Concorrência, type system, testing, APIs, CLI, packaging |
| `migration/` | Guias SQL Server/PostgreSQL → Databricks/Fabric |
| `constitution.md` | Regras invioláveis S1–S7 |
| `shared/anti-patterns.md` | Anti-padrões a evitar em todo o sistema |

### skills/ — Skills Operacionais (playbooks para os agentes)

| Domínio | Skills (SKILL.md) disponíveis |
|---------|-----------------------------|
| `databricks/` | agent-bricks, ai-functions, aibi-dashboards, app-python, bundles, config, dbsql, docs, execution-compute, genie, iceberg, jobs, lakebase-autoscale, lakebase-provisioned, metric-views, mlflow-evaluation, model-serving, python-sdk, spark-declarative-pipelines, spark-structured-streaming, synthetic-data-gen, unity-catalog, unstructured-pdf-generation, vector-search, zerobus-ingest, spark-python-data-source |
| `fabric/` | cross-platform, data-factory, deployment-pipelines, direct-lake, eventhouse-rti, git-integration, medallion, monitoring-dmv, notebook-manager, workspace-manager |
| `migration/` | Skill completa de assessment e migração |
| `patterns/` | data-quality, pipeline-design, spark-patterns, sql-generation, star-schema-design |
| `python/` | fastapi-patterns, pandas-polars-patterns, pytest-patterns, python-packaging |

---

## Fluxo de Dados — Como uma Query Percorre o Sistema

```
1. Usuário → main.py ou chainlit_app.py
2. inject_memory_context() enriquece system prompt com memórias relevantes
3. Supervisor recebe query + contexto de memória
4. Supervisor lê kb/ e avalia Clarity Checkpoint (mínimo 3/5)
5. Supervisor delega ao agente via tool Agent()
6. Hooks PreToolUse: security → sql_cost check
7. Agente especialista executa com seus MCPs
8. Hooks PostToolUse: audit → cost_guard → workflow_tracker → memory → context_budget → compress
9. Resposta retorna ao Supervisor, que sintetiza para o usuário
10. session_lifecycle.on_session_end(): flush memória + config snapshot
```

---

## Anti-Padrões de Código — NUNCA Fazer

```python
# ❌ Import global de settings (causa circular import)
from config.settings import settings  # no topo do módulo

# ✅ Import local dentro da função
def get_config():
    from config.settings import settings
    return settings.value

# ❌ Caminho relativo (falha quando cwd ≠ raiz do projeto)
Path("output/meu.md").write_text("...")

# ✅ Caminho absoluto
project_root = Path(__file__).parent.parent
(project_root / "output/meu.md").write_text("...")

# ❌ cache_prefix.md com conteúdo dinâmico (invalida prompt cache)
# agents/cache_prefix.md NUNCA deve conter timestamps, IDs ou estados variáveis

# ❌ Supervisor executando SQL/PySpark/MCP diretamente (viola S1, S2)
# Sempre delegar ao agente especialista correto
```
