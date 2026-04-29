# Architecture

Documentação de arquitetura do data-agents-copilot.

## 🏗️ Diagrama de Sistema

```
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────┐
│   data-agent CLI     │    │  Chainlit Web UI     │    │   task files     │
│  (cli/main.py)       │    │  (ui/chainlit_app.py)│    │  (tasks/*.yaml)  │
└──────────┬───────────┘    └──────────┬───────────┘    └────────┬─────────┘
           │                           │                          │
           │   menu / agent / run      │   chat stream            │ runner.py
           └───────────────────────────┴──────────────────────────┘
                                       │
                                       ▼
              ┌───────────────────────────────────────────┐
              │              Supervisor (T1)              │
              │  - Governance auto-trigger (regex)        │
              │  - Workflow auto-detection (WF-01→07)     │
              │  - KB injection (constitution + domain)   │
              │  - Memory injection/extraction            │
              │  - QA Orchestrator (score ≥ 0.7)          │
              │  - Route task / Generate PRD              │
              └──────────────────┬────────────────────────┘
                                 │
   ┌──────┬────────┬────────┬────┴─────┬─────────┬──────────┬──────────┐
   ▼      ▼        ▼        ▼          ▼         ▼          ▼          ▼
naming  spark    sql   pipeline    quality   governance  devops   lakehouse
guard  expert  expert  architect   agent     auditor    engineer  engineer
(T2)   (T2)    (T2)    (T2)        (T2)       (T2)       (T2)      (T2)
   │      │        │        │                                    + 7 agentes
   └──────┴────────┴────────┴──────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
         kb/              memory/           workflow/
      (KB-First)     (episódica + decay)  (WF-01 a WF-07)
```

---

## 📁 Estrutura de Diretórios

```
data-agents-copilot/
├── agents/
│   ├── base.py                 # BaseAgent — agentic loop + skill/MCP injection
│   ├── loader.py               # Registry loader — parse *.md → AgentConfig
│   ├── supervisor.py           # Routing + KB + memory + workflows + QA
│   ├── health.py               # /health — conectividade Databricks/Fabric
│   ├── party.py                # Party Mode — execução paralela multi-agente
│   └── registry/               # 15 system prompts em markdown
├── cli/
│   ├── main.py                 # Entry point — argparse (data-agent command)
│   ├── menu.py                 # Menu interativo com questionary
│   └── runner.py               # Carrega e executa arquivos de tarefa YAML/MD
├── config/
│   └── settings.py             # Pydantic settings loader (.env)
├── hooks/
│   ├── audit_hook.py           # Audit logging (JSONL)
│   ├── cost_guard_hook.py      # Budget tracking + reset()
│   ├── security_hook.py        # check_input() + check_output() separados
│   └── output_compressor.py    # Compressão de output longo
├── integrations/
│   ├── fabricgov.py            # Wrapper CLI fabricgov (/assessment)
│   └── github_context.py       # Fetch contexto repo fabric-ci-cd
├── kb/
│   ├── constitution.md         # 30+ regras invioláveis
│   ├── sql-patterns/
│   ├── spark-patterns/
│   ├── spark-internals/
│   ├── pipeline-design/
│   ├── data-quality/
│   ├── governance/
│   ├── databricks-platform/
│   ├── databricks-ai/
│   ├── fabric/
│   ├── lakehouse-design/
│   ├── lakehouse-ops/
│   ├── genai/
│   ├── prompt-engineering/
│   ├── data-modeling/
│   ├── ci-cd/
│   ├── orchestration/
│   ├── testing/
│   └── shared/
├── mcp_servers/
│   ├── databricks_server.py    # MCP server standalone — 9 tools Databricks
│   └── fabric_server.py        # MCP server standalone — 8 tools Fabric
├── memory/
│   ├── types.py                # MemoryType, Memory dataclass, DECAY_CONFIG
│   ├── store.py                # MemoryStore CRUD + thread-safe
│   ├── retrieval.py            # retrieve_relevant_memories() — keyword local
│   ├── decay.py                # compute_decayed_confidence()
│   ├── extractor.py            # extract_and_save() via regex
│   ├── kg.py                   # KnowledgeGraph (entities + relations)
│   └── data/                   # user/ feedback/ architecture/ progress/ daily/
├── orchestrator/
│   ├── models.py               # TaskSpec, ScoreReport, ReviewResult
│   └── qa_orchestrator.py      # QA peer orchestrator (score ≥ 0.7, auto-ativo)
├── workflow/
│   ├── dag.py                  # WF-01 a WF-07 + detect_workflow()
│   └── executor.py             # execute_workflow() com handoff de contexto
├── evals/
│   ├── canonical_queries.yaml  # 13 queries, 9 domínios
│   └── runner.py               # CLI --domain, --id, --limit, --dry-run
├── tasks/                      # Repositório de task files versionados
│   ├── _template.yaml
│   ├── sql/
│   ├── spark/
│   ├── pipelines/
│   ├── governance/
│   ├── quality/
│   ├── devops/
│   └── workflows/
├── tests/                      # 233 testes, cobertura 83%
├── ui/
│   └── chainlit_app.py         # Web UI (Chainlit, lazy init)
├── resources/
│   ├── naming convention.md    # Source-of-truth das regras de naming
│   └── jobs.yml                # Config de jobs Databricks
├── logs/
├── output/
│   ├── prd/                    # PRDs gerados (sha1 filename)
│   └── workflows/              # Outputs de workflows
├── main.py                     # CLI legado (mantido para compatibilidade)
├── pyproject.toml
├── databricks.yml
└── Makefile
```

---

## 🔄 Request Flow

### Cenário 1: Comando Direto via CLI

```
1. User runs: data-agent naming "CREATE TABLE raw_customers (id INT)"
                         ↓
2. cli/main.py parses subcommand "naming" → cmd_agent(args)
                         ↓
3. _lazy_supervisor() → Supervisor() + loader.AGENT_COMMANDS["naming"]
                         ↓
4. supervisor._load_naming_convention_context() injects resources/naming convention.md
                         ↓
5. base.py._build_system() concatenates:
   - System prompt from naming_guard.md
   - Naming convention rules
   - Skills: [schema-validator, sql-optimizer]
   - MCPs: [databricks]
                         ↓
6. base.py.run() → OpenAI API
                         ↓
7. Agent returns result (approved/violations/suggestions)
                         ↓
8. cli/main.py exibe via Rich
```

### Cenário 2: Auto-Trigger (Naming Guard)

```
1. User runs: data-agent "CREATE TABLE raw_customers (id INT)"
   (sem subcomando explícito)
                         ↓
2. cli/main.py → supervisor.route(task)
                         ↓
3. supervisor._TABLE_CREATION_PATTERN.search(task) → match
                         ↓
4. supervisor.route() returns naming_guard automaticamente
                         ↓
5. naming_guard valida e retorna approved/violations
```

### Cenário 3: Task File com `agent: auto`

```
1. User runs: data-agent run tasks/workflows/implantacao_lakehouse.yaml
                         ↓
2. cli/runner.load_task_file() → parse YAML → {agent: "auto", task: "..."}
                         ↓
3. runner._dispatch("auto", task_text) → supervisor.route(task)
                         ↓
4. detect_workflow(task) verifica WF_TRIGGER_PATTERNS (WF-01→07)
   OU supervisor._plan_and_delegate():
     - Gera PRD → output/prd/<sha1>.md
     - Extrai nome do agente via regex
                         ↓
5. Agente especialista executa e retorna resultado
                         ↓
6. runner._save_output() salva em output/ se campo output definido
```

---

## 🧠 Agent Hierarchy

### Tier System

| Tier | Model | Cost | Speed | Use Case |
|------|-------|------|-------|-----------|
| **T1** | claude-sonnet-4-6 | $$$ | 2-5s | Routing, PRD, QA Orchestrator, planning |
| **T2** | gpt-4.1 | $$ | 1-3s | Domínio (Spark, SQL, naming, lakehouse…) |
| **T3** | gpt-4.1-mini | $ | 0.5-1s | Q&A simples, conceitual, help |

### Agent Specialization

#### Supervisor (T1)
- **Model**: claude-sonnet-4-6
- **Purpose**: Route tasks, detect intent, generate PRDs
- **Skills**: (injected dynamically based on PRD)
- **MCPs**: [] — nunca acessa MCP diretamente; delega para especialistas
- **Auto-Triggers**:
  - `CREATE TABLE` → naming_guard
  - `SELECT * FROM table LIMIT...` → (none, handle via routing)
  - Complex task → PRD generation → specialist

#### Naming Guard (T2)
- **Model**: gpt-4.1
- **Purpose**: Validate naming conventions
- **Skills**: [schema-validator, sql-optimizer]
- **MCPs**: [databricks]
- **Input**: SQL DDL + naming rules
- **Output**: ✅ Approved | ❌ Violations + suggestions
- **Auto-Trigger**: CREATE TABLE (regex pattern)

#### Spark Expert (T2)
- **Model**: gpt-4.1
- **Purpose**: PySpark optimization, debugging, architecture
- **Skills**: [pyspark-expert, spark-optimization]
- **MCPs**: [databricks]

#### SQL Expert (T2)
- **Model**: gpt-4.1
- **Purpose**: Query optimization, CTEs, window functions
- **Skills**: [sql-optimizer, sql-queries]
- **MCPs**: [databricks]

#### Pipeline Architect (T2)
- **Model**: gpt-4.1
- **Purpose**: ETL/ELT design, SCD patterns, orchestration
- **Skills**: [data-engineer, pipeline-reviewer]
- **MCPs**: [databricks, fabric]

#### Governance Auditor (T2)
- **Model**: gpt-4.1
- **Purpose**: PII, LGPD, data access controls
- **Skills**: [data-docs, senior-data-engineer]
- **MCPs**: [databricks, fabric]

#### dbt Expert (T2)
- **Model**: gpt-4.1
- **Purpose**: dbt models, snapshots, incremental, tests
- **Skills**: [data-engineer]

#### Python Expert (T2)
- **Model**: gpt-4.1
- **Purpose**: Python puro, testes, utilitários
- **Skills**: [python-expert]

#### Fabric Expert (T2)
- **Model**: gpt-4.1
- **Purpose**: Lakehouse, OneLake, Direct Lake, Fabric CI/CD
- **Skills**: [fabric-lakehouse]
- **MCPs**: [fabric]

#### Lakehouse Engineer (T2)
- **Model**: gpt-4.1
- **Purpose**: Implantação, migração, sustentação de lakehouse
- **Skills**: [fabric-lakehouse, senior-data-engineer]
- **MCPs**: [databricks, fabric]

#### Databricks AI (T2)
- **Model**: gpt-4.1
- **Purpose**: Agent Bricks, Genie, MLflow, Unity Catalog AI
- **Skills**: [databricks-docs]
- **MCPs**: [databricks]

#### DevOps Engineer (T2)
- **Model**: gpt-4.1
- **Purpose**: DABs, Azure DevOps, Fabric CI/CD, GitHub Actions
- **Skills**: [databricks-asset-bundles, databricks-ci-integration]
- **MCPs**: [databricks]

#### QA Reviewer (T1)
- **Model**: claude-sonnet-4-6
- **Purpose**: Revisar spec e delivery (score 0-1, threshold 0.7)
- Ativo automaticamente em todos os inputs não-comando

#### General Agent (T3)
- **Model**: gpt-4.1-mini
- **Purpose**: Q&A conceitual, tarefas simples, sem MCP

---

## 🎯 Key Design Patterns

### 1. Skill Injection

Skills are `.md` files loaded at runtime into agent context:

```python
# agents/base.py
def _build_system(self) -> str:
    system = self.config.system_prompt
    for skill_name in self.config.skills:
        skill = self._load_skill(skill_name)
        system += f"\n\n## Skill: {skill_name}\n{skill}"
    return system
```

**Benefits**:
- No hardcoding of knowledge
- Skills versioned in ~/.claude/skills/
- Easy to add/remove capabilities without agent code changes

### 2. MCP Integration

MCPs (Model Context Protocol) provide read-only data access:

```python
# agents/base.py (conceptual)
def _dispatch_tool(self, tool_name: str, args: dict) -> str:
    if tool_name == "mcp:databricks:list_tables":
        return mcp_databricks.list_tables(**args)
    elif tool_name == "mcp:fabric:list_schemas":
        return mcp_fabric.list_schemas(**args)
```

**Supported MCPs**:
- `databricks` — Clusters, jobs, tables, notebooks
- `fabric` — Lakehouses, warehouses, datasets, schemas

### 3. Context Auto-Injection

Naming convention context injected automatically for naming_guard:

```python
# agents/supervisor.py
def _load_naming_convention_context(self) -> str:
    content = NAMING_CONVENTION_FILE.read_text()
    return "Use estritamente as convenções:\n\n" + content
```

**Pattern**: Supervisor loads template → passes to specialist → specialist uses as guidance

### 4. Regex-Based Intent Detection

Pattern matching for auto-triggering:

```python
_TABLE_CREATION_PATTERN = re.compile(
    r"\b(create\s+(or\s+replace\s+)?table|"
    r"criar\s+(uma\s+)?(nova\s+)?tabela)\b",
    re.IGNORECASE
)
```

**Flexibility**: Captures:
- ✅ `CREATE TABLE t1 (...)`
- ✅ `CREATE OR REPLACE TABLE t1 (...)`
- ✅ `criar nova tabela t1 (...)`
- ✅ Multi-line queries

---

## � Knowledge Base (`kb/`)

**KB-First Protocol**: o supervisor consulta o KB antes de delegar.

1. Carrega `kb/constitution.md` em toda chamada (regras invioláveis).
2. Infere domínio da tarefa → carrega `kb/<dominio>/index.md`.
3. Injeta conteúdo relevante no system prompt do agente.
4. Somente se KB for insuficiente, delega para skills ou MCP.

```
kb/
├── constitution.md          ← sempre injetado
├── sql-patterns/
│   ├── index.md             ← sumário + links
│   ├── ddl-patterns.md
│   └── window-functions.md
├── spark-patterns/
│   ├── index.md
│   ├── delta-lake.md
│   └── structured-streaming.md
├── pipeline-design/
│   ├── index.md
│   └── medallion-pattern.md
├── data-quality/
│   ├── index.md
│   └── expectations.md
├── governance/
│   ├── index.md
│   └── pii-handling.md
└── shared/
    └── anti-patterns.md
```

---

## 🧠 Memory System (`memory/`)

Memória episódica file-based com decay temporal.

### Tipos

| Tipo | Arquivo | Decay | Uso |
|------|---------|-------|-----|
| `USER` | `data/user/` | nunca | Preferências do usuário |
| `ARCHITECTURE` | `data/architecture/` | nunca | Decisões arquiteturais |
| `FEEDBACK` | `data/feedback/` | 5%/dia | Correções e ajustes |
| `PROGRESS` | `data/progress/` | 10%/dia | Status de tasks |

### Fluxo

```
Supervisor.route(task)
    ↓
_load_memory_context()
  → retrieve_relevant_memories(task, store, max_memories=5)
  → keyword matching nos campos summary + tags
  → compute_decayed_confidence() → filtra < 0.1
    ↓
Injeção no system prompt do agente escolhido
    ↓
Resposta gerada
    ↓
_save_memory()
  → extract_and_save(task, response, store)
  → detecta padrões (ARCHITECTURE, PROGRESS) via regex
  → persiste em memory/data/<tipo>/<id>.md (YAML frontmatter)
```

Sem chamada extra de LLM. Recuperação puramente local (keyword matching).

---

## ⚙️ Workflow Engine (`workflow/`)

4 workflows multi-agente com encadeamento sequencial.

### Definição

Cada `WorkflowDef` tem:
- `id`: WF-01 a WF-04
- `steps`: lista de `{agent_name, description, output_key}`
- Trigger: `WF_TRIGGER_PATTERNS` dict de regex

### Fluxo de execução

```
detect_workflow(task)          # regex match
    ↓
WorkflowDef selecionado
    ↓
execute_workflow(wf, task, agents)
    ↓ (para cada step)
  build context handoff:
    context = {output_key_anterior: resultado_anterior}
  agent.run(task + context)
    ↓
Resultado final salvo em output/workflows/<wf_id>/<timestamp>.md
```

### Workflows disponíveis

| ID | Trigger | Agentes |
|----|---------|--------|
| WF-01 | `pipeline completo, bronze até gold` | pipeline_architect → spark_expert → data_quality |
| WF-02 | `star schema, camada gold, modelo dimensional` | pipeline_architect → sql_expert → data_quality |
| WF-03 | `migrar para Fabric / Databricks` | pipeline_architect → spark_expert → sql_expert |
| WF-04 | `auditoria, governança completa, compliance` | naming_guard → data_quality → pipeline_architect |
| WF-05 | `implantar lakehouse, novo lakehouse` | pipeline_architect → lakehouse_engineer → data_quality → governance_auditor → devops_engineer |
| WF-06 | `migrar lakehouse, migrar Synapse` | diagnóstico → arquitetura → pipeline → qualidade → governança → devops |
| WF-07 | `sustentação, otimizar lakehouse, vacuum` | monitoramento → otimização → custo → relatório |

---

## �🔐 Security & Governance

### Hooks System

#### 1. Audit Hook (`hooks/audit_hook.py`)
- Logs ALL agent API calls
- Stores: timestamp, agent, model, tokens, cost
- Output: `logs/audit.log`

#### 2. Cost Guard (`hooks/cost_guard_hook.py`)
- Tracks session cost per model
- Enforces MAX_COST_PER_SESSION limit
- Blocks execution if limit exceeded
- Alerts user before expensive operations (T1 model)

#### 3. Security Hook (`hooks/security_hook.py`)
- Filters sensitive data:
  - Secrets (DATABRICKS_TOKEN, Azure secrets, API keys)
  - PII patterns (SSN, credit card, email in logs)
  - SQL passwords
- Strips before logging

### Configuration

Hooks controlled via `.env`:

```bash
ENABLE_AUDIT_HOOK=true
ENABLE_COST_GUARD_HOOK=false
ENABLE_SECURITY_HOOK=true
MAX_COST_PER_SESSION=50.0
```

---

## 📊 Dataflow: Naming Convention Governance

```
┌──────────────────────────────┐
│ resources/naming            │
│ convention.md               │
│ (source of truth)           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ User: CREATE TABLE raw_customers (...)      │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Supervisor.route()                          │
│ → _TABLE_CREATION_PATTERN.search() matches  │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Supervisor._load_naming_convention_context()│
│ → Read resources/naming convention.md       │
│ → Inject as context to naming_guard         │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Naming Guard Agent (T2, gpt-4.1)             │
│ - System prompt + naming rules              │
│ - Skills: schema-validator, sql-optimizer  │
│ - MCPs: Databricks (read schema metadata)   │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│ Validation Result:                          │
│ ✅ Approved / ❌ Violations                  │
│ - Violations: [list of rules broken]        │
│ - Suggestions: [corrected SQL]              │
└─────────────────────────────────────────────┘
```

---

## 🚀 Performance Considerations

### API Call Optimization

**Tier-based fallback** to minimize cost:

```python
# supervisor.py (conceptual)
if simple_query:
    agent = geral_agent  # T3, gpt-4.1-mini (cheap)
elif domain_specific:
    agent = specialist_agent  # T2, gpt-4.1 (fast)
else:
    agent = supervisor_agent  # T1, claude-sonnet-4-6 (smart)
```

**Expected savings**: ~80% reduction vs. always using T1

### Caching Strategies

- **Skills cached** in-memory after first load
- **Agent configs cached** after registry parse
- **Naming convention** read once, reused for session

### Parallel Processing

Future: Use `asyncio` for parallel skill loading and MCP calls.

---

## 🔗 Dependencies

### Core

```toml
openai = ">=1.0.0"              # GitHub Copilot API
pydantic = ">=2.0.0"            # Settings validation
typer = ">=0.9.0"               # CLI framework
rich = ">=13.0.0"               # Pretty output
python-dotenv = ">=1.0.0"       # .env loader
```

### Optional (Data Platforms)

```toml
databricks-sdk = ">=0.8.0"      # Databricks MCP
azure-storage-blob = ">=12.0.0" # Azure MCP
```

### Development

```toml
pytest = ">=7.0.0"              # Testing
mypy = ">=1.0.0"                # Type checking
ruff = ">=0.1.0"                # Linting
black = ">=23.0.0"              # Formatting
```

---

## 📈 Future Roadmap

### Phase 1: Cost Optimization ✅ (v1.0.0)
- [x] Tier-based agent selection
- [x] Naming Guard auto-trigger
- [ ] Cost estimation before running

### Phase 2: Observability (Q1 2025)
- [ ] Metrics dashboard (success rate, latency, cost)
- [ ] Trace view (agent → skill → MCP call path)
- [ ] Alert system (job failures, cost overruns)

### Phase 3: Advanced Governance (Q2 2025)
- [ ] Policy engine (enforce rules at runtime)
- [ ] Approval workflows (for breaking changes)
- [ ] Lineage tracking (table → agent → PRD)

### Phase 4: Multi-Language (Q3 2025)
- [ ] English interface (currently PT-BR)
- [ ] System prompt templates for multiple locales

---

## 📚 References

- [GitHub Copilot Chat API](https://docs.github.com/en/copilot/using-github-copilot/getting-started-with-github-copilot-chat)
- [OpenAI API](https://platform.openai.com/docs/api-reference)
- [Databricks SDK](https://docs.databricks.com/dev-tools/sdk-python)
- [Microsoft Fabric](https://learn.microsoft.com/en-us/fabric)
- [Original: data-agents (ThomazRossito)](https://github.com/ThomazRossito/data-agents)

---

Questions? Open an [issue](https://github.com/arthurfr23/data-agents-copilot/issues) or [discussion](https://github.com/arthurfr23/data-agents-copilot/discussions).
