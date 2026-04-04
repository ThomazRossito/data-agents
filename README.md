# Data Agents

Sistema Multi-Agentes para **Engenharia e Análise de Dados**, construído sobre o **Claude Agent SDK** da Anthropic com integração nativa via **Model Context Protocol (MCP)** ao **Databricks** e **Microsoft Fabric**.

---

### 👤 Autor
- **Desenvolvido por:** Thomaz Antonio Rossito Neto
- **Professional:** Specialist Data & AI Solutions Architect | Center of Excellence CoE @CI&T | Enterprise AI Agents, Microsoft Fabric & Databricks Expert
- **LinkedIn:** [https://www.linkedin.com/in/thomaz-antonio-rossito-neto/](https://www.linkedin.com/in/thomaz-antonio-rossito-neto/)
- **GitHub:** [https://github.com/ThomazRossito/](https://github.com/ThomazRossito/)
- **Data criação:** 04/04/2026
- **Data atualização:** 04/04/2026
- **Versão:** 1.0.0

---

## Arquitetura

```
Usuário (linguagem natural)
        │
        ▼
┌─────────────────────────┐
│   AGENT SUPERVISOR      │  Claude Opus 4.6 — orquestra e planeja
│   (Orquestrador)        │
└────┬──────┬─────────┬───┘
     │      │         │
     ▼      ▼         ▼
  SQL     Spark    Pipeline
 Expert   Expert   Architect
(Sonnet) (Sonnet)  (Opus)
     │               │
     └───────┬────────┘
             ▼
   ┌─────────────────────┐
   │    Camada MCP       │
   │  Databricks  Fabric │
   │  Fabric RTI         │
   └─────────────────────┘
```

## Agentes

| Agente | Modelo | Responsabilidade |
|--------|--------|-----------------|
| **Supervisor** | Claude Opus 4.6 | Interpretar intenção, planejar e delegar |
| **SQL Expert** | Claude Sonnet 4.6 | SQL, KQL, descoberta de metadados |
| **Spark Expert** | Claude Sonnet 4.6 | PySpark, Delta Lake, DLT/LakeFlow |
| **Pipeline Architect** | Claude Opus 4.6 | ETL/ELT cross-platform, Jobs, execução |

## Pré-requisitos

- Python 3.11+
- `databricks-mcp-server` instalado e configurado
- `microsoft-fabric-rti-mcp` instalado (via pip ou uvx)
- `microsoft-fabric-mcp` instalado (servidor community)
- dotnet SDK 8.0+ (para Fabric MCP Server oficial)
- Databricks CLI autenticado **ou** variáveis `DATABRICKS_HOST` / `DATABRICKS_TOKEN`
- Azure CLI autenticado (`az login`) **ou** service principal configurado

## Instalação

```bash
# 1. Clone o projeto
git clone <repo-url>
cd data-agents

# 2. Crie e ative ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Instale as dependências
pip install -e ".[dev]"

# 4. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais reais

# 5. Crie o diretório de logs
mkdir -p logs
```

## Uso

### Modo interativo (recomendado)

```bash
python main.py
```

### Single-query (para automação/CI)

```bash
python main.py "Analise a tabela analytics.default.vendas e gere um relatório de qualidade"
```

### Exemplos de solicitações

```
"Leia o CSV vendas_2024.csv do OneLake no Fabric, normalize os dados com PySpark e salve no Databricks Unity Catalog"

"Gere uma query SQL para calcular o top 10 produtos por receita no último mês na tabela analytics.default.vendas"

"Crie um Spark Declarative Pipeline para ingestão incremental do bucket S3 para o Unity Catalog, com camadas Bronze, Silver e Gold"

"Otimize esta query: SELECT * FROM vendas WHERE ano = 2024"

"Analise a qualidade dos dados da tabela fabric.lakehouse.clientes: nulos, duplicatas e anomalias"
```

## Executar testes

```bash
pytest tests/ -v
```

## Adicionar nova plataforma (ex: Snowflake)

1. Copie o template: `cp -r mcp_servers/_template mcp_servers/snowflake`
2. Implemente `get_snowflake_mcp_config()` em `mcp_servers/snowflake/server_config.py`
3. Registre em `config/mcp_servers.py`
4. (Opcional) Crie `agents/definitions/snowflake_expert.py`
5. (Opcional) Registre o agente em `agents/supervisor.py`

## Estrutura do Projeto

```
data-agents/
├── main.py                          # Entry point
├── pyproject.toml                   # Dependências
├── .env.example                     # Template de configuração
├── config/
│   ├── settings.py                  # Configurações (Pydantic)
│   └── mcp_servers.py               # Registry de servidores MCP
├── agents/
│   ├── supervisor.py                # Constrói o ClaudeAgentOptions
│   ├── definitions/                 # AgentDefinition de cada especialista
│   └── prompts/                     # System prompts
├── mcp_servers/
│   ├── databricks/                  # MCP Server Databricks
│   ├── fabric/                      # MCP Servers Fabric (oficial + community)
│   ├── fabric_rti/                  # MCP Server Fabric RTI
│   └── _template/                   # Template para novos módulos
├── hooks/                           # Hooks de segurança e auditoria
├── skills/                          # Conhecimento especializado em Markdown
└── tests/                           # Testes automatizados
```

## Licença

MIT
