# Data Agents — Guia para Claude Code

Sistema multi-agente construído sobre o **Claude Agent SDK** da Anthropic com integração
nativa via MCP ao **Databricks** e **Microsoft Fabric**. Orquestra 12 agentes especialistas
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
./start.sh --chat-only                # Só o chat (porta 8502)

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
Usuário → main.py / ui/chat.py / ui/chainlit_app.py
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
        ├─► skill-updater        [T2] — refresh de Skills operacionais
        └─► geral                [T3] — perguntas conceituais, zero MCP
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
skill_domains: [databricks, root]        # injeta índice de SKILL.md disponíveis
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
| skill-updater | context7, tavily, firecrawl |
| geral | *(nenhum — resposta direta sem MCP)* |

> MCPs sem credenciais (context7, memory_mcp) são ativados automaticamente.
> Os demais requerem variáveis de ambiente configuradas no `.env`.

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
| `/skill [domínio]` | skill-updater | Atualiza Skills com documentação recente via context7/tavily |
| `/genie <tarefa>` | semantic-modeler | Criar/atualizar Genie Spaces no Databricks |
| `/dashboard <tarefa>` | semantic-modeler | Criar/publicar AI/BI Dashboards |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/health` | — | Status das plataformas configuradas |
| `/status` | — | Estado da sessão atual |
| `/memory <query>` | — | Consulta memória persistente |
| `/party <query>` | — | Multi-agente paralelo: perspectivas independentes (flags: --quality, --arch, --full) |
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
