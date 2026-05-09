> All notable changes to this project are documented here.
>
> Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
> Versioning: [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

# Changelog

## [Unreleased]

## [2.3.0] — 2026-05-09

### Added — Chainlit UI completeness: /workflow, /geral streaming, /sessions, /resume

- **`/workflow` na Chainlit UI** (`ui/chainlit_app.py`): `_handle_workflow()` executa
  workflows WF-01 a WF-05 com feedback em tempo real — um `cl.Step` por fase via novo
  `step_callback` no `WorkflowRunner`. Fases com `require_human_approval=True` pausam e
  exibem botões `cl.Action` (Aprovar/Abortar) resolvidos via `asyncio.Future` com timeout
  de 5 min. Action callbacks `wf_approve` / `wf_abort` registrados.
- **`StepCallback` em `WorkflowRunner`** (`commands/workflow.py`): novo parâmetro opcional
  `step_callback: StepCallback | None` chamado com status `"start"` / `"done"` / `"error"`
  por fase. Backward-compatible (default `None`). Tipo `StepCallback` exportado.
- **`/geral` streaming de tokens** (`commands/geral.py`, `ui/chainlit_app.py`): parâmetro
  `token_callback` em `run_geral_query()` — quando fornecido, usa `client.messages.stream()`
  e chama o callback com cada chunk de texto. Chainlit passa `response_msg.stream_token` como
  callback, exibindo tokens à medida que chegam. CLI sem callback continua usando
  `messages.create()` (backward-compatible).
- **`/sessions` na Chainlit UI** (`ui/chainlit_app.py`): `_handle_sessions()` formata lista
  de sessões como tabela Markdown. Suporta `/sessions`, `/sessions all` e `/sessions <id>`
  para ver transcript completo. Não requer modo Supervisor.
- **`/resume` na Chainlit UI** (`ui/chainlit_app.py`): `_handle_resume()` constrói prompt
  de retomada via `build_resume_prompt_for_session()` e envia ao Supervisor. Suporta
  `/resume last` (sessão mais recente) e `/resume <session-id>`. Ativa modo Supervisor
  automaticamente se necessário.
- **`/workflow`, `/sessions`, `/resume` no `COMMAND_GROUPS`** (`ui/ui_config.py`): grupos
  `"🎉 Multi-Agente"` e `"📂 Sessões"` atualizados para aparecer na tela de boas-vindas.
- **13 novos testes** (`tests/test_geral_command.py`): `TestRunGeralQuery` cobre path
  non-streaming, streaming com callback, acumulação de chunks e isolação do `messages.stream`.
- **5 novos testes** (`tests/test_workflow.py`): `StepCallback` start/done/error, None sem
  exceção, type annotation.

## [2.2.0] — 2026-05-09

### Added — Chainlit UI parity + Lições Aprendidas dashboard

- **`/analyze-project` como comando real** (`commands/analyze.py`): 5 grupos de agentes
  (default, quality, arch, databricks, fabric), prompts por agente com 5 seções estruturadas,
  relatório consolidado em `output/analyze-project/`. Antes existia apenas como comando
  Claude Code, causando alucinação no Supervisor.
- **Anti-alucinação no Supervisor** (`agents/prompts/supervisor_prompt.py`): seção
  `SLASH COMMANDS REFERENCE` com tabela de comandos reais e instrução explícita de nunca
  inventar comandos fora da lista.
- **`/analyze-project` na Chainlit UI** (`ui/chainlit_app.py`): `_handle_analyze_project()`
  intercepta o comando antes do Supervisor, roda agentes em paralelo via `asyncio.gather`,
  exibe um `cl.Step` por agente durante a execução e resultados como `cl.Message` individuais.
- **`/party` na Chainlit UI** (`ui/chainlit_app.py`): `_handle_party()` implementado com o
  mesmo padrão — suporta todos os flags (`--quality`, `--arch`, `--full`, `--engineering`,
  `--migration`) e listas explícitas de agentes. Antes caía no Supervisor com `doma_prompt`
  truncado.
- **`/geral` direct dispatch na Chainlit UI** (`ui/chainlit_app.py`): `_handle_geral()`
  chama `run_geral_query()` diretamente via `anthropic.AsyncAnthropic` com Haiku (T0) —
  sem Supervisor, sem Agent tool, ~95% mais barato. Mantém histórico de conversa
  (`_geral_history`) para follow-ups na sessão.
- **Página "🧠 Lições Aprendidas"** no Streamlit (`monitoring/app.py`): `load_lessons()`
  lê `memory/data/lesson_learned/*.md` via frontmatter. Exibe métricas (total ativas/expiradas,
  avg confidence, agentes com lições), distribuição por trigger e agente, lista filtrável com
  agente + trigger + show-expired, detalhe expandível por lição com conteúdo e tags.
- **`/party` e `/analyze-project` no `COMMAND_GROUPS`** (`ui/ui_config.py`): grupo
  `"🎉 Multi-Agente"` adicionado para aparecer no texto de boas-vindas do Chainlit.
- **26 novos testes** (`tests/test_analyze_command.py`): parser, grupos, prompts e
  consolidador de relatório.

### Fixed

- **Monitoring Observability**: `"analyze"` adicionado ao `_SUPERVISOR_LIKE` set para
  sessions do tipo `/analyze-project` aparecerem corretamente no dashboard.
- **Escape sequences**: `\|` em tabelas Markdown no `supervisor_prompt.py` corrigido para `|`.

## [2.1.0] — 2026-05-09

### Added — Autonomous Learning System + S4 Selective Relaxation

- **LESSON_LEARNED memory type** (`memory/types.py`): 8º tipo de memória com decay de 30 dias.
  Captura erros, operações de alto custo, retentativas e ops lentas como conhecimento estruturado.
- **Lesson capture pipeline** (`hooks/memory_hook.py`): detecção de 4 triggers (error, high_cost,
  retries, slow_op) via PostToolUse + PreToolUse. Sumarização via Haiku (~$0.001/lesson).
- **`pre_track_lesson_timing()`**: hook PreToolUse que registra t₀ de cada tool call para medir
  duração real (slow_op detection). Registrado em `supervisor.py`.
- **Anti-bloat**: `store.prune_lessons_by_agent()` limita a 50 lessons ativas por agente.
  `compiler.deduplicate_lessons()` consolida lessons com >60% de overlap por agente+task_type.
  `deduplicate_lessons()` agora é chamado automaticamente em `compile_daily_logs()`.
- **Lesson injection** (`memory/retrieval.py`): seção `### Lições Aprendidas ⚠️` no bloco
  injetado no system prompt no início de cada sessão.
- **Agent instructions**: `databricks-engineer`, `fabric-engineer`, `databricks-ai`,
  `migration-expert` — cada um recebeu instrução de consultar lessons antes de ops HIGH-risk.
- **S4 Autonomous Mode** (`config/settings.py`): 3 novos campos — `s4_autonomous_mode`,
  `s4_auto_approval_min_clarity_score`, `s4_auto_approval_max_cost_usd`. Default OFF.
- **`tracker.log_s4_decision()`** (`workflow/tracker.py`): loga evento `s4_decision` em
  `logs/workflows.jsonl` com mode, clarity_score, approved, reason e agents.
- **S4 constitution clause** (`kb/constitution.md`): §2.1 documenta critérios de auto-aprovação.
- **S4 supervisor prompt** (`agents/prompts/supervisor_prompt.py`): Step 2 atualizado com
  lógica condicional S4-AUTO.
- **22 novos testes**: `test_memory_lesson_learned.py` (14 testes, Fases 1–4) e
  `test_s4_relaxation.py` (8 testes, Fase 5).

### Gated (aguardando telemetria)

- **T1.7** — Decidir Caminho A vs B da memória (`logs/memory_usage.jsonl` 24-72h).
- **T2.5** — Dashboard de cache hit rate (`logs/audit.jsonl` acumulado).
- **T4.5** — Decisão final Caminho A da memória (6 semanas de métricas).

### Backlog

- ~~**T0.2.1**~~ — Issue aberta em
  [`anthropics/claude-agent-sdk-python#845`](https://github.com/anthropics/claude-agent-sdk-python/issues/845)
  pedindo passthrough de `extra_headers` para opt-in em `anthropic-beta: token-efficient-tools-2025-02-19`.
- **T5.1** — Prompt caching explícito no Supervisor. Confirmado bloqueado em SDK 0.1.63.

---

## [2.0.0] — 2026-05-09

### Removed — Consolidação 23 → 14 agentes (Phases 1–5)

- **12 agentes Fabric consolidados em 3** (Phase 1):
  - `semantic-modeler`, `catalog-intelligence`, `schema-designer`, `cost-optimizer`,
    `medallion-architect` → absorvidos por `fabric-engineer`
  - `ontology-engineer` → renomeado para `fabric-ontology`

- **7 agentes Databricks consolidados em 2** (Phase 2):
  - `sql-expert`, `spark-expert`, `pipeline-architect`, `cdc-specialist`,
    `spark-diagnostics` → consolidados em `databricks-engineer`
  - `ai-data-engineer`, `streaming-engineer` → consolidados em `databricks-ai`

- **Interface Streamlit de chat** (T5.4): `ui/chat.py` (964 LOC) removido.
  Chainlit (`ui/chainlit_app.py`) é agora a única UI de chat, ativada por
  `./start.sh` na porta 8503. Streamlit continua como dependência do
  dashboard de monitoramento (`monitoring/app.py`, porta 8501) e foi
  removido dos extras `[ui]` em `pyproject.toml` — permanece só em
  `[monitoring]`. Arquivos ajustados: `start.sh` (flag `--chainlit`
  removida, porta padrão 8503), `start_chainlit.sh`, `README.md`,
  `.claude/CLAUDE.md`, `Manual_Relatorio_Tecnico_Projeto_Data_Agents.md`,
  `commands/geral.py` (docstring), `main.py` (comentário),
  `ui/chainlit_app.py` (prompt do Dev Assistant), `ui/ui_config.py`
  (constantes `COMMANDS_NO_ARGS` e `STREAMLIT_CSS` removidas),
  `tests/test_functional.py` (removida a parametrização de `ui/chat.py`
  em `TestDOMARenamingNoBMADInCode` e o teste `test_chat_uses_doma_prompt`).

### Changed

- **`scripts/refresh_skills.py` migrado para Anthropic Batch API** (T5.2):
  todas as skills pendentes de refresh agora são submetidas em um único
  batch via `client.messages.batches.create()`, com 50% de desconto sobre
  input+output. O script faz polling a cada 10s (SLA máximo 24h, batches
  pequenos concluem em minutos) e escreve cada SKILL.md conforme os
  resultados retornam. Flag `--concurrent` removida (paralelismo é
  servidor-side). Custo estimado por rodada cai de `~$1-3` para `~$0.50-1.50`.
  20 testes novos em `tests/test_refresh_skills_batch.py` mockam o ciclo
  `create → retrieve → results` e cobrem custo, submissão única,
  propagação de erros e curto-circuito em `--dry-run`.

- **Skills migradas para o formato nativo Anthropic** (T5.3): cinco skills
  canônicas que viviam como arquivos flat em `skills/*.md` agora residem em
  `skills/patterns/<name>/SKILL.md` com frontmatter YAML (`name` +
  `description`):
  - `data_quality.md` → `patterns/data-quality/SKILL.md`
  - `pipeline_design.md` → `patterns/pipeline-design/SKILL.md`
  - `sql_generation.md` → `patterns/sql-generation/SKILL.md`
  - `spark_patterns.md` → `patterns/spark-patterns/SKILL.md`
  - `star_schema_design.md` → `patterns/star-schema-design/SKILL.md`

  `agents/loader.py::_load_skills_index` deixou de ter o branch especial
  `"root"` e usa `description` do frontmatter como hint (antes inferia a
  primeira linha do corpo). 8 agentes tiveram `skill_domains: [..., root]`
  atualizados para `[..., patterns]`; 25 testes novos em
  `tests/test_native_skills.py` cobrem descoberta e injeção.

### Added

- **Skills `async-patterns` e `cli-patterns`** em `skills/python/` (T6.4):
  cobertura completa de asyncio (`gather`, `Queue`, cancelamento, `httpx`
  async, `Semaphore`, `run_in_executor`) e de CLIs (`argparse`, Typer,
  Rich output, stdin/stdout/pipe, entry points, exit codes semânticos).
  `SKILL.md` do python-expert atualizado; agente passa a consultar ambos
  antes de gerar código async ou ferramentas de linha de comando.

- **`make bootstrap` com validação de ambiente** (T6.3):
  `scripts/bootstrap.py` ganhou `_check_system_deps()` — verifica
  presença de `uvx`, `npx`/`node`, `dotnet` e Python ≥ 3.11 antes de
  criar o `.env`, exibindo instrução de instalação por dep ausente.
  5 novos testes em `tests/test_bootstrap.py`.

- **Regression detection em `make evals`** (T6.2):
  `evals/runner.py` carrega o run anterior como baseline via
  `load_latest_run()` e detecta regressões via `detect_regressions()`.
  O sumário exibe queries que regrediram e o exit code é 1 quando
  qualquer query regrediu ou falhou. 10 novos testes em `tests/test_evals.py`.

- **Compactação autônoma do contexto** (T6.1): `context_budget_hook.py`
  monitora tokens acumulados; ao atingir 80% gera summary via Haiku 4.5
  e seta flag consumível `_compaction_pending`. Entry points (`main.py` e
  `ui/chainlit_app.py`) detectam o flag após cada resposta, injetam o
  summary no `base_system_prompt` e reconectam o cliente SDK — nova janela
  limpa, transparente ao usuário. Limiares: aviso a 70%, compacta a 80%,
  ERROR a 95%.

- **Página "🔭 Observabilidade"** em `monitoring/app.py` (T6.5): nova
  página do dashboard com 4 tabs — (1) **Custo por agente**: agrega
  `logs/sessions.jsonl` via mapa `session_type → agente`, soma
  `total_cost_usd` / `num_turns`, complementa com delegações reais do
  Supervisor a partir de `logs/workflows.jsonl` (event `agent_delegation`);
  (2) **Latência**: p50/p95/max/mean por agente em ms (filtra
  `duration_s > 0`); (3) **Erros por MCP**: taxa de erro por `platform`
  vindo de `logs/audit.jsonl` (`has_error=true`) com
  `st.column_config.ProgressColumn` + drill-down dos últimos 50 erros,
  mais erros de sessão (`sessions.jsonl.has_error`); (4) **Cache hit
  rate**: empty state gated em T2.5/SDK #626 que auto-ativa quando
  `cache_read_tokens` aparecer nos registros. Respeita o filtro de data
  da sidebar já existente.
- **`PRODUCT.md`** na raiz: tese de produto em uma página — ICP, JTBD,
  diferencial vs alternativas (Genie nativo, Copilot Fabric, dbt AI,
  LangChain, ChatGPT/Claude direto) e anti-escopo explícito.
- **`make bootstrap`** (`scripts/bootstrap.py`): wizard interativo que
  gera um `.env` mínimo a partir de 3 perguntas (Anthropic + Databricks
  opcional + Fabric opcional). Sem dependências extras; cross-platform.
  Defaults de sistema (DEFAULT_MODEL, MAX_BUDGET_USD, memória) vêm
  pré-configurados.
- **`make demo`** (`scripts/demo.py`): smoke test end-to-end chamando
  `commands/geral.run_geral_query` direto (Haiku 4.5, zero MCP, zero
  Supervisor). Custo ~$0.005 por execução. Valida que o sistema
  funciona antes de configurar Databricks/Fabric.
- **8 testes** em `tests/test_bootstrap.py` para `_render_env` e
  `_validate_anthropic_key` (funções puras do wizard).
- **`make evals`** (`evals/runner.py` + `evals/canonical_queries.yaml`):
  framework de regressão v1 com 15 queries canônicas e rubric
  determinística (`must_include`, `must_not_include`, `min_length`,
  `max_length`). Score 1.0 / 0.5 / 0.0 por query; exit 0 se tudo passa.
  Executa via `run_geral_query` (Haiku 4.5, ~$0.005 por query =
  ~$0.08 por rodada completa). Resultados persistidos em
  `logs/evals/<timestamp>.jsonl`. Filtros CLI: `--domain`, `--id`,
  `--limit`. **18 testes** em `tests/test_evals.py` cobrindo
  loader, scoring e filtros.

### Fixed

- `README.md`: removidas referências ao agente `skill-updater` (removido em
  T3.6 do Sprint 3). Refresh de Skills é agora `scripts/refresh_skills.py`.
- `.github/workflows/cd.yml`: removido trigger por tag (`push: tags: v*`);
  deploy exclusivamente via `workflow_dispatch` manual. Evita falhas de CD
  por secrets intencionalmente não configurados.

---

## [1.3.0] — 2026-05-07

### Added

- **9 novos agentes especialistas** no registry (`agents/registry/`):
  - `ai-data-engineer` (T1) — RAG pipelines, Vector Search, embeddings, chunking, LLMOps, AI Functions, feature stores
  - `streaming-engineer` (T1) — Kafka, Apache Flink, Spark Structured Streaming, Fabric RTI, CDC com Debezium
  - `cdc-specialist` (T1) — Change Data Capture: Debezium, Kafka Connect, AUTO CDC INTO, transactional outbox, CQRS
  - `data-contracts-engineer` (T2) — ODCS v3 authoring, SLA de qualidade, schema evolution, breaking change management, knowledge graph de contratos
  - `schema-designer` (T2) — Star Schema, Snowflake Schema, Data Vault 2.0, SCD tipos 1–6, grain definition, modelagem dimensional
  - `cost-optimizer` (T2) — Análise DBU/CU via system tables, rightsizing de clusters, otimização Delta Storage, budget forecasting
  - `data-mesh-architect` (T2) — mapeamento de domínios, Data Products, self-serve platform, governança federada, maturity assessment
  - `spark-diagnostics` (T2) — diagnóstico de jobs Spark: OOM, data skew, shuffle/spill, hangs, análise Spark UI, AQE tuning, falhas DLT
  - `medallion-architect` (T2) — design Bronze/Silver/Gold, seleção de artefatos (STREAMING TABLE vs MATERIALIZED VIEW), anti-pattern detection

- **9 novos slash commands** em `config/commands.yaml`:
  `/streaming`, `/ai`, `/cdc`, `/schema`, `/finops`, `/mesh`, `/diagnose`, `/medallion`, `/contract`

- **`governance-auditor` expandido** com capacidades de auditoria de segurança:
  - Auditoria de RLS (Row-Level Security) via `information_schema.row_filters`
  - Auditoria de Column Masking/OLS via `information_schema.column_masks`
  - Auditoria de Sensitivity Labels no Fabric e Microsoft Purview
  - Verificação de Workspace Roles e privilégios de tabela
  - 4 novos tipos de tarefa no Mapa KB+Skills

### Changed

- `agents/prompts/supervisor_prompt.py`: atualizado para 23 agentes com seções de roteamento para todos os novos especialistas
- `tests/test_agents.py`: lista de agentes esperados atualizada de 14 para 23
- `README.md`: badges, tabela de agentes e tabela de comandos atualizados para v1.3.0 com todos os 23 agentes e 38 slash commands
- `.claude/CLAUDE.md`: seções "MCPs por Agente", "Slash Commands", cabeçalho e lista de agentes no registry atualizados

---

## [1.0.0] — 2026-04-18

Primeira release versionada. Representa o estado após a execução dos sprints
S0-S4 do plano de enxugamento 2026: correções pontuais, sessão com memória
real, elevação da maturidade declarativa e refatoração arquitetural.

**Suite:** 1026 testes ✅ (0 falhas).

### Added

- **Transcript por sessão** (`hooks/transcript_hook.py`): persiste JSONL
  append-only em `logs/sessions/<session_id>.jsonl` com turnos
  user/assistant, tools usadas, custo e duração.
- **Slash `/sessions`** (`commands/sessions.py`): tabela Rich com todas as
  sessões — ID, timestamps, turns, custo, status (transcript 📝 ou
  checkpoint 💾), último prompt.
- **Slash `/resume <id>|last`**: reabre sessão injetando os últimos N turnos
  do transcript (default 30×2000 chars ≈ 8% do context budget); fallback
  para `build_resume_prompt` em sessões legadas.
- **Session Summarizer** (`utils/summarizer.py`): Haiku 4.5 via Anthropic
  Messages API direta, produz resumo em 7 campos GAPS G3 (Objetivo /
  Decisões / Artefatos / Pendências / Próximos passos / Contexto técnico /
  Descobertas-chave). Regra "Nunca invente" + `Nenhum(a)` para campos vazios.
- **Compactação autônoma** em `hooks/context_budget_hook.py`: dispara uma
  vez por sessão ao cruzar `context_budget_summarize_threshold` (0.80),
  persiste em `logs/summaries/<sid>.md` e reconecta o cliente com nova janela.
- **Emergency checkpoint em saídas normais**: `main.py` registra `atexit`,
  SIGINT, SIGTERM, SIGHUP; `hooks/checkpoint.py` grava
  `logs/sessions/<sid>.json` + espelho em `logs/checkpoint.json`.
- **Histórico múltiplo de sessões** via `list_sessions()` e
  `load_session_by_id()` em `hooks/checkpoint.py`.
- **Slash `/add-agent`** (`.claude/commands/add-agent.md`): scaffolda novo
  registry, sinaliza os dois pontos manuais (supervisor_prompt,
  test_agents), valida YAML e faz smoke test do loader.
- **Slash `/add-mcp`** (`.claude/commands/add-mcp.md`): guia pelos 5 passos
  do CLAUDE.md + checklist + 4 validações automáticas.
- **Matriz de delegação declarativa** (`agents/delegation_map.yaml` +
  `agents/delegation.py`): 25 routes, renderização de
  `kb/task_routing.md` §2 via markers, `classify()` determinístico.
- **Declaração de commands em YAML** (`config/commands.yaml`): 22 definições
  de slash commands, loader em `commands/parser.py` reduzido para ~120
  linhas.
- **Pacote `workflow/`**: extração de `hooks/workflow_tracker.py` em
  `dag.py` / `tracker.py` / `executor.py`.
- **Pacote `compression/`**: extração de `hooks/output_compressor_hook.py`
  em `constants.py` / `strategies.py` / `metrics.py` / `hook.py`.
- **`utils/tokenizer.py`**: `estimate_tokens_flat` e
  `estimate_tokens_adjusted` — fonte única de estimativa, substitui
  implementações inline em `context_budget_hook` e `compression/metrics`.
- **Scripts independentes do Supervisor:**
  - `scripts/refresh_skills.py` — chama Anthropic Messages API direta com
    tool nativo `web_search_20250305`.
  - `scripts/monitor_daemon.py` — executa SQL direto via
    `databricks-sdk`/`pymssql` (sem LLM).
- **`docs/mcp_fabric_guide.md`**: matriz de decisão para namespaces ATIVO
  (`mcp__fabric_community__*`) vs OFICIAL (`mcp__fabric__*`).
- **Telemetria de cache** em `hooks/audit_hook.py`:
  `cache_creation_input_tokens`, `cache_read_input_tokens`, `cache_hit_rate`
  gravados em `logs/audit.jsonl` quando o SDK expuser.
- **Telemetria de memória** em `memory/telemetry.py`: contadores em
  `store.read/write`, `compiler.compile`, `retrieval.retrieve`; grava
  `logs/memory_usage.jsonl`.
- **Testes para MCPs customizados**: `tests/test_databricks_genie_server.py`
  (22), `tests/test_fabric_sql_server.py` (21), `tests/test_transcript_hook.py`
  (21), `tests/test_sessions_command.py` (21), `tests/test_summarizer.py`
  (16).

### Changed

- **Supervisor thinking migrado para Opus 4.7**: `{type: adaptive, effort:
  high}` em `agents/supervisor.py` (era `{type: enabled, budget_tokens:
  8000}`, incompatível).
- **Agente `geral` em Haiku 4.5** (`bedrock/anthropic.claude-haiku-4-5`) —
  ~4× mais barato para Q&A conceitual.
- **`agents/prompts/supervisor_prompt.py` 361 → 150 linhas (-58%)**:
  descrições em prosa compactadas; tabelas de roteamento e KBs movidas para
  `kb/task_routing.md`.
- **Regras S1-S7 são fonte única em `kb/constitution.md`**: removidas das
  duplicações em `supervisor_prompt.py` e `cache_prefix.md`.
- **`commands/parser.py` 542 → 120 linhas (-78%)**: definições migradas para
  `config/commands.yaml` (228 linhas), API pública preservada
  (`COMMAND_REGISTRY`, `CommandDefinition`, `parse_command`,
  `get_help_text`).
- **`hooks/workflow_tracker.py` 492l → 45l (shim)**: re-exporta do novo
  pacote `workflow/`.
- **`hooks/output_compressor_hook.py` 437l → 52l (shim)**: re-exporta do
  novo pacote `compression/`.
- **Fabric MCPs reorganizados**: rename apenas de variáveis Python
  (`FABRIC_COMMUNITY_MCP_TOOLS` → `FABRIC_MCP_TOOLS` canônico;
  `FABRIC_MCP_TOOLS` oficial MS → `FABRIC_OFFICIAL_MCP_TOOLS`). Alias
  legado preservado.
- **`business-monitor` agente** é agora **somente Q&A interativo** —
  modo autônomo vive em `scripts/monitor_daemon.py`.
- **`skill-updater` removido do registry** — refresh é 100% script em
  `scripts/refresh_skills.py`.
- **`memory/types.py::Memory.normalized_summary`** — `@property` única,
  substitui lógica duplicada em `compiler.py` e `lint.py`.
- **Diagrama e contagem de agentes em `.claude/CLAUDE.md`** ajustados de
  "12 agentes" para "13 agentes" (sem contar `_template.md`).
- **`hooks/context_budget_hook.reset_context_budget`** aceita
  `session_id: str | None = None`, propagado por
  `hooks/session_lifecycle.on_session_start`.

### Removed

- `agents/registry/skill-updater.md` — virou script puro.
- `memory/decay.py` — marcado para remoção (aguarda decisão T1.7).
- `_run_via_agent` em `monitor_daemon.py` — 33 linhas de dead code legacy
  que acoplavam daemon ao agente.

### Fixed

- `agents/supervisor.py`: crash em `/plan` com Opus 4.7 (thinking syntax).
- `hooks/checkpoint.py`: double-save ao encerrar sessão
  (flag `_checkpoint_saved_for_session` + reset por iteração).
- `tests/test_memory_retrieval.py`: adaptado para a nova assinatura
  `_query_sonnet_for_ids → (ids, cost)`.
- `tests/test_agents.py::valid_models`: inclui
  `bedrock/anthropic.claude-haiku-4-5`.
- `tests/test_supervisor.py::test_build_thinking_enabled`: ajustado para
  `{type: adaptive, effort: high}`.
- `tests/test_output_compressor.py`: monkeypatch aponta para
  `compression.hook._compress_sql_result` (re-export binding resolvido em
  import time).

### Security

- Nenhuma alteração relevante nesta release.

### Observability

- `logs/audit.jsonl`: campos `cache_write_tokens`, `cache_read_tokens`,
  `cache_hit_rate`.
- `logs/memory_usage.jsonl`: hits, custo Sonnet, duração por função.
- `logs/compression.jsonl`: métricas de compressão por tool.
- `logs/sessions/<sid>.jsonl`: transcript completo append-only.
- `logs/sessions/<sid>.json`: checkpoint por sessão
  (`logs/checkpoint.json` continua como espelho da mais recente).
- `logs/summaries/<sid>.md`: resumo Haiku disparado a 80% do budget.

### Notes

- SDK `claude-agent-sdk==0.1.61` **não** expõe `extra_headers` nem
  `cache_control` — tarefas T0.2 (`token-efficient-tools` beta) e T5.1
  (prompt caching explícito) permanecem bloqueadas upstream
  (issue `anthropics/claude-agent-sdk-python#626`).
- O baseline de linhas de código pré-enxugamento está em
  `to_do/baseline_loc.txt` (2026-04-17): 52.314 LOC totais, 42.460
  prod-only, 13 agentes, 13 MCPs.

---

[Unreleased]: https://github.com/ThomazRossito/data-agents/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/ThomazRossito/data-agents/releases/tag/v1.0.0
