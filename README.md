<p align="center">
  <img src="img/readme/banner.png" alt="Data Agents Banner" width="100%">
</p>

<p align="center">
  <h1 align="center">Data Agents</h1>
  <p align="center">
    <strong>Sistema Multi-Agentes para Engenharia de Dados, Qualidade, Governanca e Analise Corporativa</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Version-3.1.0-brightgreen.svg" alt="Version 3.1.0">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Databricks-MCP-FF3621.svg" alt="Databricks MCP">
    <img src="https://img.shields.io/badge/Microsoft%20Fabric-MCP-0078D4.svg" alt="Fabric MCP">
    <img src="https://img.shields.io/badge/Anthropic-Claude%20SDK-D97757.svg" alt="Claude SDK">
    <img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg" alt="CI/CD">
  </p>
</p>

Sistema multi-agente construido sobre o **Claude Agent SDK** da Anthropic com integracao nativa via **Model Context Protocol (MCP)** ao **Databricks** e **Microsoft Fabric**. Transforma um assistente de IA em uma equipe autonoma de dados que opera diretamente nas suas plataformas de nuvem, seguindo regras corporativas declarativas.

---

## Autor

> ## **Thomaz Antonio Rossito Neto**
>
> Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T

## Contatos

> **LinkedIn:** [thomaz-antonio-rossito-neto](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/)

> **GitHub:** [ThomazRossito](https://github.com/ThomazRossito/)

### Certificações Databricks

<img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134719" alt="Databricks Certified Spark Developer" width="120"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/169321258" alt="Databricks Certified Generative AI Engineer Associate" width="120"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/167127257" alt="Databricks Certified Data Analyst Associate" width="120"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/125134780" alt="Databricks Certified Data Engineer Associate" width="120"/> <img src="https://api.accredible.com/v1/frontend/credential_website_embed_image/badge/157011932" alt="Databricks Certified Data Engineer Professional" width="120"/>

### Certificações Microsoft

<a href="https://www.credly.com/badges/052e5133-0c67-4ab7-bb3a-c99efa7b4406/public_url" target="_blank"><img src="https://images.credly.com/images/70eb1e3f-d4de-4377-a062-b20fb29594ea/azure-data-fundamentals-600x600.png" alt="DP-900" width="120"/></a> <a href="https://learn.microsoft.com/pt-br/users/thomazantoniorossitoneto/credentials/certification/fabric-data-engineer-associate" target="_blank"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310419663028569643/ftqfVZsrmaGyfUha.png" alt="DP-700" width="120"/></a>

---

## Arquitetura

<p align="center">
  <img src="img/readme/architecture_v2.png" alt="Arquitetura Multi-Agent System" width="100%">
</p>

O sistema opera com um **Supervisor** (Opus) que orquestra **6 agentes especialistas** definidos declarativamente em Markdown. Cada agente declara seus dominios de conhecimento (`kb_domains`), ferramentas e tier no frontmatter YAML. O Supervisor segue o **Protocolo KB-First + BMAD** com validacao constitucional.

### Fluxo Completo do Supervisor

```
Passo 0   - KB-First: le Knowledge Bases relevantes
Passo 0.5 - Clarity Checkpoint: valida clareza da requisicao (5 dimensoes, minimo 3/5)
Passo 0.9 - Spec-First: seleciona template de spec para tarefas complexas
Passo 1   - Planejamento: cria PRD em output/
Passo 2   - Aprovacao: mostra resumo e aguarda confirmacao do usuario
Passo 3   - Delegacao: aciona agentes (com suporte a Workflows Colaborativos WF-01 a WF-04)
Passo 4   - Sintese e Validacao Constitucional: verifica aderencia a kb/constitution.md
```

---

## Agentes Especialistas

| Agente                         | Comando         | Tier | Papel                                                 |
| ------------------------------ | --------------- | ---- | ----------------------------------------------------- |
| **Supervisor**           | `/plan`       | -    | Orquestra, planeja e valida contra a Constituicao     |
| **SQL Expert**           | `/sql`        | T1   | SQL (Spark SQL, T-SQL, KQL), metadados, Unity Catalog |
| **Spark Expert**         | `/spark`      | T1   | PySpark, Delta Lake, pipelines SDP/LakeFlow           |
| **Pipeline Architect**   | `/pipeline`   | T1   | ETL/ELT cross-platform, DABs, DataOps                 |
| **Data Quality Steward** | `/quality`    | T2   | Profiling, expectations, alertas, SLAs                |
| **Governance Auditor**   | `/governance` | T2   | Auditoria, linhagem, PII, LGPD/GDPR                   |
| **Semantic Modeler**     | `/semantic`   | T2   | DAX, Direct Lake, Metric Views, Power BI              |

---

## Inicio Rapido

```bash
# 1. Clone e entre no diretorio
git clone git@github.com:ThomazRossito/data-agents.git && cd data-agents

# 2. Crie o ambiente
conda create -n data-agents python=3.11 && conda activate data-agents

# 3. Instale dependencias
pip install -e ".[dev]"

# 4. Configure credenciais
cp .env.example .env   # edite com suas chaves

# 5. Inicie
python main.py
```

### Credenciais no `.env`

| Variavel                                            | Obrigatoria | Plataforma |
| --------------------------------------------------- | ----------- | ---------- |
| `ANTHROPIC_API_KEY`                               | Sim         | Claude API |
| `DATABRICKS_HOST`, `DATABRICKS_TOKEN`           | Nao         | Databricks |
| `AZURE_TENANT_ID`, `FABRIC_WORKSPACE_ID`        | Nao         | Fabric     |
| `KUSTO_SERVICE_URI`, `KUSTO_SERVICE_DEFAULT_DB` | Nao         | Fabric RTI |

O sistema ativa automaticamente apenas as plataformas com credenciais validas.

---

## Camada de Protecao (Hooks)

| Hook                  | Tipo         | Protecao                                            |
| --------------------- | ------------ | --------------------------------------------------- |
| `security_hook`     | PreToolUse   | 17 padroes destrutivos + 11 padroes de evasao       |
| `check_sql_cost`    | PreToolUse   | Bloqueia `SELECT *` sem `WHERE`/`LIMIT`       |
| `audit_hook`        | PostToolUse  | Log JSONL com categorizacao de erros (6 categorias) |
| `workflow_tracker`  | PostToolUse  | Rastreia delegacoes, workflows e Clarity Checkpoint |
| `cost_guard_hook`   | PostToolUse  | Classificacao HIGH/MEDIUM/LOW com alertas           |
| `output_compressor` | PostToolUse  | Trunca outputs (SQL 50 rows, listas 30, max 8K)     |
| `checkpoint`        | Budget/Reset | Salva estado da sessao para recuperacao automatica  |

---

## Checkpoint de Sessao

Quando o budget estoura ou voce digita `limpar`, o sistema salva automaticamente um checkpoint com o ultimo prompt, custo acumulado e arquivos gerados. Na proxima sessao, digite **`continuar`** para retomar de onde parou.

---

## Knowledge Bases, Constituicao e Workflows

O conhecimento e organizado em 3 camadas:

- **Constituicao** (`kb/constitution.md`): documento de autoridade maxima com ~50 regras inviolaveis (Medallion, Star Schema, Seguranca, Qualidade, Plataforma)
- **Knowledge Bases** (`kb/`): 8 dominios de regras de negocio (sql-patterns, spark-patterns, pipeline-design, data-quality, governance, semantic-modeling, databricks, fabric)
- **Skills** (`skills/`): manuais operacionais detalhados (27 modulos Databricks + 5 Fabric)

**Workflows Colaborativos** (`kb/collaboration-workflows.md`): 4 workflows pre-definidos com handoff automatico entre agentes (WF-01 Pipeline End-to-End, WF-02 Star Schema, WF-03 Cross-Platform, WF-04 Governance Audit).

**Spec-First Templates** (`templates/`): 3 templates para pipeline, star-schema e cross-platform, com regras constitucionais embutidas.

---

## Dashboard de Monitoramento

```bash
pip install -e ".[monitoring]"
streamlit run monitoring/app.py
```

9 paginas: Overview, Agentes (com metricas de performance), Workflows (delegacoes, Clarity Checkpoint, specs), Execucoes, MCP Servers, Logs, Configuracoes, Custo & Tokens (economia do compressor), Sobre. Inclui filtro global de datas e auto-refresh.

---

## CI/CD

- **CI** (push/PR): ruff lint + ruff format + mypy + pytest (cobertura minima 80%) + bandit security scan
- **CD** (tags): deploy via Databricks Asset Bundles

```bash
make lint      # ruff check + format
make test      # pytest com cobertura
make run       # python main.py
```

---

## Configuracoes Avancadas

| Variavel                 | Default | Descricao                                                    |
| ------------------------ | ------- | ------------------------------------------------------------ |
| `MAX_BUDGET_USD`       | 5.0     | Limite de custo por sessao                                   |
| `MAX_TURNS`            | 50      | Limite de turns por sessao                                   |
| `CONSOLE_LOG_LEVEL`    | WARNING | Nivel de log no terminal (WARNING esconde logs operacionais) |
| `TIER_MODEL_MAP`       | {}      | Override de modelo por tier:`'{"T1": "claude-opus-4-6"}'`  |
| `INJECT_KB_INDEX`      | true    | Injecao automatica de KBs nos agentes                        |
| `IDLE_TIMEOUT_MINUTES` | 30      | Reset automatico por inatividade (0 = desabilitar)           |

---

## Manual completo

[Manual completo](Manual_Relatorio_Tecnico_Projeto_Data_Agents.md)

---

## Licenca

[MIT License](LICENSE)
