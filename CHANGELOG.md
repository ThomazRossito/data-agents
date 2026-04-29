# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

Formato: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) | [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Não liberado]

### A fazer

- Rollback com persistência de estado em workflows (hoje o partial não é salvo em disco)
- Cache de skills com invalidação por mtime (hoje é permanente na sessão)
- Comprimir KB pesado (lakehouse_engineer ~17k, pipeline_architect ~14k) antes de injetar
- Dedup de memórias em `memory/extractor.py` (hoje regex frágil + sem dedup)

---

## [0.4.1] — 2026-04-28

Hardening residual após segundo round de auditoria. Fecha itens deixados em aberto pelo
`[0.4.0]`: dead config no Supervisor, regex de KB com falsos positivos, race condition
no Chainlit, deprecation de asyncio, e sincronização de docs.

### Corrigido

#### Supervisor sem KB pesado por engano (`agents/registry/supervisor.md`)

- `kb_domains: []` (era lista de 16 domínios ~32k tokens)
- O Supervisor já usa `_load_kb_for_task` per-task; a lista global era dead config que
  poderia explodir custo se alguém invocasse `_load_kb_context("supervisor")` direto

#### Regex word-boundary em `_load_kb_for_task` (`agents/supervisor.py`)

- Migrado de `any(k in task_lower for k in ...)` para `re.search(r"\b...\b", ...)`
- "model"/"transform" não disparam mais `pipeline-design` em qualquer query
- "workflow" não dispara mais `orchestration` indiscriminadamente
- "dag" só casa como palavra isolada (antes casava em "drag", "dagger" etc.)
- Dedup de domínios preservando ordem

#### `_TABLE_CREATION_PATTERN` mais restrito

- Antes: "como criar uma tabela com SCD2?" disparava Naming Guard (T2 + MCP)
- Agora aceita apenas: `CREATE TABLE`, intent verb forte (`crie`/`vou criar`), ou
  `criar tabela <schema.tabela>` com nome qualificado

#### Frontmatter `model:` honrado pelo loader (`agents/loader.py`, `agents/base.py`)

- `AgentConfig.model: str | None = None` — campo opcional
- `_parse_registry_file` propaga `meta.get("model")`
- `BaseAgent.__init__`: `self.model = config.model or settings.model_for_tier(tier)`
- Antes: campo `model:` no frontmatter era decorativo (sempre lia do `tier_model_map`)

#### `main.py` deduplicado

- Era ~100 LOC duplicando `cli/main.py`; agora é 1 import + delegação

#### `ui/chainlit_app.py`

- `asyncio.get_event_loop()` → `asyncio.get_running_loop()` (deprecation 3.10+)
- Lazy init do `Supervisor()` envolto em `asyncio.Lock()` global — chats concorrentes
  não disparam mais N inicializações simultâneas (15 leituras de disco × N usuários)
- Tuple unpacking atualizado para nova API do `QAOrchestrator` (4-tuple negotiate,
  3-tuple verify) — bug latente que só funcionava por sorte

#### `_should_bypass` → `should_bypass` (`orchestrator/qa_orchestrator.py`)

- Função era importada por `ui/chainlit_app.py` apesar do prefixo `_` (privado)
- Renomeada para público; testes atualizados

#### `ARCHITECTURE.md` sincronizado com registry

- Supervisor: `MCPs: []` (antes "Databricks, Fabric" — registry sempre disse `[]`)
- SQL Expert: `Skills: [sql-optimizer, sql-queries]` (antes `sql-query-optimizer`
  que nem existe)

### Testes

- `tests/test_qa_orchestrator.py` — `_should_bypass` → `should_bypass` (15 occorrências)
- Suite: 249 passed, 0 failed, 84.76% coverage, ruff=0

---

## [0.4.0] — 2026-04-27

Hardening completo após auditoria externa: 3 fixes de segurança críticos, 4 correções de
arquitetura no QA Orchestrator e 7 inconsistências de configuração/regex.

### 🔴 Segurança (CRÍTICO)

#### #1 Path traversal em `cli/runner.py::resolve_context`

- Caminhos absolutos em `context_files` agora são silenciosamente rejeitados
- Caminhos relativos são resolvidos e validados via `Path.is_relative_to(project_root)`
- Antes: `context_files: ["/etc/passwd"]` era lido e injetado no prompt do LLM

#### #2 Secrets em logs (`hooks/audit_hook.py`, `utils/session.py`)

- Regex universal `_SECRET_RE` cobre `token|password|api_key|secret|bearer|dapi|ghp_|sk-|pat_`
- `audit_hook.record()` aplica `_redact()` no campo `task` antes de gravar `logs/audit.jsonl`
- `session.record()` aplica em `user_input` e `result_content` antes de gravar `logs/sessions/*.jsonl`
- Antes: tokens completos eram serializados raw no disco

#### #3 Testes `test_json_mode` quebrados por singleton de Settings

- `tests/conftest.py::_ensure_github_token` agora também faz
  `monkeypatch.setattr(settings, "github_token", "test_token_fixture")` para sobrescrever
  o singleton instanciado em import-time
- Antes: `setenv` sozinho não afetava `Settings()` já cacheado

### 🟠 Arquitetura QA Orchestrator (SÉRIO)

#### #4 `kb_domains` lido do registry em vez de mapa hard-coded

- `AgentConfig` ganha campo `kb_domains: list[str]`
- `loader._parse_registry_file` propaga `kb_domains` do frontmatter `.md`
- `Supervisor._load_kb_context` agora consulta `agent.config.kb_domains` diretamente
- Removido mapa hard-coded de 12 entradas em `agents/supervisor.py` que divergia do
  frontmatter em 8 dos 13 agentes

#### #5 `QAOrchestrator.execute()` honra a spec acordada

- Antes: chamava `supervisor.route(user_input)` ignorando totalmente a spec — fases
  1 e 2 (negotiate/draft) eram decorativas
- Agora: chama `supervisor.get_agent(spec.agent_name)` e injeta a spec serializada
  como `context` para o agente cumprir as `acceptance_criteria` acordadas
- Fallback para `route()` apenas quando `agent_name` é inválido

#### #6 Defaults fail-closed em `verify` e `_review_spec`

- `verify`: quando `criteria_results` vier vazio (parser falhou ou LLM omitiu),
  agora retorna `score=0.0`, `passed=False`. Antes: `score=1.0` (fail-open)
- `_review_spec`: quando `decision` não for `APPROVE`/`REQUEST_CHANGES`, força
  `REQUEST_CHANGES`. Antes: aceitava qualquer string como APPROVE implícito

#### #7 Token accounting completo

- `QAOrchestrator.handle()` agora soma `neg_tokens + delivery.tokens_used + ver_tokens`
- `negotiate_spec` retorna 4-tuple `(spec, rounds, tokens, calls)`
- `verify` e `_review_spec` retornam `(report, tokens, calls)`
- `Supervisor.draft_spec`/`revise_spec` retornam `(spec, tokens, calls)`
- Antes: tokens das fases de negotiation e verification eram descartados (subestimação 3-5x)

### 🟡 Inconsistências de configuração

#### #8 `.env.example` reescrito

- Removidas variáveis fantasma que não existiam em `Settings`: `COPILOT_API_KEY`,
  `COPILOT_MODEL_T1/T2/T3`, `LOG_LEVEL`, `LOG_FILE`, `ENABLE_*_HOOK`,
  `MAX_COST_PER_SESSION`, `NAMING_CONVENTION_FILE`, `CHAINLIT_PORT`,
  `CHAINLIT_HOST`, `DEBUG`, `VERBOSE`, `AZURE_SUBSCRIPTION_ID`, `CONTEXT7_ENABLED`
- Mantidas apenas variáveis efetivamente lidas em `config/settings.py`

#### #9 `spark_expert.md` recebe MCP `databricks`

- Frontmatter `mcps: [databricks]` (era `[]`) — agente especialista em Spark/Databricks
  agora declara o MCP que efetivamente usa

#### #10 Settings fantasma removidas (`config/settings.py`)

- Removidos campos não-usados: `max_turns`, `agent_permission_mode`, `memory_enabled`,
  `context7_enabled`

#### #11 `session_max_resume_turns` agora é configurável

- `utils/session.py::load_last_session(max_turns=None)` consulta
  `settings.session_max_resume_turns` por padrão
- Removido `_MAX_RESUME_TURNS = 10` hard-coded

#### #12 `max_turns` global removido

- Variável era declarada em Settings mas nunca consumida (cada agente já controla seus
  próprios `max_turns` via `AgentConfig`)

#### #13 Workflow regex com verbo de comando obrigatório (`workflow/dag.py`)

- Todas as regexes WF-01..WF-07 reescritas para exigir verbo de comando inicial
  (criar/construir/implementar/migrar/sustentar/auditar/etc.)
- WF-05 aceita "implantar um novo lakehouse"; WF-07 aceita "sustentação do lakehouse"
- Antes: matches falso-positivos disparavam workflows caros em queries inocentes
  como "o que é um lakehouse?"

#### #14 KG threshold via `require_explicit_flow` (`memory/kg.py`)

- `extract_lineage_from_text(text, kg, require_explicit_flow=True)` por default
- Tabelas Medallion isoladas (`raw_*`, `bronze_*`) só viram entidades quando há
  fluxo explícito `_FLOW_PATTERN` ou `INSERT INTO ... FROM` no texto
- Antes: qualquer menção a tabela poluía o KG

### Testes

- `tests/conftest.py` — fixture sobrescreve singleton settings
- `tests/test_cli_runner.py` — novo `test_resolve_context_rejects_absolute_path_traversal`
- `tests/test_qa_orchestrator.py` — atualizado para nova assinatura tuple em
  `negotiate_spec` (4-tuple), `verify` (3-tuple), `draft_spec`/`revise_spec` (3-tuple);
  `test_verify_no_criteria_fails_closed` substitui o antigo
  `test_verify_no_criteria_defaults_score_1`; `test_execute_falls_back_to_route_when_agent_invalid`
  cobre fallback
- `tests/test_supervisor_extended.py`, `tests/test_supervisor_routing.py` — atualizados

**Resultado:** 249 passed, 0 failed, 82.70% coverage, ruff=0.

---

## [0.3.0] — 2026-04-27

### Adicionado

#### Structured output em `_plan_and_delegate` (`agents/supervisor.py`)

- `BaseAgent.run()` aceita `json_mode=False` — quando `True`, passa `response_format={"type": "json_object"}` na chamada OpenAI
- PRD prompt reescrito para retornar `{"agent_name": "<agente>", "prd": "<markdown>"}` em vez de texto livre
- `supervisor._plan_and_delegate` faz `json.loads()` do resultado; fallback para regex se JSON inválido
- Elimina parse frágil via `_PRD_AGENT_RE.search()` como caminho principal

#### Cache de skills a nível de classe (`agents/base.py`)

- `BaseAgent._CLASS_SKILL_CACHE: dict[str, str] = {}` — variável de classe compartilhada entre todas as instâncias
- `_load_skill()` lê do disco apenas na primeira chamada por skill por sessão; N instâncias do mesmo agente compartilham o cache
- Removido `self._skill_cache` (variável de instância)

#### Rollback / early-stop em workflows (`workflow/executor.py`)

- `execute_workflow(..., fail_fast=True)` — para na primeira etapa que lança exception, retorna resultado parcial acumulado
- `fail_fast=False` — continua nas etapas seguintes, registra o erro como placeholder no contexto
- `supervisor.route()` agora passa `fail_fast=True` explicitamente
- Comportamento sem erros 100% retrocompatível

#### Evals via `Supervisor.route()` (`evals/runner.py`)

- `run_query_routed(query, supervisor)` — executa query via `supervisor.route()` em vez de agente direto
- `run_all_routed(queries, supervisor)` — batch via supervisor
- Flag `--use-supervisor` no CLI de evals: `python -m evals.runner --use-supervisor --domain sql`
- Makefile: `make evals-routed` equivale a `--use-supervisor`

#### Testes

- `tests/test_backlog_features.py` — 14 testes cobrindo as 4 features (json_mode, class cache, fail_fast, evals routed)
- Total: 233 → **247 testes**, cobertura 82.70%

---

## [0.2.0] — 2026-04-27

### Adicionado

#### CLI `data-agent` (`cli/`)

- `cli/main.py`: entry point argparse registrado via `pyproject.toml` como `data-agent = "cli.main:main"`
  - Subcomandos: `start`, `run`, `health`, `list`, `tasks` + todos os 15 agentes como atalhos diretos
  - `_lazy_supervisor()` — inicializa Supervisor só quando necessário
- `cli/menu.py`: menu interativo com `questionary.select` (20 opções)
  - File picker de `tasks/` integrado
  - Exibe sumário de tokens após cada resposta
- `cli/runner.py`: executa arquivos de tarefa YAML e Markdown
  - `load_task_file()` — suporta `.yaml`, `.yml`, `.md` (com frontmatter)
  - `run_task_file()` — despacha para agente direto ou `supervisor.route()`
  - `_save_output()` — persiste resultado se campo `output` presente
  - `list_task_files()` — rglob excluindo arquivos `_` prefixo
  - Fix: `task: null` no YAML não quebra mais o runner (`or ""` antes de `.strip()`)

#### Repositório de Task Files (`tasks/`)

- Estrutura por subpastas: `sql/`, `spark/`, `pipelines/`, `governance/`, `quality/`, `devops/`, `workflows/`
- 9 exemplos prontos + `_template.yaml` comentado
- Schema YAML: `agent` (default: `auto`), `task`, `context_files`, `output`
- Schema MD: frontmatter com mesmos campos, corpo = texto da tarefa

#### Dependências

- `questionary>=2.0` — menus interativos
- `pyyaml>=6.0` — parse de task files

#### Testes

- `tests/test_cli_runner.py`: 17 testes para `cli/runner.py` (load, resolve, run, list, integração YAML)
- Total: 215 → **233 testes**, cobertura 83%

#### Makefile

- Targets: `agent` (executa `data-agent`), `tasks` (lista tasks), `run-task` (executa `FILE`)

---

## [0.1.0] — 2026-04-27

### Adicionado

#### QA Orchestrator (`orchestrator/`)

- `orchestrator/models.py`: `TaskSpec`, `ReviewResult`, `DeliveryResult`, `ScoreReport`, `parse_json_from_llm()`
- `orchestrator/qa_orchestrator.py`: `QAOrchestrator` — protocolo spec → negociação → execução → score
  - Ativo automaticamente em todos os inputs não-comandos (`/health`, `/help`, `/sessions`... são bypassed)
  - Score threshold 0.7 configurável via `QA_SCORE_THRESHOLD`
  - Max 3 rounds de negociação configurável via `QA_MAX_ROUNDS`
- `agents/registry/qa_reviewer.md`: agente QA tier T1 (review_spec + verify_delivery)
- `Supervisor.draft_spec()` + `Supervisor.revise_spec()`: suporte ao protocolo de negociação
- `Supervisor.get_agent(name)`: acesso público a agente por nome (substitui `_agents.get`)

#### Workflows WF-05, WF-06, WF-07 (`workflow/dag.py`)

- WF-05 (5 etapas): implantação de lakehouse — pipeline_architect, lakehouse_engineer, data_quality, governance_auditor, devops_engineer
- WF-06 (6 etapas): migração de lakehouse — diagnóstico, arquitetura, pipeline, qualidade, governança, devops
- WF-07 (4 etapas): sustentação — monitoramento, otimização, custo, relatório

#### Novos Agentes

- `databricks_ai.md` — Agent Bricks, Genie, MLflow, UC AI
- `devops_engineer.md` — DABs, Azure DevOps, Fabric CI/CD
- `lakehouse_engineer.md` — implantação, migração, sustentação de lakehouse
- `python_expert.md` — Python puro, testes, utilitários
- `fabric_expert.md` — Fabric Lakehouse, OneLake, Direct Lake

#### Integrações

- `integrations/fabricgov.py`: wrapper do CLI fabricgov para `/assessment`
- `integrations/github_context.py`: fetch de contexto do repo fabric-ci-cd para agente devops

#### MCP Servers Standalone

- `mcp_servers/databricks_server.py`: 9 tools Databricks via REST
- `mcp_servers/fabric_server.py`: 8 tools Fabric via REST

#### Knowledge Base (`kb/`)

- 18 domínios: `sql-patterns`, `spark-patterns`, `spark-internals`, `pipeline-design`, `data-quality`, `governance`, `databricks-platform`, `databricks-ai`, `fabric`, `lakehouse-design`, `lakehouse-ops`, `genai`, `prompt-engineering`, `data-modeling`, `ci-cd`, `orchestration`, `testing`, `shared`
- `kb/constitution.md`: 30+ regras invioláveis

#### Testes

- Cobertura de 29% → **83%** (215 testes)
- Novos arquivos: `test_base.py`, `test_hooks.py`, `test_supervisor_methods.py`, `test_supervisor_extended.py`, `test_workflow_executor.py`, `test_qa_orchestrator.py`, `test_health.py`, `test_party.py`, `test_party.py`, `test_settings.py`
- `tests/conftest.py`: fixture `_ensure_github_token` (autouse) — testes rodam sem `.env`

### Corrigido

- **Bug**: `GITHUB_TOKEN` obrigatório quebrava qualquer `import` sem `.env` — agora default `""`, validado só ao acessar `copilot_client`
- **Bug**: `Supervisor()` instanciado em import-time no Chainlit — movido para `@cl.on_chat_start` (lazy init)
- **Bug**: `security_hook` bloqueava output legítimo de agentes com docs SQL (`SELECT *`) — separado em `check_input()` (todas as regras) e `check_output()` (só destrutivos reais)
- **Bug**: `hash(task)` não-determinístico em filenames de PRD e workflow — substituído por `hashlib.sha1(task.encode()).hexdigest()[:8]`
- **Bug**: `_session_total_tokens` / `_session_high_count` nunca resetados — adicionado `cost_guard_hook.reset()`
- **Bug**: `args_parsed` calculado e descartado em `base._dispatch_tool` — `dispatch_tool` agora aceita `str | dict`, `args_parsed` passado diretamente

---

## [0.0.1] — 2026-04-25

### Adicionado — Base

- Fork de `ThomazRossito/data-agents` adaptado para GitHub Copilot Chat API
- 10 agentes iniciais: supervisor, spark_expert, sql_expert, pipeline_architect, data_quality, naming_guard, governance_auditor, dbt_expert, geral + base
- `agents/supervisor.py`: roteamento por regex (comandos → governança → workflows → PRD → fallback)
- Auto-trigger: `CREATE TABLE / ALTER TABLE / DROP TABLE` → Naming Guard
- `workflow/dag.py`: WF-01 a WF-04
- `memory/`: MemoryStore + retrieval + decay + extractor + KnowledgeGraph
- `hooks/`: audit_hook, cost_guard_hook, security_hook, output_compressor
- `kb/`: constitution + domínios iniciais
- `evals/`: 13 queries canônicas, 9 domínios, runner CLI
- `config/settings.py`: Pydantic settings (tier_model_map T1/T2/T3)
- `ui/chainlit_app.py`: interface web Chainlit
- `main.py`: CLI entry point com Rich
- `Makefile`: targets test, ui, evals, lint, deploy-prod
- `.mcp.json`: configuração MCP para VS Code
