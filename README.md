<p align="center">
  <img src="img/readme/banner.png" alt="Data Agents Banner" width="100%">
</p>

<p align="center">
  <h1 align="center">Data Agents</h1>
  <p align="center">
    <strong>Sistema Multi-Agentes para Engenharia de Dados, Análise e MLOps Corporativo</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Version-0.1.0-brightgreen.svg" alt="Version 0.1.0">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Databricks-MCP-FF3621.svg" alt="Databricks MCP">
    <img src="https://img.shields.io/badge/Microsoft%20Fabric-MCP-0078D4.svg" alt="Fabric MCP">
    <img src="https://img.shields.io/badge/Anthropic-Claude%20SDK-D97757.svg" alt="Claude SDK">
    <img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg" alt="CI/CD">
  </p>
</p>

Construído sobre o **Claude Agent SDK** da Anthropic com integração nativa via **Model Context Protocol (MCP)** ao **Databricks** e **Microsoft Fabric**. Este ecossistema transforma o seu assistente de IA em um verdadeiro arquiteto e executor de engenharia de dados, operando recursos diretamente nas suas nuvens corporativas — gerando pipelines modernos com **Spark Declarative Pipelines (SDP/LakeFlow)**, **Liquid Clustering**, **Medallion Architecture** e **V-Order** para Direct Lake.

---

## 👤 Autor

> ## Thomaz Antonio Rossito Neto
> Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T | Enterprise AI Agents, Microsoft Fabric & Databricks Expert

## Educação Acadêmica

> **MBA: Ciência de Dados com ênfase em Big Data**
> **MBA: Engenharia de Dados com ênfase em Big Data**

## Contatos

> **LinkedIn:** [https://www.linkedin.com/in/thomaz-antonio-rossito-neto/](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/)
> **GitHub:** [https://github.com/ThomazRossito/](https://github.com/ThomazRossito/)

---

#### 🏆 Profissional Certificado Databricks

<img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134719" alt="Databricks Certified Spark Developer" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/169321258" alt="Databricks Certified Generative AI Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/167127257" alt="Databricks Certified Data Analyst Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134780" alt="Databricks Certified Data Engineer Associate" width="155"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/157011932" alt="Databricks Certified Data Engineer Professional" width="155"/>

[Todas as certificações](https://credentials.databricks.com/profile/thomazantoniorossitoneto39867/wallet)

---

#### 🏆 Profissional Certificado Microsoft

<a href="https://www.credly.com/badges/052e5133-0c67-4ab7-bb3a-c99efa7b4406/public_url" target="_blank">
  <img src="https://images.credly.com/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/azure-data-fundamentals-600x600.png" alt="Microsoft Certified: Azure Data Fundamentals (DP-900)" width="155"/>
</a>
<a href="https://learn.microsoft.com/pt-br/users/thomazantoniorossitoneto/credentials/certification/fabric-data-engineer-associate" target="_blank">
  <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310419663028569643/ftqfVZsrmaGyfUha.png" alt="Microsoft Certified: Fabric Data Engineer Associate (DP-700)" width="155"/>
</a>

[Todas as certificações](https://www.credly.com/users/thomaz-antonio-rossito-neto/badges#credly)

---

## 🏗️ Visão Geral e Arquitetura

O **Data Agents** é projetado para atuar como uma *squad* autônoma de dados. Através de um Supervisor de Agentes e o **Método BMAD** (Breakthrough Method for Agile AI-Driven Development), a sua intenção em linguagem natural é orquestrada para especialistas capacitados em SQL, Spark e Pipelines de Dados.

O diferencial deste projeto é o seu **Hub de Conhecimento (Skills)**. Os agentes não apenas geram códigos genéricos, mas **nativamente leem documentações oficiais e guias de melhores práticas armazenados no repositório** antes de qualquer geração de código. O Supervisor consulta os skills relevantes (**Context Engineering**) para garantir que o PRD e os artefatos sigam os padrões arquiteturais mais modernos, incluindo:

- **Spark Declarative Pipelines (SDP/LakeFlow)** — `from pyspark import pipelines as dp`, `STREAMING TABLE`, `AUTO CDC INTO`, `CLUSTER BY`
- **Liquid Clustering** — substitui `PARTITION BY + ZORDER BY` (deprecated)
- **V-Order** — otimização Parquet para Direct Lake/Power BI no Microsoft Fabric
- **Medallion Architecture** — Bronze (cloud_files) → Silver (STREAMING TABLE + AUTO CDC) → Gold (MATERIALIZED VIEW)

<p align="center">
  <img src="img/readme/architecture.png" alt="Arquitetura Multi-Agent System" width="100%">
</p>

---

## 🤖 Agentes Especialistas

| Agente | Modelo | Papel e Responsabilidades |
|---|---|---|
| **Supervisor** | `claude-opus-4-6` | Líder técnico. Recebe a requisição, quebra em subtarefas, lê os *skills* necessários (Context Engineering), cria PRDs e aciona o especialista correto via BMAD. |
| **SQL Expert** | `claude-sonnet-4-6` | Especialista em dados relacionais, analítica e modelagem (KQL, T-SQL, Spark SQL). Consulta metadados *read-only*, analisa schemas Fato/Dimensão e gera SQL com Liquid Clustering. |
| **Spark Expert** | `claude-sonnet-4-6` | Ás da Engenharia Big Data. **Focado exclusivamente em geração de código SDP/LakeFlow moderno** — lê obrigatoriamente os SKILL.md antes de gerar qualquer pipeline. |
| **Pipeline Architect** | `claude-sonnet-4-6` | Engenheiro DataOps/SRE. Único com permissões amplas de execução. Automatiza pipelines completos, gerencia DABs, Workflows e integrações cross-platform Databricks ↔ Fabric. |

---

## 🗂️ Método BMAD

O **BMAD (Breakthrough Method for Agile AI-Driven Development)** é o protocolo de orquestração central do projeto. Ele garante qualidade arquitetural em vez de geração de código "no escuro".

```
Passo 0: Triage       — Supervisor identifica o tipo de tarefa
Passo 1: Context Eng. — Lê os SKILL.md relevantes antes de qualquer ação
Passo 2: PRD          — Documenta arquitetura em output/prd_*.md e aguarda aprovação
Passo 3: Delegação    — Aciona o agente especialista com contexto rico
Passo 4: Síntese      — Valida e consolida os artefatos produzidos
```

**Modos disponíveis:**

| Modo | Comando | Descrição |
|---|---|---|
| **BMAD Full** | `/plan` | Fluxo completo com PRD e aprovação antes de delegar |
| **BMAD Express** | `/sql`, `/spark`, `/pipeline`, `/fabric` | Bypass do PRD — vai direto ao agente especialista |
| **Internal** | `/health`, `/status`, `/review` | Diagnóstico, listagem de PRDs e revisão de artefatos |

---

## 📋 Pré-Requisitos e Credenciais

1. **Python 3.11+**: Recomenda-se instalação via `pyenv` ou `virtualenv`.
2. **.NET SDK 8.0+**: Necessário para o servidor MCP oficial do Microsoft Fabric.
3. **Anthropic API**: Variável `ANTHROPIC_API_KEY` (obrigatória).
4. **Databricks**: CLI configurado + `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_SQL_WAREHOUSE_ID`.
5. **Microsoft Fabric**: Azure CLI autenticado (`az login`) ou Service Principal (`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`) + `FABRIC_WORKSPACE_ID`.
6. **Fabric RTI (Real-Time Intelligence)**: `KUSTO_SERVICE_URI` e `KUSTO_SERVICE_DEFAULT_DB`.

> **Diagnóstico automático de startup**: ao iniciar `main.py`, o sistema valida automaticamente quais plataformas têm credenciais configuradas e emite warnings/errors para as que estiverem faltando.

---

## 🚀 Configuração Rápida

```bash
# 1. Clone o repositório
git clone git@github.com:ThomazRossito/data-agents.git
cd data-agents

# 2. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Instale as dependências
pip install -e "."          # produção
pip install -e ".[dev]"     # + ferramentas de desenvolvimento

# 4. Configure as credenciais
cp .env.example .env
# Edite .env com suas credenciais

# 5. Inicie o sistema
python main.py
# ou usando o entry point instalado:
data-agents
```

---

## 💬 Slash Commands Disponíveis

Digite `/help` no CLI para ver a lista completa. Os comandos disponíveis são:

| Comando | Modo | Agente | Descrição |
|---|---|---|---|
| `/sql <tarefa>` | Express | sql-expert | Geração de SQL, análise e modelagem dimensional |
| `/spark <tarefa>` | Express | spark-expert | Pipelines SDP/LakeFlow, Structured Streaming, PySpark |
| `/pipeline <tarefa>` | Express | pipeline-architect | Pipelines completos, DABs, DataOps |
| `/fabric <tarefa>` | Express | pipeline-architect | Microsoft Fabric: Lakehouse, Direct Lake, Data Factory |
| `/plan <tarefa>` | Full | supervisor | Cria PRD completo em `output/` e aguarda aprovação |
| `/health` | Internal | supervisor | Verifica conectividade com Databricks e Fabric via MCP |
| `/status` | Internal | supervisor | Lista PRDs gerados em `output/` com resumos |
| `/review [arquivo]` | Internal | supervisor | Revisita um PRD existente para continuar ou ajustar |
| `/help` | — | — | Exibe ajuda com todos os comandos |
| `sair` / `exit` | — | — | Encerra a sessão |
| `limpar` / `clear` | — | — | Limpa a tela e inicia nova sessão |

---

## 💡 Exemplos Práticos

**Databricks — Lakeflow / SDP:**

```
/plan Crie um pipeline SDP com STREAMING TABLEs e AUTO CDC INTO para
e-commerce (Bronze→Silver→Gold, Star Schema). Salvar em output/databricks/.
```

```
/spark Implemente a camada Silver com SCD Type 2 usando AUTO CDC INTO,
lendo o PRD salvo em output/.
```

**Databricks — SQL e Modelagem:**

```
/sql Analise o schema da tabela raw.transactions e gere a DDL Delta com
Liquid Clustering por (data_evento, categoria).
```

**Microsoft Fabric — Lakehouse + Direct Lake:**

```
/fabric Crie um pipeline Medallion no Fabric com V-Order ativo em todas as
camadas para garantir performance máxima no Direct Lake do Power BI.
```

**Microsoft Fabric — RTI / Eventhouse:**

```
/fabric Otimize esta query KQL para o Eventhouse usando filtros temporais
e políticas de caching conforme as melhores práticas.
```

**Diagnóstico e Monitoramento:**

```
/health
```

---

## 🎯 Fluxo BMAD na Prática

### Passo 1 — Context Engineering com `/plan`

```bash
data-agents
```

```
/plan Sou engenheiro de dados e preciso de um pipeline LakeFlow (SDP) com
AUTO CDC Tipo 2 e MATERIALIZED VIEWS para e-commerce, arquitetura Medallion
com Star Schema na Gold. Salvar em output/databricks/.
```

O que acontece:
1. Log: `[BMAD Agile] Iniciando Context Engineering — lendo skills relevantes...`
2. O Supervisor **lê os SKILL.md relevantes** (SDP, Unity Catalog, etc.), cria um PRD detalhado em `output/prd_<nome>.md` e apresenta o resumo para aprovação.

### Passo 2 — Implementação com BMAD Express

Após aprovar o PRD:

```
/sql Leia o PRD em output/ e implemente todos os scripts SQL conforme planejado,
salvando em output/databricks/.
```

O SQL Expert entra em ação, lê o PRD criado pelo Supervisor (sem alucinações de contexto), e gera os scripts seguindo os padrões SDP modernos.

> **Resumo do Fluxo BMAD:**
> 1. `/plan` — Supervisor vira PM, documenta arquitetura e aguarda aprovação
> 2. Validar o artefato e ajustar se necessário
> 3. `/sql`, `/spark` ou `/pipeline` — Agente especialista implementa com contexto completo

---

## 📚 Hub de Conhecimento (Skills)

Os agentes **leem obrigatoriamente os SKILL.md** antes de gerar qualquer código. O Hub é organizado em:

### Skills Databricks (26 módulos)

| Skill | Conteúdo |
|---|---|
| `databricks-spark-declarative-pipelines` | SDP/LakeFlow: STREAMING TABLE, AUTO CDC INTO, MATERIALIZED VIEW, CLUSTER BY |
| `databricks-spark-structured-streaming` | Kafka, checkpoints, stateful ops, stream-stream joins |
| `databricks-bundles` | Databricks Asset Bundles (DABs), YAML, CI/CD |
| `databricks-jobs` | Workflows, schedules, task types, notifications |
| `databricks-dbsql` | SQL Warehouse, Materialized Views, AI Functions, scripting |
| `databricks-unity-catalog` | Governance, volumes, system tables, data profiling |
| `databricks-model-serving` | Custom PyFunc, GenAI agents, AI Gateway, deployment |
| `databricks-mlflow-evaluation` | Evaluation, scorers, judge alignment, traces |
| `databricks-vector-search` | Delta Sync, Direct Access, RAG end-to-end |
| `databricks-agent-bricks` | Knowledge assistants, supervisor agents |
| `databricks-ai-functions` | AI_QUERY, AI_FORECAST, document pipelines |
| `databricks-aibi-dashboards` | Widgets, filtros, troubleshooting |
| `databricks-app-python` | Databricks Apps, frameworks, MCP approach |
| `databricks-genie` | Genie Spaces, conversational analytics |
| `databricks-iceberg` | Managed Iceberg, UniForm, REST Catalog, Snowflake interop |
| `databricks-lakebase-autoscale` | Branches, autoscale, reverse ETL |
| `databricks-lakebase-provisioned` | Provisioned Lakebase, connection patterns |
| `databricks-metric-views` | Metric Views YAML, patterns |
| `databricks-python-sdk` | SDK authentication, clusters, jobs, UC, serving |
| `databricks-execution-compute` | Clusters, políticas, compute types |
| `databricks-config` | Configurações globais, env vars |
| `databricks-synthetic-data-gen` | Geração de dados sintéticos para testes |
| `databricks-unstructured-pdf-generation` | PDF processing pipelines |
| `databricks-zerobus-ingest` | ZeroBus ingestion, protobuf schema |
| `spark-python-data-source` | Custom Data Sources, partitioning, streaming |
| `databricks-docs` | Referências gerais da documentação |

### Skills Microsoft Fabric (5 módulos + referências)

| Skill | Conteúdo |
|---|---|
| `fabric-medallion` | Bronze/Silver/Gold com V-Order, MERGE, Auto Loader no Fabric |
| `fabric-direct-lake` | Regras V-Order, causas de fallback, limites por SKU |
| `fabric-eventhouse-rti` | KQL reference table, Eventstreams, Activator, caching policies |
| `fabric-data-factory` | Copy Activity, Dataflows Gen2 Fast Copy, Pipeline JSON |
| `fabric-cross-platform` | Mirroring, Shortcuts, ABFSS, Export (Databricks ↔ Fabric) |
| `lakehouse-medallion.md` | Referência arquitetural Medallion no Fabric |
| `direct-lake-patterns.md` | Padrões de otimização para Direct Lake |
| `kql-rti-optimizations.md` | Otimizações KQL para Real-Time Intelligence |

### Skills Globais

| Skill | Conteúdo |
|---|---|
| `pipeline_design.md` | Medallion Architecture, regras por camada, decisões de design |
| `spark_patterns.md` | PySpark patterns, `pyspark.pipelines` API moderna |
| `sql_generation.md` | SQL patterns com Liquid Clustering (CLUSTER BY), sem ZORDER BY |
| `data_quality.md` | Expectations, reconciliação, qualidade de dados |
| `star_schema_design.md` | 5 regras Gold Star Schema: dim autônoma, `dim_data` via SEQUENCE, INNER JOIN obrigatório em fact, topologia de DAG, Liquid Clustering |

---

## 🛡️ Camada de Proteção (Hooks)

Todos os hooks são registrados no Supervisor e interceptam chamadas em tempo real:

| Hook | Tipo | Proteção |
|---|---|---|
| `security_hook.py` | PreToolUse (Bash) | 17 padrões destrutivos com regex (word boundaries) + 11 padrões de evasão (base64, eval, curl\|shell pipe, xargs) |
| `audit_hook.py` | PostToolUse | Log JSONL de todas as tool calls com classificação (read/write/execute), fallback para stderr se I/O falhar |
| `cost_guard_hook.py` | PostToolUse | Tiers HIGH/MEDIUM/LOW — alerta ao atingir 5 operações HIGH na sessão |

---

## 🔌 Servidores MCP

| Servidor | Plataforma | Tipo | Tools |
|---|---|---|---|
| `databricks` | Databricks | stdio (Python) | 50+ tools: execute_sql, run_job_now, start_pipeline, list_catalogs, etc. |
| `fabric` | Microsoft Fabric | stdio (dotnet) | Tools oficiais Microsoft para Workspaces, Lakehouses, Datasets |
| `fabric_community` | Microsoft Fabric | stdio (Python) | Tools da comunidade para OneLake, Semantic Models |
| `fabric_rti` | Fabric Eventhouse | stdio (Python) | kusto_query, kusto_command, eventstream_create, activator_create_trigger |

---

## 🛠️ Enterprise Readiness & DataOps

### CI/CD com GitHub Actions

```
.github/
├── workflows/
│   ├── ci.yml    # Lint (ruff) + type check (mypy) + testes + security scan (bandit)
│   └── cd.yml    # Deploy automático para staging/production via Databricks Asset Bundles
```

- **CI** dispara em push para `main`/`develop` e em pull requests
- **CD** dispara em tags `v*-rc` (staging) ou `v*` sem `-rc` (production)

### Makefile — Comandos de Desenvolvimento

```bash
make help           # Lista todos os comandos disponíveis
make dev            # Instala dependências de desenvolvimento
make test           # Executa testes com cobertura mínima de 80%
make lint           # ruff check
make format         # ruff format
make type-check     # mypy
make security       # bandit
make run                # Inicia o Data Agents
make health-databricks  # Valida credenciais e conectividade Databricks
make health-fabric      # Valida credenciais e conectividade Microsoft Fabric
make fabric-env         # Cria ambiente conda para Fabric Notebooks
make deploy-staging     # Deploy para Databricks Staging
make deploy-prod        # Deploy para Databricks Production
make clean              # Remove cache e artefatos temporários
```

### Databricks Asset Bundles (Multi-Environment)

O arquivo `databricks.yml` configura três targets:

| Target | Uso | Caminho |
|---|---|---|
| `dev` | Desenvolvimento local (default) | workspace padrão |
| `staging` | Homologação com permissões de grupo | `/Shared/data-agents-staging` |
| `production` | Produção com service principal | `/Shared/data-agents-prod` |

### MLflow / Mosaic AI Model Serving

A classe `agents/mlflow_wrapper.py` empacota toda a engine Multi-Agente como um endpoint REST via Databricks Model Serving. Compatível com Python 3.12+ (usa `asyncio.run()` em vez do deprecated `get_event_loop()`). Aceita o formato OpenAI Messages e retorna respostas compatíveis com Databricks AI Gateway.

Ao final de cada execução, o wrapper captura o `ResultMessage` do SDK e loga automaticamente as métricas no MLflow Run ativo (quando disponível):

| Métrica | Descrição |
|---|---|
| `agent.cost_usd` | Custo total da sessão em dólares |
| `agent.num_turns` | Número de turns executados |
| `agent.duration_ms` | Duração total em milissegundos |

### Diagnóstico de Startup

Ao iniciar, `config/settings.py` executa validação automática de credenciais e emite relatório no log:

```
✅ DATABRICKS: credenciais configuradas.
⚠️  FABRIC: variáveis ausentes: AZURE_TENANT_ID, FABRIC_WORKSPACE_ID.
📋 Configuração: model=claude-opus-4-6, budget=$5.0, max_turns=50
```

---

## 📂 Estrutura Completa de Diretórios

```text
data-agents/
├── main.py                            # Entry point: loop interativo + single-query + /help
├── databricks.yml                     # Databricks Asset Bundles (dev / staging / production)
├── fabric_environment.yml             # Dependências para Fabric Notebooks / Spark Compute
├── pyproject.toml                     # Dependências, metadados e configuração mypy/ruff/pytest
├── Makefile                           # Automação: test, lint, format, health-checks, deploy
├── .pre-commit-config.yaml            # Hooks locais: ruff, bandit, trailing-whitespace, detect-private-key
├── .env.example                       # Variáveis de ambiente (template)
│
├── .github/
│   └── workflows/
│       ├── ci.yml                     # CI: ruff + mypy + pytest + bandit
│       └── cd.yml                     # CD: deploy staging/production via DABs
│
├── commands/                          # 🎯 Parser de Slash Commands
│   └── parser.py                      # Registry extensível: /sql /spark /pipeline /fabric /plan etc.
│
├── config/                            # Configurações e infraestrutura
│   ├── settings.py                    # Pydantic BaseSettings + startup_diagnostics()
│   ├── exceptions.py                  # Hierarquia: DataAgentsError → MCPConnectionError, etc.
│   ├── logging_config.py              # Logging dual: Rich console + JSONL rotativo
│   └── mcp_servers.py                 # Registro e configuração dos MCP Servers
│
├── agents/                            # Cérebros e Personas
│   ├── supervisor.py                  # Orquestrador BMAD (4 passos: Triage→Context→PRD→Delegação)
│   ├── mlflow_wrapper.py              # PyFunc wrapper para Databricks Model Serving (Python 3.12+)
│   ├── definitions/                   # Definições dos agentes especialistas
│   │   ├── sql_expert.py
│   │   ├── spark_expert.py
│   │   └── pipeline_architect.py
│   └── prompts/                       # System prompts com Mapa de Skills e regras mandatórias
│       ├── supervisor_prompt.py       # Mapa 19 skills + protocolo BMAD
│       ├── sql_expert_prompt.py       # Padrões SQL/KQL/T-SQL + mapa 9 skills
│       ├── spark_expert_prompt.py     # SDP/LakeFlow obrigatório + regras por camada
│       └── pipeline_architect_prompt.py  # Cross-platform + DABs + mapa 10 skills
│
├── hooks/                             # 🛡️ Camada de Proteção (PreToolUse / PostToolUse)
│   ├── security_hook.py               # 17 padrões destrutivos + 11 evasão (regex word boundaries)
│   ├── audit_hook.py                  # JSONL: timestamp, tool, operation_type, fallback stderr
│   └── cost_guard_hook.py             # HIGH/MEDIUM/LOW tiers + contadores de sessão
│
├── mcp_servers/                       # 🔌 Configurações dos Servidores MCP
│   ├── databricks/                    # 50+ tools Databricks (stdio Python)
│   ├── fabric/                        # Tools Microsoft oficiais (stdio dotnet)
│   ├── fabric_rti/                    # KQL, Eventstreams, Activator (stdio Python)
│   └── _template/                     # Template para novos servidores
│
├── tools/                             # Ferramentas auxiliares Python
│   ├── databricks_health_check.py     # Valida auth e conexão Databricks
│   └── fabric_health_check.py         # Valida auth Azure/Entra ID para Fabric
│
├── tests/                             # 🧪 Suíte de Testes (pytest)
│   ├── test_agents.py                 # Definições de agentes
│   ├── test_commands.py               # Parser de slash commands (15 casos)
│   ├── test_exceptions.py             # Hierarquia de exceções (10 casos)
│   ├── test_hooks.py                  # Bloqueios de segurança e auditoria
│   ├── test_mcp_configs.py            # Registros MCP
│   ├── test_mlflow_wrapper.py         # MLflow wrapper (9 casos)
│   └── test_settings.py              # Validação de configurações (10 casos)
│
├── output/                            # 📄 Artefatos gerados pelos agentes
│   └── prd_*.md                       # PRDs documentados pelo Supervisor
│
├── logs/                              # 📊 Logs de auditoria e sistema
│   ├── audit.jsonl                    # Tool calls (timestamp, tool, operation_type)
│   └── app.jsonl                      # Log geral da aplicação (JSONL rotativo)
│
└── skills/                            # 📚 HUB DE CONHECIMENTO (lido pelos agentes via Read)
    ├── pipeline_design.md             # Medallion Architecture + regras por camada
    ├── spark_patterns.md              # PySpark + pyspark.pipelines (API moderna)
    ├── sql_generation.md              # SQL com Liquid Clustering (CLUSTER BY)
    ├── data_quality.md                # Expectations + reconciliação
    ├── star_schema_design.md          # 5 regras Gold Star Schema (dim autônoma, SEQUENCE, INNER JOIN)
    ├── databricks/                    # 26 Skills Databricks (SDP, Unity Catalog, DABs, MLflow, etc.)
    └── fabric/                        # 5 Skills Microsoft Fabric (Medallion, Direct Lake, RTI, etc.)
```

---

## 🧪 Testes e Desenvolvimento

O projeto inclui suíte de testes assíncronos via `pytest` com 7 arquivos e cobertura mínima de **80%**:

```bash
# Instale as dependências de desenvolvimento
pip install -e ".[dev]"

# Execute a suíte completa com cobertura
pytest tests/ -v --tb=short --cov=agents --cov=config --cov=hooks --cov=commands

# Ou via Makefile
make test
```

Escopo de cobertura: `agents/`, `config/`, `hooks/`, `commands/`.

---

## ✅ Scripts de Health Check

Antes de usar em um ambiente novo, valide suas credenciais:

```bash
# Databricks: valida autenticação, lista SQL Warehouses e catálogos do Unity Catalog
python tools/databricks_health_check.py
# ou: make health-databricks

# Microsoft Fabric: valida token Entra ID + conectividade real (GET /v1/workspaces)
python tools/fabric_health_check.py
# ou: make health-fabric

# Health check via agente (verifica MCP servers em tempo real)
data-agents
/health
```

---

## 🤝 Como Contribuir com Skills

O verdadeiro poder do **Data Agents** reside no Hub de Conhecimento. Para adicionar novos skills:

1. Navegue até `skills/databricks/TEMPLATE/` ou `skills/fabric/`.
2. Copie a estrutura do template para uma nova skill (ex: `skills/databricks/nova-skill/`).
3. Preencha o `SKILL.md` com: quando usar, padrões obrigatórios e exemplos de código.
4. Adicione a nova skill no **Mapa de Skills** dos prompts relevantes (`supervisor_prompt.py`, `sql_expert_prompt.py`, `spark_expert_prompt.py` ou `pipeline_architect_prompt.py`).
5. O Supervisor lerá automaticamente o novo `SKILL.md` quando o contexto exigir.

---

*"Um agente com acesso à nuvem é bom. Um hub de multi-agentes que conhece as melhores práticas corporativas lendo seus próprios manuais é revolucionário."*
