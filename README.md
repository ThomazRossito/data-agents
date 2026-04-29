# data-agents-copilot

**Orquestrador multi-agente para engenharia de dados com GitHub Copilot integrado.**

Sistema de despacho automático que roteia tarefas de dados (SQL, PySpark, pipelines, governança) para 15 agentes IA especializados. Executado via CLI, Chainlit web, ou diretamente no VS Code Chat.

---

## 🎯 O Que É

`data-agents-copilot` é um fork do projeto original [data-agents](https://github.com/ThomazRossito/data-agents) de **Thomaz Rossito** — adaptado para operar com **GitHub Copilot Chat API**, adicionando governança automática de nomenclatura, workflows colaborativos multi-agente, Knowledge Base estruturada, sistema de memória episódica, e protocolo QA peer-to-peer.

### Principais Diferenças em Relação ao Original

| Aspecto | Original | data-agents-copilot |
|---------|----------|---------------------|
| **LLM SDK** | Anthropic Claude SDK | GitHub Copilot Chat API (GPT-4.1 / claude-sonnet-4-6) |
| **Agentes** | 13 agentes | **15 agentes especializados** |
| **Workflows** | WF-01 a WF-05 | **WF-01 a WF-07 implementados** com auto-trigger |
| **Memória** | Episódica | Episódica + decay temporal + Knowledge Graph |
| **KB** | Sem KB | **`kb/` com 18 domínios** + constitution |
| **QA** | — | **QA Orchestrator automático** (score 0-1, threshold 0.7) |
| **MCPs** | 15 MCPs | 2 MCPs (Databricks, Fabric) + 2 servidores MCP standalone |
| **Evals** | — | **13 queries canônicas**, 9 domínios |

---

## 📦 Estrutura

```
data-agents-copilot/
├── agents/
│   ├── registry/           # 15 agentes (system prompts em markdown)
│   │   ├── supervisor.md
│   │   ├── spark_expert.md
│   │   ├── sql_expert.md
│   │   ├── pipeline_architect.md
│   │   ├── data_quality.md
│   │   ├── naming_guard.md
│   │   ├── governance_auditor.md
│   │   ├── dbt_expert.md
│   │   ├── python_expert.md
│   │   ├── fabric_expert.md
│   │   ├── databricks_ai.md
│   │   ├── devops_engineer.md
│   │   ├── lakehouse_engineer.md
│   │   ├── geral.md
│   │   └── qa_reviewer.md
│   ├── tools/              # MCP tools nativas (Databricks + Fabric)
│   ├── loader.py           # Parser do registry + AGENT_COMMANDS
│   ├── base.py             # Classe base BaseAgent (loop OpenAI)
│   ├── health.py           # /health check
│   ├── party.py            # Party Mode (execução paralela)
│   └── supervisor.py       # Roteador principal
├── orchestrator/
│   ├── models.py           # TaskSpec, ScoreReport, ReviewResult
│   └── qa_orchestrator.py  # QA peer orchestrator (auto-ativo)
├── workflow/
│   ├── dag.py              # WF-01 a WF-07 + detect_workflow()
│   └── executor.py         # execute_workflow() com handoff de contexto
├── memory/
│   ├── store.py            # MemoryStore CRUD + thread-safe
│   ├── retrieval.py        # retrieve_relevant_memories()
│   ├── extractor.py        # extract_and_save() via regex
│   ├── decay.py            # compute_decayed_confidence()
│   ├── kg.py               # KnowledgeGraph (entities + relations)
│   └── types.py            # MemoryType, Memory dataclass
├── hooks/
│   ├── audit_hook.py       # Registro JSONL de execuções
│   ├── cost_guard_hook.py  # Budget tracking + reset()
│   ├── security_hook.py    # check_input() + check_output()
│   └── output_compressor.py
├── integrations/
│   ├── fabricgov.py        # fabricgov CLI wrapper
│   └── github_context.py   # fabric-ci-cd context fetch
├── mcp_servers/
│   ├── databricks_server.py  # MCP server standalone (Databricks)
│   └── fabric_server.py      # MCP server standalone (Fabric)
├── evals/
│   ├── canonical_queries.yaml  # 13 queries, 9 domínios
│   └── runner.py               # CLI --domain, --id, --limit, --dry-run
├── kb/                     # 18 domínios de conhecimento
│   ├── constitution.md
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
├── config/
│   └── settings.py         # Pydantic settings (GITHUB_TOKEN opcional)
├── ui/
│   └── chainlit_app.py     # Interface web (lazy init em on_chat_start)
├── resources/
│   ├── naming convention.md   # Convenções editáveis
│   └── jobs.yml               # Config de jobs Databricks
├── tests/                  # 215 testes, cobertura 83%
├── output/
│   ├── prd/                # PRDs gerados (sha1 filename)
│   └── workflows/          # Outputs de workflows
└── main.py                 # CLI entry point
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/arthurfr23/data-agents-copilot.git
cd data-agents-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # preencher GITHUB_TOKEN
```

### Execução

```bash
# Menu interativo
data-agent

# Acesso direto ao agente
data-agent spark "otimize pipeline Bronze→Silver incremental"
data-agent sql "modele star schema para vendas com SCD2"
data-agent naming "CREATE TABLE raw_customers (id INT)"

# Executar arquivo de tarefa versionado
data-agent run tasks/sql/review_query_pedidos.yaml
data-agent run tasks/spark/scd2_clientes.md
data-agent run tasks/pipelines/              # pasta inteira

# Utilitários
data-agent health    # status das plataformas
data-agent list      # agentes disponíveis
data-agent tasks     # arquivos em tasks/

# Interface web Chainlit
make ui

# Evals
make evals                         # todas as queries
make evals-domain DOMAIN=sql       # por domínio
```

Ver [QUICK_START.md](QUICK_START.md) para guia completo incluindo formato dos arquivos de tarefa.

---

## 🤖 Agentes e Comandos

| Comando | Agente | Domínio |
|---------|--------|---------|
| `/plan <tarefa>` | Supervisor | Tarefas complexas com PRD |
| `/spark <tarefa>` | Spark Expert | PySpark, Delta Lake, DLT |
| `/sql <tarefa>` | SQL Expert | Queries, modelagem, Unity Catalog |
| `/pipeline <tarefa>` | Pipeline Architect | ETL/ELT |
| `/quality <tarefa>` | Data Quality | Validação, DQX, profiling |
| `/naming <tarefa>` | Naming Guard | Auditoria de nomenclatura |
| `/governance <tarefa>` | Governance Auditor | PII, LGPD, controles |
| `/dbt <tarefa>` | dbt Expert | Models, snapshots, incremental |
| `/python <tarefa>` | Python Expert | Código Python, testes |
| `/fabric <tarefa>` | Fabric Expert | Lakehouse, OneLake, Direct Lake |
| `/lakehouse <tarefa>` | Lakehouse Engineer | Implantação, migração |
| `/ops <tarefa>` | Lakehouse Engineer | Manutenção, incidente, custo |
| `/ai <tarefa>` | Databricks AI | Agent Bricks, Genie, MLflow |
| `/devops <tarefa>` | DevOps Engineer | DABs, Azure DevOps, Fabric CI/CD |
| `/geral <tarefa>` | Geral | Conceitual, sem MCP |
| `/review <artefato>` | Supervisor | Review de código/pipeline |
| `/party <tarefa>` | Party Mode | Multi-agente paralelo |
| `/assessment [--days N]` | fabricgov + Governance Auditor | Assessment Fabric |
| `/health` | — | Status de conectividade |
| `/kg list\|lineage\|add` | — | Knowledge Graph |
| `/sessions` | — | Histórico de sessões |
| `/resume [task]` | — | Retomar última sessão |

**Auto-triggers** (sem comando):
- `CREATE TABLE / ALTER TABLE / DROP TABLE` → Naming Guard
- `pipeline`, `bronze`, `silver`, `gold`, `lakehouse`, `fabric`... → PRD + delegação
- Padrões de workflow → WF-01 a WF-07 encadeados

---

## ⚙️ Workflows Colaborativos

| ID | Trigger | Etapas |
|----|---------|--------|
| WF-01 | `pipeline completo, end-to-end, bronze até gold` | 2 agentes |
| WF-02 | `star schema, camada gold, modelo dimensional` | 3 agentes |
| WF-03 | `migrar para Fabric / Databricks` | 3 agentes |
| WF-04 | `auditoria, governança completa, compliance` | 3 agentes |
| WF-05 | `implantar lakehouse, novo lakehouse, setup lakehouse` | 5 agentes |
| WF-06 | `migrar lakehouse, migrar Synapse` | 6 agentes |
| WF-07 | `sustentação, otimizar lakehouse, vacuum, observabilidade` | 4 agentes |

---

## 🔐 Segurança & Governança

### Políticas Separadas

```python
# Input do usuário — bloqueia destrutivos + queries não qualificadas
ok, reason = security_hook.check_input(user_input)

# Output de agente — bloqueia só destrutivos reais (não bloqueia docs SQL)
ok, reason = security_hook.check_output(agent_result.content)
```

Padrões bloqueados no **input**: `DROP TABLE`, `TRUNCATE`, `rm -rf`, `git push --force`, `.env`, `.ssh/`, `DELETE FROM` sem WHERE, `SELECT *` sem WHERE/LIMIT.

Padrões bloqueados no **output**: apenas os destrutivos — agentes podem gerar documentação com `SELECT *` normalmente.

---

## 🧪 Testes

```bash
GITHUB_TOKEN=test pytest tests/ -v --cov --cov-fail-under=80
```

233 testes, cobertura 83%, ruff=0.

---

## 🏗️ Arquitetura

Ver [ARCHITECTURE.md](ARCHITECTURE.md) para diagramas de sistema, fluxo de roteamento e decisões de design.

---

## 📚 Documentação

- [Agentes](agents/registry/) — System prompts, tiers, skills, MCPs
- [Arquitetura](ARCHITECTURE.md) — Diagramas e decisões de design
- [Convenções de Nomenclatura](resources/naming%20convention.md) — Editável, fonte de verdade
- [Knowledge Base](kb/) — 18 domínios + constitution

---

## 🤝 Contribuindo

Ver [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📄 Licença

Fork de [ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents) — MIT License. Ver [LICENSE.md](LICENSE.md).

