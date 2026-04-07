<p align="center">
  <img src="img/readme/banner.png" alt="Data Agents Banner" width="100%">
</p>

<p align="center">
  <h1 align="center">Data Agents</h1>
  <p align="center">
    <strong>Sistema Multi-Agentes para Engenharia de Dados, Qualidade, Governança e Análise Corporativa</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Version-0.2.0-brightgreen.svg" alt="Version 0.2.0">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
    <img src="https://img.shields.io/badge/Databricks-MCP-FF3621.svg" alt="Databricks MCP">
    <img src="https://img.shields.io/badge/Microsoft%20Fabric-MCP-0078D4.svg" alt="Fabric MCP">
    <img src="https://img.shields.io/badge/Anthropic-Claude%20SDK-D97757.svg" alt="Claude SDK">
    <img src="https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF.svg" alt="CI/CD">
  </p>
</p>

Construído sobre o **Claude Agent SDK** da Anthropic com integração nativa via **Model Context Protocol (MCP)** ao **Databricks** e **Microsoft Fabric**. Este ecossistema transforma o seu assistente de IA em uma verdadeira equipe de dados autônoma, operando recursos diretamente nas suas nuvens corporativas. O sistema atua em Engenharia de Dados, Qualidade de Dados, Governança e Modelagem Semântica, garantindo aderência estrita às melhores práticas corporativas por meio de uma arquitetura declarativa de Knowledge Bases. 

---

## 👤 Autor

> ## Thomaz Antonio Rossito Neto
>
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

## 🏗️ Visão Geral e Arquitetura v2.0

O **Data Agents** é projetado para atuar como uma *squad* autônoma de dados. Através de um Supervisor de Agentes e o **Método BMAD** (Breakthrough Method for Agile AI-Driven Development), a sua intenção em linguagem natural é orquestrada para **6 especialistas declarativos**, abrangendo Engenharia, Qualidade, Governança e Análise.

A grande inovação da versão 2.0 é a separação entre **Knowledge Bases (KB)** e **Skills**. O Supervisor lê as regras de negócio corporativas (KB) *antes* de planejar a arquitetura, enquanto os Agentes Especialistas consultam os manuais operacionais (Skills) na hora de executar. Os agentes são definidos dinamicamente via arquivos Markdown (YAML Frontmatter), permitindo escalar a equipe virtual sem escrever código Python.


<p align="center">
  <img src="img/readme/architecture_v2.png" alt="Arquitetura Multi-Agent System" width="100%">
</p>

---

## 🤖 Agentes Especialistas (Registry Dinâmico)

O sistema conta com 6 agentes especialistas carregados dinamicamente a partir de `agents/registry/*.md`:

| Agente                         | Comando         | Modelo                | Papel e Responsabilidades                                                                                                |
| ------------------------------ | --------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Supervisor**           | `/plan`       | `claude-opus-4-6`   | Líder técnico. Recebe a requisição, lê as KBs (KB-First), cria PRDs e delega para a equipe.                         |
| **SQL Expert**           | `/sql`        | `claude-sonnet-4-6` | Especialista em dados relacionais (KQL, T-SQL, Spark SQL). Consulta metadados*read-only* e gera SQL.                   |
| **Spark Expert**         | `/spark`      | `claude-sonnet-4-6` | Focado exclusivamente em geração de código PySpark e SDP/LakeFlow moderno.                                            |
| **Pipeline Architect**   | `/pipeline`   | `claude-opus-4-6`   | Engenheiro DataOps/SRE. Automatiza pipelines completos e integrações cross-platform.                                   |
| **Data Quality Steward** | `/quality`    | `claude-sonnet-4-6` | Garante a saúde dos dados. Executa profiling, define expectations, monitora SLAs e cria alertas no Fabric Activator.    |
| **Governance Auditor**   | `/governance` | `claude-sonnet-4-6` | Focado em compliance. Audita acessos, mapeia linhagem, identifica PII e garante políticas LGPD/GDPR.                    |
| **Semantic Modeler**     | `/semantic`   | `claude-sonnet-4-6` | Ponte com o negócio. Desenvolve modelos semânticos DAX, otimiza Direct Lake e configura Databricks Genie/Metric Views. |

---

## 🗂️ Método BMAD e Protocolo KB-First

O **BMAD (Breakthrough Method for Agile AI-Driven Development)** garante qualidade arquitetural em vez de geração de código "no escuro". Na v2.0, o protocolo adota a abordagem **KB-First**:

```
Passo 0: Triage       — Supervisor identifica o tipo de tarefa
Passo 1: KB-First     — Lê as Knowledge Bases (kb/) relevantes antes de planejar
Passo 2: PRD          — Documenta arquitetura em output/prd_*.md e aguarda aprovação
Passo 3: Delegação    — Aciona o agente especialista, que lê as Skills operacionais
Passo 4: Síntese      — Valida e consolida os artefatos produzidos
```

**Modos disponíveis:**

| Modo                   | Comando                                                                                        | Descrição                                            |
| ---------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **BMAD Full**    | `/plan`                                                                                      | Fluxo completo com PRD e aprovação antes de delegar  |
| **BMAD Express** | `/sql`, `/spark`, `/pipeline`, `/fabric`, `/quality`, `/governance`, `/semantic` | Bypass do PRD — vai direto ao agente especialista     |
| **Internal**     | `/health`, `/status`, `/review`                                                          | Diagnóstico, listagem de PRDs e revisão de artefatos |

---

## 📋 Pré-Requisitos e Credenciais

1. **Python 3.11+**: Recomenda-se instalação via `pyenv`, `conda` ou `virtualenv`.
2. **Anthropic API**: Variável `ANTHROPIC_API_KEY` (obrigatória).
3. **Databricks** (opcional): `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_SQL_WAREHOUSE_ID`.
4. **Microsoft Fabric** (opcional): Service Principal com `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` + `FABRIC_WORKSPACE_ID`.
5. **Fabric RTI** (opcional): `KUSTO_SERVICE_URI` e `KUSTO_SERVICE_DEFAULT_DB`.

Todas as credenciais são configuradas no arquivo `.env` — nenhum `export` manual no shell é necessário.

---

## 🚀 Configuração Rápida

```bash
# 1. Clone o repositório
git clone git@github.com:ThomazRossito/data-agents.git
cd data-agents

# 2. Crie e ative o ambiente virtual (conda ou venv)
conda create -n data-agents python=3.11
conda activate data-agents
# ou: python3 -m venv .venv && source .venv/bin/activate

# 3. Instale as dependências
pip install -e ".[dev]"      # produção + ferramentas de desenvolvimento
pip install -e ".[monitoring]"  # + dashboard Streamlit (opcional)

# 4. Configure as credenciais
cp .env.example .env
# Edite .env com suas credenciais (Anthropic API key é obrigatória)

# 5. Inicie o sistema
python main.py
```

> **Fabric Community MCP:** se o binário `microsoft-fabric-mcp` não for encontrado no PATH, adicione o caminho absoluto no `.env`:
> ```
> FABRIC_COMMUNITY_COMMAND=/opt/anaconda3/envs/data-agents/bin/microsoft-fabric-mcp
> ```

---

## 💬 Slash Commands Disponíveis

Digite `/help` no CLI para ver a lista completa.

| Comando                  | Agente               | Descrição                                            |
| ------------------------ | -------------------- | ------------------------------------------------------ |
| `/sql <tarefa>`        | sql-expert           | Geração de SQL, análise e modelagem dimensional     |
| `/spark <tarefa>`      | spark-expert         | Pipelines SDP/LakeFlow, Structured Streaming, PySpark  |
| `/pipeline <tarefa>`   | pipeline-architect   | Pipelines completos, DABs, DataOps Databricks          |
| `/fabric <tarefa>`     | pipeline-architect   | Microsoft Fabric: Lakehouse, Data Factory              |
| `/quality <tarefa>`    | data-quality-steward | Profiling, Data Expectations, Alertas e SLAs           |
| `/governance <tarefa>` | governance-auditor   | Auditoria de acessos, Linhagem, PII e Conformidade     |
| `/semantic <tarefa>`   | semantic-modeler     | Modelos DAX, Direct Lake, Databricks Metric Views      |
| `/plan <tarefa>`       | supervisor           | Cria PRD completo em `output/` e aguarda aprovação |
| `/health`              | supervisor           | Verifica conectividade com Databricks e Fabric via MCP |
| `/status`              | supervisor           | Lista PRDs gerados em `output/` com resumos          |
| `/review [arquivo]`    | supervisor           | Revisita um PRD existente para continuar ou ajustar    |

---

## 💡 Exemplos Práticos

**Databricks — Qualidade de Dados:**

```
/quality Faça um profiling da tabela silver_vendas e identifique colunas com valores nulos acima de 5%.
```

**Databricks — Governança:**

```
/governance Audite os acessos ao catálogo de produção e verifique se há tabelas com PII não mascarado.
```

**Microsoft Fabric — Modelagem Semântica:**

```
/semantic Crie um modelo semântico DAX para as tabelas Gold de vendas, otimizado para Direct Lake.
```

**Databricks — Lakeflow / SDP (BMAD Full):**

```
/plan Crie um pipeline SDP com STREAMING TABLEs e AUTO CDC INTO para e-commerce. Salvar em output/databricks/.
```

---

## 📚 Knowledge Bases e Skills

A arquitetura de conhecimento é dividida em duas camadas:

### 1. Knowledge Bases (`kb/`)

Regras de negócio e padrões arquiteturais lidos pelo Supervisor *antes* de planejar.

- `sql-patterns`, `spark-patterns`, `pipeline-design`
- `data-quality`, `governance`, `semantic-modeling`
- `fabric`, `databricks`

### 2. Skills Operacionais (`skills/`)

Manuais detalhados lidos pelos especialistas *durante* a execução.

- **Databricks (26 módulos):** SDP, Unity Catalog, DABs, MLflow, Vector Search, etc.
- **Fabric (5 módulos):** Medallion, Direct Lake, RTI, Data Factory, Cross-Platform.

---

## 🛡️ Camada de Proteção (Hooks)

Todos os hooks são registrados no Supervisor e interceptam chamadas em tempo real:

| Hook                   | Tipo              | Proteção                                                    |
| ---------------------- | ----------------- | ------------------------------------------------------------- |
| `security_hook.py`   | PreToolUse (Bash) | 17 padrões destrutivos com regex + 11 padrões de evasão    |
| `audit_hook.py`      | PostToolUse       | Log JSONL de todas as tool calls com classificação          |
| `cost_guard_hook.py` | PostToolUse       | Tiers HIGH/MEDIUM/LOW — alerta ao atingir limites na sessão |

---

## 🔌 Servidores MCP

| Servidor             | Plataforma        | Tipo           | Configuração     | Tools                                                                    |
| -------------------- | ----------------- | -------------- | ---------------- | ------------------------------------------------------------------------ |
| `databricks`       | Databricks        | stdio (Python) | `mcp_servers.py` | 50+ tools: execute_sql, run_job_now, start_pipeline, list_catalogs, etc. |
| `fabric_community` | Microsoft Fabric  | stdio (Python) | `mcp_servers.py` | list_workspaces, list_tables, get_table_schema, get_lineage, list_jobs   |
| `fabric_rti`       | Fabric Eventhouse | stdio (Python) | `mcp_servers.py` | kusto_query, kusto_command, eventstream_create, activator_create_trigger |

### Como funciona a configuração dos MCP Servers

Os servidores MCP são gerenciados **exclusivamente via Python** (`mcp_servers/fabric/server_config.py`). As credenciais vêm do `.env` através do pydantic-settings — **não é necessário fazer `export` no shell**.

O arquivo `.mcp.json` na raiz está intencionalmente vazio (`{"mcpServers": {}}`). Colocar `fabric_community` no `.mcp.json` causaria conflito: o Claude Code leria as variáveis `${VAR}` do shell (potencialmente vazias) e ignoraria as credenciais do `.env`, quebrando a autenticação.

> **Regra prática:** configure tudo no `.env` e nunca duplique servidores no `.mcp.json`.

---

## 📊 Dashboard de Monitoramento

O projeto inclui um dashboard Streamlit em tempo real para acompanhar execuções, logs, status dos MCPs e configurações.

```bash
# Instale as dependências de monitoramento (uma vez só)
pip install -e ".[monitoring]"

# Inicie o dashboard
streamlit run monitoring/app.py
```

Abre automaticamente em **http://localhost:8501**

| Aba              | Conteúdo                                                              |
| ---------------- | --------------------------------------------------------------------- |
| 📊 Overview       | KPIs gerais, atividade por data, top ferramentas, status dos MCPs     |
| 🤖 Agentes        | Os 6 agentes do registry com modelo, tier, tools e MCP servers        |
| ⚡ Execuções      | Volume de cada ferramenta, chamadas MCP reais, histórico              |
| 🔌 MCP Servers    | Status real baseado em chamadas do `audit.jsonl`                      |
| 📋 Logs           | Viewer ao vivo do `app.jsonl` e `audit.jsonl` com filtros e busca     |
| ⚙️ Configurações  | Modelo, budget, max_turns, mapa de arquivos do projeto                |
| ℹ️ Sobre          | Autoria, versão, licença e descrição detalhada do sistema             |

Use o seletor **Auto-refresh** na sidebar para atualizar automaticamente enquanto os agentes rodam (5s, 10s, 30s ou 60s). Todos os horários são exibidos no fuso de **São Paulo (UTC-3)**.

---

## 🛠️ Enterprise Readiness & DataOps

### CI/CD com GitHub Actions

- **CI** dispara em push para `main`/`develop`: Lint (ruff) + type check (mypy) + testes + security scan (bandit).
- **CD** dispara em tags: Deploy automático para staging/production via Databricks Asset Bundles.

### Testes Automatizados

O projeto inclui suíte de testes assíncronos via `pytest` cobrindo o loader dinâmico de agentes, parser de comandos, hooks e configurações, com cobertura mínima de **80%**.

```bash
make test
```

### MLflow / Mosaic AI Model Serving

A classe `agents/mlflow_wrapper.py` empacota toda a engine Multi-Agente como um endpoint REST via Databricks Model Serving. Compatível com Python 3.12+ e formato OpenAI Messages.

---

## 🤝 Como Contribuir com Agentes e KBs

A v2.0 introduziu a definição declarativa de agentes. Para criar um novo agente:

1. Crie um arquivo `novo-agente.md` em `agents/registry/`.
2. Adicione o Frontmatter YAML definindo `name`, `model`, `mcp_servers`, `kb_domains` e `tools`.
3. Escreva o prompt do agente no corpo do Markdown.
4. O `loader.py` carregará o agente automaticamente no próximo boot.

*"Um agente com acesso à nuvem é bom. Uma equipe de especialistas autônomos governados por Knowledge Bases declarativas é revolucionário."*

---

## 📄 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).
