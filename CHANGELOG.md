> All notable changes to this project are documented here.
>
> Format: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
> Versioning: [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

# Changelog

## [Unreleased]

### Removed

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

### Gated (aguardando telemetria)

- **T1.7** — Decidir Caminho A vs B da memória (`logs/memory_usage.jsonl` 24-72h).
- **T2.5** — Dashboard de cache hit rate (`logs/audit.jsonl` acumulado).
- **T4.5** — Decisão final Caminho A da memória (6 semanas de métricas).

### Backlog

- ~~**T0.2.1**~~ — Issue aberta em
  [`anthropics/claude-agent-sdk-python#845`](https://github.com/anthropics/claude-agent-sdk-python/issues/845)
  pedindo passthrough de `extra_headers` (ou relaxar `SdkBeta`) para
  opt-in em `anthropic-beta: token-efficient-tools-2025-02-19` (~10-14%
  menos output tokens em workloads de tool use).
- **T5.1** — Prompt caching explícito no Supervisor. **Confirmado bloqueado em
  SDK 0.1.63**: `SdkBeta` aceita apenas `context-1m-2025-08-07`, sem campo
  `cache_control` nem `extra_headers`. Issue #626 (upstream) segue aberta.
  Caching implícito via `agents/cache_prefix.md` byte-idêntico continua ativo.

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
- **Auto-fire do summarizer** em `hooks/context_budget_hook.py`: dispara uma
  vez por sessão ao cruzar `context_budget_summarize_threshold` (0.65),
  persiste em `logs/summaries/<sid>.md`.
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
- `logs/summaries/<sid>.md`: resumo Haiku disparado a 65% do budget.

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
