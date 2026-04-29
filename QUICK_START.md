# Quick Start — data-agents-copilot

## 1. Instalação

```bash
git clone https://github.com/arthurfr23/data-agents-copilot.git
cd data-agents-copilot
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env          # preencher GITHUB_TOKEN (obrigatório)
```

## 2. Uso via CLI — `data-agent`

### Menu interativo (padrão)

```bash
data-agent          # abre menu com questionary
data-agent start    # equivalente
```

Navega com ↑↓, escolhe agente, digita a tarefa, vê o resultado.

### Executar arquivo de tarefa

```bash
data-agent run tasks/sql/review_query_pedidos.yaml
data-agent run tasks/spark/scd2_clientes.md
data-agent run tasks/pipelines/              # executa todos na pasta
```

### Acesso direto ao agente (power users)

```bash
data-agent spark "otimize este pipeline incremental Bronze→Silver"
data-agent sql "modele star schema para vendas com SCD2"
data-agent naming "CREATE TABLE raw_customers (id INT, name STRING)"
data-agent governance "audite PII nesta tabela"
data-agent health
data-agent list
data-agent tasks
```

### Todos os subcomandos

| Comando | O que faz |
|---------|-----------|
| `data-agent` ou `start` | Menu interativo |
| `data-agent run <arquivo\|pasta>` | Executa task file(s) |
| `data-agent health` | Status de conectividade |
| `data-agent list` | Lista os 15 agentes |
| `data-agent tasks [--dir path]` | Lista arquivos em tasks/ |
| `data-agent spark "<tarefa>"` | Acesso direto ao Spark Expert |
| `data-agent sql "<tarefa>"` | Acesso direto ao SQL Expert |
| `data-agent pipeline "<tarefa>"` | Pipeline Architect |
| `data-agent quality "<tarefa>"` | Data Quality |
| `data-agent naming "<tarefa>"` | Naming Guard |
| `data-agent governance "<tarefa>"` | Governance Auditor |
| `data-agent dbt "<tarefa>"` | dbt Expert |
| `data-agent python "<tarefa>"` | Python Expert |
| `data-agent fabric "<tarefa>"` | Fabric Expert |
| `data-agent lakehouse "<tarefa>"` | Lakehouse Engineer |
| `data-agent ai "<tarefa>"` | Databricks AI |
| `data-agent devops "<tarefa>"` | DevOps Engineer |
| `data-agent geral "<tarefa>"` | Geral |
| `data-agent plan "<tarefa>"` | Supervisor + PRD |
| `data-agent party "<tarefa>"` | Multi-agente paralelo |
| `data-agent review "<artefato>"` | Review de código |

## 3. Arquivos de Tarefa — `tasks/`

Pasta `tasks/` é seu repositório de tarefas versionadas. Estrutura:

```
tasks/
  sql/              Queries, modelagem, review
  spark/            PySpark, Delta Lake, SCD2
  pipelines/        Pipelines E2E, orquestração
  governance/       Naming audits, PII, compliance
  quality/          Expectativas DQX, regras
  devops/           DABs, CI/CD, Databricks Workflows
  workflows/        Tarefas multi-agente complexas
  _template.yaml    Template comentado
```

### Formato YAML

```yaml
agent: spark_expert       # ou "auto" para roteamento automático

task: |
  Descrição detalhada da tarefa.
  Pode ser multilinha com qualquer contexto necessário.

context_files:            # opcional — injetados como contexto extra
  - resources/naming convention.md
  - docs/schema_pedidos.md

output: output/pipelines/resultado.md   # opcional — salva o resultado
```

### Formato Markdown (com frontmatter)

```markdown
---
agent: sql_expert
output: output/sql/resultado.md
---

Descreva a tarefa aqui, com todo o Markdown necessário, incluindo
blocos de código SQL, exemplos, especificações, etc.
```

### Campos disponíveis

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `agent` | string | não (default: `auto`) | Nome do agente ou `auto` |
| `task` | string | sim | Texto da tarefa |
| `context_files` | list | não | Arquivos injetados como contexto |
| `output` | string | não | Caminho para salvar o resultado |

**Agentes válidos:** `auto`, `spark_expert`, `sql_expert`, `pipeline_architect`,
`data_quality`, `naming_guard`, `governance_auditor`, `dbt_expert`, `python_expert`,
`fabric_expert`, `databricks_ai`, `devops_engineer`, `lakehouse_engineer`, `geral`, `supervisor`

## 4. Configuração Inicial

```bash
# .env mínimo
GITHUB_TOKEN=ghp_xxxx                    # obrigatório para LLM

# Opcional — Databricks MCP
DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
DATABRICKS_TOKEN=dapi_xxx

# Opcional — Fabric MCP
AZURE_TENANT_ID=xxx
AZURE_CLIENT_ID=xxx
AZURE_CLIENT_SECRET=xxx
FABRIC_WORKSPACE_ID=xxx
```

Edite `resources/naming convention.md` com as convenções da sua equipe — o Naming Guard
as lê automaticamente.

## 5. Make targets

```bash
make test            # testes com cobertura
make lint            # ruff check
make evals           # evals do framework
make health          # health check rápido
make ui              # interface web Chainlit (porta 8503)
make run             # CLI legado (main.py)
```
