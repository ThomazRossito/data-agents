# Manual e Relatório Técnico: Projeto Data Agents

---

Repositório: [github.com/ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents)

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

## Sumário

1. [O que é este projeto?](#1-o-que-é-este-projeto)
2. [Conceitos Fundamentais (Glossário para Iniciantes)](#2-conceitos-fundamentais-glossário-para-iniciantes)
3. [Arquitetura Geral do Sistema](#3-arquitetura-geral-do-sistema)
4. [Os Agentes: A Equipe Virtual](#4-os-agentes-a-equipe-virtual)
5. [O Método DOMA: Como a IA Trabalha](#5-o-método-doma-como-a-ia-trabalha)
6. [Interfaces de Uso](#6-interfaces-de-uso)
7. [Estrutura de Arquivos e Pastas](#7-estrutura-de-arquivos-e-pastas)
8. [Análise Detalhada de Cada Componente](#8-análise-detalhada-de-cada-componente)
9. [Segurança e Controle de Custos (Hooks)](#9-segurança-e-controle-de-custos-hooks)
10. [O Hub de Conhecimento (Skills e Knowledge Base)](#10-o-hub-de-conhecimento-skills-e-knowledge-base)
11. [Conexões com a Nuvem (MCP Servers)](#11-conexões-com-a-nuvem-mcp-servers)
12. [Comandos Disponíveis (Slash Commands)](#12-comandos-disponíveis-slash-commands)
13. [Configuração e Credenciais](#13-configuração-e-credenciais)
14. [Sistema de Memória Persistente](#14-sistema-de-memória-persistente)
15. [Roteamento de Modelos por Tier](#15-roteamento-de-modelos-por-tier)
16. [Qualidade de Código e Testes](#16-qualidade-de-código-e-testes)
17. [Deploy e CI/CD (Publicação Automática)](#17-deploy-e-cicd-publicação-automática)
18. [Como Começar a Usar](#18-como-começar-a-usar)
19. [Conclusão](#19-conclusão)

---

## 1. O que é este projeto?

O **Data Agents** é um sistema de **múltiplos agentes de Inteligência Artificial** especializado em Engenharia de Dados. Em termos simples, é como ter uma equipe de engenheiros de dados virtuais que trabalham juntos para resolver problemas complexos de dados — desde escrever consultas SQL até criar e executar pipelines completos em plataformas de nuvem como Databricks e Microsoft Fabric.

O sistema é construído sobre o modelo de linguagem **Claude** da Anthropic e utiliza o **Model Context Protocol (MCP)** para que a IA possa interagir diretamente com as plataformas de dados, como se fosse um engenheiro humano acessando o painel de controle.

São **14 agentes especialistas** organizados em quatro tiers de custo e capacidade, orquestrados por um Supervisor que nunca acessa dados diretamente — apenas coordena, planeja e delega.

O grande diferencial em relação a um simples "chatbot de programação" é a **camada de governança e conhecimento**: a IA é obrigada a ler manuais de boas práticas (Skills) antes de agir, garantindo que o código gerado seja seguro, eficiente e alinhado com os padrões corporativos modernos.

---

## 2. Conceitos Fundamentais (Glossário para Iniciantes)

| Termo | O que significa na prática |
| --- | --- |
| **Agente de IA** | Um programa de IA que pode tomar decisões, usar ferramentas e executar tarefas de forma autônoma, não apenas responder perguntas. |
| **LLM (Large Language Model)** | O "cérebro" da IA. Neste projeto, é o Claude da Anthropic. |
| **MCP (Model Context Protocol)** | Uma "tomada universal" que permite que a IA se conecte a ferramentas externas de forma padronizada e segura. |
| **Databricks** | Plataforma de nuvem especializada em processamento de grandes volumes de dados com Apache Spark. |
| **Microsoft Fabric** | Plataforma de dados da Microsoft, integrando armazenamento, processamento e visualização em um único ambiente. |
| **Apache Spark** | Tecnologia de processamento de dados em larga escala — processa bilhões de linhas de forma distribuída. |
| **Pipeline de Dados** | Uma "linha de montagem" para dados: entram brutos de um lado, saem limpos e organizados do outro. |
| **Arquitetura Medalhão** | Padrão de organização em camadas: Bronze (dados brutos), Silver (dados limpos) e Gold (dados prontos para análise). |
| **SQL** | Linguagem padrão para consultar bancos de dados. |
| **PySpark** | Python + Spark. É a forma de programar o Spark usando a linguagem Python. |
| **Delta Lake** | Formato de armazenamento que adiciona histórico de versões e transações seguras ao armazenamento em nuvem. |
| **Unity Catalog** | Sistema de catálogo e governança do Databricks — índice centralizado de todos os dados, com controle de acesso. |
| **Star Schema** | Modelo de análise com tabela central de fatos (ex: vendas) rodeada por tabelas de dimensões (ex: clientes, produtos). |
| **Hook** | Um "gancho" de código executado automaticamente antes ou depois de uma ação da IA para garantir segurança. |
| **JSONL** | Formato de arquivo onde cada linha é um objeto JSON independente. Muito usado para logs. |
| **API Key** | Uma senha especial que identifica quem está chamando um serviço externo. |
| **PRD** | *Product Requirements Document* — documento que descreve o que precisa ser construído, como e por quê. |
| **Tier** | Nível de um agente (T1/T2/T3), que define qual modelo usa e quantas interações pode ter por tarefa. |

---

## 3. Arquitetura Geral do Sistema

```
 Você digita um comando (terminal ou Chainlit)
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│              Supervisor (claude-sonnet-4-6)                   │
│    Consulta KB → Clarity Checkpoint → Delega ao especialista  │
└──┬──────────────┬───────────────┬──────────────┬─────────────┘
   │              │               │              │
   ▼              ▼               ▼              ▼
Tier T1        Tier T1         Tier T2        Tier T2/T3
databricks-    fabric-         data-quality-  business-analyst
engineer       engineer        steward        geral (T0/Haiku)
databricks-ai  migration-      governance-
               expert          auditor
               python-expert   dbt-expert
                               fabric-rti
                               fabric-ontology
                               data-contracts-
                               engineer
                               data-mesh-
                               architect
   │              │               │              │
   └──────────────┴───────────────┴──────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│                    MCP Servers (15)                        │
│  databricks │ databricks_genie │ fabric │ fabric_official  │
│  fabric_rti │ fabric_semantic  │ fabric_community         │
│  fabric_sql │ fabric_ontology  │ migration_source         │
│  context7   │ memory_mcp │ tavily │ github │ firecrawl    │
│  postgres                                                  │
└──────────────────────────────────────────────────────────┘
                          │
                          ▼
              Plataformas de Nuvem Reais
          (Databricks, Microsoft Fabric, GitHub...)
```

Em paralelo a todo esse fluxo, **11 hooks** ficam monitorando cada ação: bloqueando comandos perigosos, registrando em logs de auditoria, alertando sobre custos e gerenciando o orçamento de contexto.

---

## 4. Os Agentes: A Equipe Virtual

O sistema possui **14 agentes especialistas** organizados em quatro tiers. O tier define qual modelo Claude é usado, quantos turns (chamadas de ferramenta) o agente pode fazer por tarefa e qual nível de "esforço" de raciocínio aplica.

| Tier | Modelo padrão | Max Turns | Effort | Perfil |
|------|---------------|-----------|--------|--------|
| **T0** | claude-haiku-4-5 | 3 | low | Conversacional puro, zero MCP — exclusivo do agente `geral` |
| **T1** | claude-sonnet-4-6 | 20 | high | Engineering Core: pipelines complexos, cross-platform |
| **T2** | claude-sonnet-4-6 | 12 | medium | Especializados: qualidade, governança, semântica |
| **T3** | claude-sonnet-4-6 | 5 | low | Conversacional com tools limitadas |

### 4.1. O Supervisor

**Modelo:** claude-sonnet-4-6 | **Analogia:** Gerente de Projetos Sênior

Ponto de entrada de todas as interações. Lê as Knowledge Bases, aplica o Clarity Checkpoint, aciona os especialistas certos e valida o resultado final contra a Constituição do sistema. **Nunca gera SQL, PySpark ou acessa MCP diretamente** — apenas coordena.

### 4.2. databricks-engineer — Tier T1

**Comandos:** `/sql`, `/spark`, `/pipeline`, `/cdc`, `/genie`, `/dashboard`, `/diagnose`
**MCPs:** databricks, databricks_genie, context7, migration_source, postgres, memory_mcp, github, tavily

O principal especialista Databricks. Cobre SQL (Spark SQL, T-SQL), PySpark, Delta Lake, LakeFlow/DLT, Jobs, CDC com Debezium, Genie Spaces e AI/BI Dashboards. Tem permissões amplas de execução: dispara jobs, executa SQL em warehouses, cria pipelines.

### 4.3. databricks-ai — Tier T1

**Comandos:** `/ai`, `/streaming`
**MCPs:** databricks, context7, tavily

Especialista em IA e streaming no Databricks: RAG, Vector Search, embeddings, LLMOps, AI Functions, Feature Store, Kafka, Flink e Spark Structured Streaming.

### 4.4. fabric-engineer — Tier T1

**Comandos:** `/fabric`, `/semantic`, `/schema`, `/finops`, `/medallion`, `/catalog`
**MCPs:** fabric, fabric_community, fabric_official, fabric_sql, fabric_semantic

Cobre todo o ecossistema Microsoft Fabric: pipelines no Data Factory, Medallion (Bronze/Silver/Gold), Star Schema, Semantic Models, DAX, Direct Lake, Genie Spaces, FinOps e análise de capacidade (Capacity Units).

### 4.5. migration-expert — Tier T1

**Comando:** `/migrate`
**MCPs:** migration_source, databricks, fabric, fabric_sql, context7

Assessment e migração de bancos relacionais (SQL Server, PostgreSQL) para Databricks ou Microsoft Fabric. O MCP `migration_source` conecta-se diretamente ao banco de origem para extrair DDL, views, procedures, functions e estatísticas.

### 4.6. python-expert — Tier T1

**Comando:** `/python`
**MCPs:** context7

Python puro: pacotes, automação, APIs, CLIs, testes unitários, asyncio, pandas/polars. Consulta a documentação atualizada de bibliotecas via context7 antes de gerar código.

### 4.7. dbt-expert — Tier T2

**Comando:** `/dbt`
**MCPs:** context7, postgres

Especialista em dbt Core: models (staging, marts, intermediate), testes de qualidade, snapshots para SCD Tipo 2, seeds e documentação.

### 4.8. data-quality-steward — Tier T2

**Comando:** `/quality`
**MCPs:** databricks, fabric, fabric_community, fabric_rti, postgres

Validação de dados, profiling estatístico, definição de SLAs e alertas de qualidade cross-platform. Conhece os padrões de qualidade de cada camada da Arquitetura Medalhão.

### 4.9. governance-auditor — Tier T2

**Comando:** `/governance`
**MCPs:** databricks, fabric, fabric_community, tavily, postgres, memory_mcp

Auditoria de acessos, linhagem de dados, detecção de PII, RLS/OLS, Sensitivity Labels e conformidade com LGPD/GDPR. Registra descobertas no knowledge graph de memória para referência futura.

### 4.10. data-contracts-engineer — Tier T2

**Comando:** `/contract`
**MCPs:** context7, databricks, fabric_sql, postgres, memory_mcp

ODCS v3: autoria de contratos, SLA de qualidade, schema evolution e gestão de breaking changes. Persiste contratos e decisões no knowledge graph.

### 4.11. data-mesh-architect — Tier T2

**Comando:** `/mesh`
**MCPs:** context7, tavily, databricks, memory_mcp

Mapeamento de domínios, design de Data Products, self-serve platform e maturity assessment de Data Mesh. Usa busca web para referenciar padrões atualizados.

### 4.12. fabric-rti — Tier T2

**Comando:** `/streaming` (RTI focus)
**MCPs:** fabric_rti

Real-Time Intelligence no Fabric: Eventhouse, KQL, Eventstream e Activator.

### 4.13. fabric-ontology — Tier T2

**Comando:** `/ontology`
**MCPs:** context7, tavily, firecrawl, fabric, fabric_community, fabric_official, fabric_sql, fabric_ontology

OWL 2, RDF, SPARQL e integração com o Fabric IQ Ontology. Cria, edita e exporta ontologias diretamente no OneLake.

### 4.14. business-analyst — Tier T3

**Comando:** `/brief`, `/ship`
**MCPs:** tavily, firecrawl

Transforma reuniões brutas, prints de Slack, e-mails e briefings em backlogs estruturados P0/P1/P2. Usa busca web para enriquecer o contexto com referências de mercado.

### 4.15. geral — Tier T0

**Comando:** `/geral`
**MCPs:** nenhum

Respostas conceituais e explicações diretas, sem passar pelo Supervisor e sem acionar nenhum MCP. Usa Haiku 4.5 — cerca de 95% mais barato que uma resposta via Supervisor completo. Ideal para perguntas como "O que é Delta Lake?" ou "Explique o conceito de SCD Tipo 2".

---

## 5. O Método DOMA: Como a IA Trabalha

O **Método DOMA** (*Data Orchestration Method for Agents*) é o protocolo central que governa como o Supervisor planeja e executa tarefas. Ele foi criado para evitar o problema mais comum com IAs generativas: gerar código bonito mas incorreto, sem seguir os padrões do projeto.

### Os 7 Passos do DOMA

**Passo 0 — KB-First:** O Supervisor consulta as Knowledge Bases relevantes antes de qualquer plano. A IA não inventa — lê os manuais técnicos verificados do projeto.

**Passo 0.5 — Clarity Checkpoint:** Valida se a solicitação está clara o suficiente (score 1 a 5, mínimo 3 para prosseguir). Se necessário, faz perguntas de clarificação antes de agir.

**Passo 0.9 — Spec-First:** Seleciona o template adequado para a tarefa (pipeline spec, star schema spec, cross-platform spec) e o preenche antes de delegar.

**Passo 1 — PRD:** Para tarefas complexas, cria um *Product Requirements Document* e salva em `output/prd/`. Você pode revisar antes de autorizar a execução.

**Passo 2 — Aprovação:** Aguarda confirmação do usuário antes de executar operações de escrita ou de alto custo.

**Passo 3 — Delegação:** Aciona os agentes especialistas na ordem certa, passando contexto completo (schemas, regras de negócio, padrões, Skills relevantes).

**Passo 4 — Validação:** Verifica se o resultado segue as regras da Constituição (`kb/constitution.md`) antes de entregar ao usuário.

### Modos de Operação

**DOMA Full (`/plan`):** Executa todos os 7 passos, incluindo criação de PRD e pausa para aprovação. Ideal para tarefas grandes e críticas.

**DOMA Express (`/sql`, `/spark`, `/pipeline`, etc.):** Pula a criação de PRD e vai direto ao especialista. Ideal para tarefas menores e mais diretas.

### Workflows Colaborativos

Para projetos end-to-end, o Supervisor encadeia agentes automaticamente com passagem de contexto:

| Workflow | Quando usar | Agentes encadeados |
|----------|-------------|-------------------|
| **WF-01** Pipeline End-to-End | "Crie um pipeline Bronze→Gold completo" | databricks-engineer → data-quality-steward → fabric-engineer → governance-auditor |
| **WF-02** Star Schema | "Crie a camada Gold em Star Schema" | fabric-engineer → databricks-engineer → data-quality-steward |
| **WF-03** Migração Cross-Platform | "Migre do Databricks para o Fabric" | databricks-engineer → fabric-engineer → data-quality-steward → governance-auditor |
| **WF-04** Auditoria de Governança | "Gere um relatório de compliance" | governance-auditor → data-quality-steward → Relatório |
| **WF-05** Migração Relacional→Nuvem | "Migre o SQL Server para Databricks" | migration-expert → databricks-engineer → data-quality-steward → governance-auditor |

---

## 6. Interfaces de Uso

### 6.1. Web UI Chainlit (recomendada — porta 8503)

Interface moderna com steps expandíveis em tempo real mostrando cada delegação e tool call enquanto acontecem. Dois modos disponíveis:

- **Data Agents:** sistema completo com todos os 14 agentes
- **Dev Assistant:** Claude direto com ferramentas de código (sem agentes especialistas)

**Funcionalidades da Chainlit:**

- Steps expandíveis mostram o raciocínio de cada agente em tempo real
- Suporte completo a todos os slash commands
- Exibição de artefatos gerados (PRDs, SPECs, backlogs)
- **`/export`:** exporta o histórico completo da sessão como arquivo HTML com formatação profissional — markdown renderizado, código com syntax highlighting, separação visual de usuário (azul) vs. assistente (verde), e métricas de custo removidas automaticamente. Abra no browser e use Cmd+P (macOS) ou Ctrl+P (Windows/Linux) para salvar como PDF.

```bash
./start.sh              # Chainlit (8503) + Monitoring (8501)
./start.sh --chat-only  # somente Chainlit
```

### 6.2. Dashboard de Monitoramento (porta 8501)

9 páginas: Overview, Agentes, Workflows, Execuções, MCP Servers, Logs, Configurações, Custo e Tokens. Inclui tier badge nos cards de agentes, todos os workflows (WF-01 a WF-05), download CSV de logs, timezone configurável e indicador de freshness dos dados.

```bash
./start.sh --monitor-only
```

### 6.3. Terminal (CLI)

Interface de linha de comando. Ideal para automação e ambientes sem interface gráfica.

```bash
python main.py                              # modo interativo
python main.py "liste tabelas da silver"   # consulta única
```

---

## 7. Estrutura de Arquivos e Pastas

| Caminho | Tipo | Descrição |
| --- | --- | --- |
| `main.py` | Python | Ponto de entrada — CLI interativo e modo single-query |
| `pyproject.toml` | Config | Dependências e metadados do projeto Python |
| `Makefile` | Automação | Atalhos para tarefas comuns (instalar, testar, rodar) |
| `.env.example` | Modelo | Template para configurar credenciais (nunca versionar o `.env` real) |
| `switch-env.sh` | Shell | Alternância entre arquivos `.env` (ex: conta pessoal vs. proxy corporativo) |
| `start.sh` | Shell | Inicia as interfaces (Chainlit Chat + Streamlit Monitoring) |
| `databricks.yml` | YAML | Configuração para deploy via Databricks Asset Bundles |
| `.pre-commit-config.yaml` | Config | Hooks de qualidade que rodam antes de cada commit |
| `agents/` | Pasta | Definições, prompts e lógica de todos os agentes |
| `agents/supervisor.py` | Python | Lógica de orquestração do Supervisor |
| `agents/loader.py` | Python | Carrega agentes do registry, resolve aliases de ferramentas |
| `agents/registry/` | Pasta | Definições declarativas dos agentes (`.md` + YAML frontmatter) |
| `agents/prompts/` | Pasta | System prompt do Supervisor e templates |
| `agents/cache_prefix.md` | Markdown | Prefixo byte-idêntico injetado em todos os agentes (prompt caching) |
| `config/` | Pasta | Configurações globais do sistema |
| `config/settings.py` | Python | Leitura e validação das variáveis de ambiente via Pydantic |
| `config/mcp_servers.py` | Python | Registro centralizado de todos os MCP servers |
| `commands/` | Pasta | Lógica dos slash commands (`/sql`, `/spark`, etc.) |
| `hooks/` | Pasta | Interceptadores de segurança, auditoria, custo e contexto |
| `mcp_servers/` | Pasta | Configurações de conexão com plataformas de nuvem |
| `mcp_servers/databricks_genie/` | Pasta | MCP customizado: Databricks Genie Conversation API |
| `mcp_servers/fabric_sql/` | Pasta | MCP customizado: Fabric SQL Analytics via TDS |
| `mcp_servers/fabric_semantic/` | Pasta | MCP customizado: introspecção de Semantic Models |
| `mcp_servers/migration_source/` | Pasta | MCP customizado: extração de DDL de SQL Server/PostgreSQL |
| `skills/` | Pasta | Manuais técnicos de boas práticas (Skills operacionais) |
| `kb/` | Pasta | Knowledge Bases — lidas pelo Supervisor antes de cada plano |
| `kb/constitution.md` | Markdown | Regras invioláveis do sistema (7 regras S1-S7) |
| `memory/` | Pasta | Sistema de memória episódica — captura e retrieval semântico |
| `ui/` | Pasta | Interface web de chat (Chainlit) |
| `ui/chainlit_app.py` | Python | Aplicação Chainlit — interface de chat oficial |
| `ui/exporter.py` | Python | Exportação de histórico de sessão para HTML/PDF |
| `monitoring/` | Pasta | Dashboard de monitoramento (Streamlit, 9 páginas) |
| `tools/` | Pasta | Scripts utilitários para o usuário |
| `tests/` | Pasta | Suíte de testes automatizados (pytest) |
| `output/` | Pasta | Artefatos gerados pelos agentes (PRDs, SPECs) |
| `logs/` | Pasta | Arquivos de log de auditoria e sistema |
| `.github/` | Pasta | Workflows de CI/CD do GitHub Actions |

---

## 8. Análise Detalhada de Cada Componente

### 8.1. `main.py` — A Interface de Terminal

**Modo Interativo:** Abre um loop de conversa no terminal. Suporta todos os slash commands, exibe o progresso em tempo real (qual ferramenta está sendo usada) e mostra custo total e número de interações ao final de cada resposta.

**Modo de Consulta Única:** `python main.py "Analise a tabela de vendas"` — processa e encerra.

### 8.2. `config/settings.py` — O Painel de Controle

Usa **Pydantic BaseSettings** para ler variáveis de ambiente do `.env` e transformá-las em um objeto Python tipado e validado. Executa um **diagnóstico automático no startup**: verifica quais plataformas têm credenciais e emite avisos. Se `ANTHROPIC_API_KEY` não estiver configurada, o sistema não inicia.

Principais configurações:

| Variável | Padrão | Descrição |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | obrigatório | Chave de acesso à API do Claude |
| `ANTHROPIC_BASE_URL` | (vazio) | URL de proxy LiteLLM (AWS Bedrock, etc.) — vazio = usa api.anthropic.com |
| `DEFAULT_MODEL` | `claude-sonnet-4-6` | Modelo padrão do Supervisor |
| `TIER_MODEL_MAP` | `{}` | Override de modelo por tier T1/T2/T3 — tem precedência sobre o frontmatter dos agentes |
| `TIER_TURNS_MAP` | T1=20, T2=12, T3=5 | Máximo de turns por tier |
| `TIER_EFFORT_MAP` | high/medium/low | Nível de raciocínio por tier |
| `MAX_BUDGET_USD` | `5.0` | Limite de gasto por sessão |
| `MAX_TURNS` | `50` | Limite de interações do Supervisor por sessão |
| `AGENT_PERMISSION_MODE` | `bypassPermissions` | `acceptEdits` para confirmação manual de writes |
| `CONSOLE_LOG_LEVEL` | `WARNING` | `INFO` exibe logs operacionais; `WARNING` os oculta |
| `MEMORY_ENABLED` | `true` | Sistema de memória persistente |

### 8.3. `agents/loader.py` — O Carregador de Agentes

Carrega automaticamente todos os arquivos `.md` de `agents/registry/`. O YAML frontmatter de cada arquivo define o nome, modelo, ferramentas, MCPs, tier e domínios de KB e Skill do agente — **sem necessidade de tocar código Python** para adicionar um novo agente.

O loader também resolve aliases de ferramentas como `databricks_readonly`, `fabric_all`, `context7_all`, que mapeiam para conjuntos de tools específicas, simplificando o frontmatter dos agentes.

### 8.4. `ui/exporter.py` — Exportação de Sessão

Exporta o histórico de chat para um arquivo HTML com:

- Layout profissional com header, bubbles de usuário (azul) e assistente (verde)
- Markdown completamente renderizado (tabelas, código com syntax highlighting, listas, negrito)
- Remoção automática das métricas de custo (`💰 $X.XXXX`) do conteúdo exportado
- Estilos `@media print` para resultado profissional ao salvar como PDF via browser (Cmd+P)

Ativado via `/export` na Chainlit.

### 8.5. `agents/mlflow_wrapper.py` — Integração com MLflow

Permite publicar o Data Agent como endpoint de API dentro do Databricks via MLflow. Implementa a interface `mlflow.pyfunc.PythonModel` e aceita requisições no formato OpenAI Messages, facilitando a integração com outras ferramentas corporativas.

---

## 9. Segurança e Controle de Custos (Hooks)

Os hooks são interceptadores automáticos ativados antes (`PreToolUse`) ou depois (`PostToolUse`) de cada ação da IA.

| Hook | Tipo | O que faz |
|------|------|-----------|
| `security_hook.py` | PreToolUse (Bash) | Bloqueia 22 padrões destrutivos: `DROP`, `rm -rf`, `git reset --hard`, `TRUNCATE`, acesso a `.env`, `.ssh/`, etc. |
| `security_hook.py` | PreToolUse (all) | Detecta `SELECT *` sem `WHERE` ou `LIMIT` |
| `audit_hook.py` | PostToolUse | Registra todas as tool calls no JSONL de auditoria (timestamp, tool, tipo, parâmetros) |
| `cost_guard_hook.py` | PostToolUse | Classifica operações HIGH/MEDIUM/LOW; alerta após 5 HIGH na sessão |
| `output_compressor_hook.py` | PostToolUse | Trunca outputs verbosos para preservar tokens de contexto |
| `context_budget_hook.py` | PostToolUse | Alerta a 70%; compacta autonomamente a 80% (summary Haiku + reconexão); ERROR a 95% |
| `workflow_tracker.py` | PostToolUse | Rastreia delegações, Clarity Checkpoint e cascade PRD→SPEC |
| `memory_hook.py` | PreToolUse | Registra t₀ de cada tool call para medir duração real (`slow_op` detection) |
| `memory_hook.py` | PostToolUse | Captura contexto da sessão para memória persistente; detecta triggers de LESSON_LEARNED |
| `session_logger.py` | PostToolUse | Registra métricas finais de custo/turns/duração por sessão |
| `transcript_hook.py` | PostToolUse | Persiste transcript completo por sessão em `logs/sessions/<id>.jsonl` (append-only) — usado pelo `/resume` |
| `checkpoint.py` | — | Save/restore automático do estado da sessão |
| `session_lifecycle.py` | SessionStart/End | Injeção de memórias no início; config snapshot ao encerrar |

### Classificação de Custo de Operações

| Nível | Operações | Ação do Hook |
|-------|-----------|--------------|
| **HIGH** | Executar Jobs, Iniciar Clusters, Iniciar Pipelines | Alerta se > 5 na sessão |
| **MEDIUM** | Executar SQL no Warehouse | Log informativo |
| **LOW** | Consultar histórico, Queries KQL, Leituras de metadados | Log debug |

---

## 10. O Hub de Conhecimento (Skills e Knowledge Base)

### Skills Operacionais (`skills/`)

Manuais técnicos que os agentes **são obrigados a ler antes de agir**. Garantem que o código gerado siga padrões verificados em vez de inventar soluções.

**Skills Gerais:**

- `skills/patterns/pipeline-design/SKILL.md` — Arquitetura Medalhão com regras por camada (Bronze/Silver/Gold)
- `skills/patterns/spark-patterns/SKILL.md` — PySpark moderno: Delta Lake, MERGE, OPTIMIZE, VACUUM
- `skills/patterns/sql-generation/SKILL.md` — Padrões SQL com Liquid Clustering (substitui `PARTITIONED BY + ZORDER BY`)
- `skills/patterns/star-schema-design/SKILL.md` — 5 regras de ouro para criar tabelas Gold

**Skills Databricks (26+ skills):** Spark Declarative Pipelines, Structured Streaming, Jobs, Unity Catalog, MLflow Evaluation, Vector Search, Synthetic Data Generation, Model Serving, AI Functions, Lakebase, Apps Python, ZeroBus Ingest, DBSQL, Iceberg, e outras.

**Skills Microsoft Fabric (8+ skills):** Medallion, Direct Lake, RTI/Eventhouse, Data Factory, Cross-Platform, Deployment Pipelines, Git Integration, Monitoring DMV.

### Knowledge Base (`kb/`)

Documentos de referência lidos pelo Supervisor antes de planejar qualquer tarefa:

- `kb/constitution.md` — As 7 regras invioláveis do sistema (S1-S7)
- `kb/README.md` — Índice das KBs disponíveis por domínio

---

## 11. Conexões com a Nuvem (MCP Servers)

| MCP | Plataforma | Tipo | Principais capacidades |
|-----|------------|------|----------------------|
| `databricks` | Databricks | Oficial | SQL, tabelas, clusters, jobs, model serving, notebooks (50+ tools) |
| `databricks_genie` | Databricks Genie | Customizado | Genie Conversation API + Space Management (gap do oficial) |
| `fabric` | Microsoft Fabric | Oficial | REST API: workspaces, itens, upload/download OneLake, schedules |
| `fabric_community` | Fabric | Comunidade | Linhagem de dados, dependências entre itens |
| `fabric_sql` | Fabric SQL Analytics | Customizado | Queries via TDS — resolve limitação do schema `dbo` da REST API |
| `fabric_rti` | Fabric RTI | Customizado | KQL, Eventhouse, Eventstreams, Activator |
| `fabric_semantic` | Power BI / Fabric | Customizado | Introspecção de Semantic Models: TMDL, DAX, medidas, RLS, relacionamentos |
| `context7` | Documentação | Externo | Docs atualizadas de qualquer biblioteca — ativo automaticamente (sem credenciais) |
| `tavily` | Web | Externo | Busca web otimizada para LLMs |
| `github` | GitHub | Externo | Repos, issues, PRs, commits |
| `firecrawl` | Web | Externo | Web scraping e crawling estruturado |
| `postgres` | PostgreSQL | Externo | Queries readonly em bancos externos |
| `memory_mcp` | Local (JSON) | Customizado | Knowledge graph de entidades — ativo automaticamente (sem credenciais) |
| `migration_source` | SQL Server / PostgreSQL | Customizado | DDL, views, procedures, functions, stats do banco de origem |

### Por que MCPs Customizados?

Os quatro MCPs customizados resolvem gaps específicos que os MCPs oficiais não cobrem:

**`databricks_genie`** — O `databricks-mcp-server` oficial não expõe as tools de Genie Conversation. Este MCP conecta à Genie REST API usando as mesmas credenciais Databricks e suporta registry de múltiplos Spaces com nomes amigáveis.

**`fabric_sql`** — A REST API do Fabric só enxerga o schema `dbo`. Este MCP conecta via TDS (pyodbc + AAD Bearer Token) ao SQL Analytics Endpoint e suporta registry multi-lakehouse.

**`fabric_semantic`** — O MCP da comunidade não expõe TMDL, medidas DAX, relacionamentos ou RLS. Este MCP usa a Power BI REST API para introspectar Semantic Models existentes antes de propor mudanças.

**`migration_source`** — Conecta diretamente a bancos SQL Server e PostgreSQL de origem para extrair DDL completo, views, stored procedures, functions e estatísticas — essencial para as fases de ASSESS e ANALYZE do migration-expert.

---

## 12. Comandos Disponíveis (Slash Commands)

| Comando | Agente | Quando usar |
|---------|--------|-------------|
| `/plan <tarefa>` | Supervisor | Tarefas complexas que precisam de PRD e aprovação antes de executar |
| `/brief <texto>` | business-analyst | Converter reunião/briefing em backlog estruturado P0/P1/P2 |
| `/sql <tarefa>` | databricks-engineer | Queries SQL, análise de schemas, Unity Catalog |
| `/spark <tarefa>` | databricks-engineer | Código PySpark, Delta Lake, DLT/LakeFlow |
| `/pipeline <tarefa>` | databricks-engineer | Pipelines ETL/ELT completos com execução na nuvem |
| `/cdc <tarefa>` | databricks-engineer | CDC com Debezium, Kafka Connect, AUTO CDC INTO |
| `/diagnose <tarefa>` | databricks-engineer | Diagnóstico de jobs Spark: OOM, skew, shuffle, hangs |
| `/genie <tarefa>` | databricks-engineer | Criar/atualizar Genie Spaces no Databricks |
| `/dashboard <tarefa>` | databricks-engineer | Criar/publicar AI/BI Dashboards |
| `/ai <tarefa>` | databricks-ai | RAG, Vector Search, embeddings, LLMOps, AI Functions |
| `/streaming <tarefa>` | databricks-ai | Kafka, Flink, Spark Structured Streaming |
| `/fabric <tarefa>` | fabric-engineer | Qualquer tarefa Microsoft Fabric |
| `/semantic <tarefa>` | fabric-engineer | DAX, Direct Lake, modelos semânticos |
| `/schema <tarefa>` | fabric-engineer | Star Schema, Data Vault 2.0, SCD, modelagem dimensional |
| `/finops <tarefa>` | fabric-engineer | FinOps Fabric: Capacity Units, rightsizing, análise de custo |
| `/medallion <tarefa>` | fabric-engineer | Design Medallion Fabric: Bronze/Silver/Gold |
| `/catalog <subcmd>` | fabric-engineer | Documentar/avaliar catálogo de dados Fabric |
| `/migrate <fonte> para <destino>` | migration-expert | Assessment e migração de banco relacional para Databricks/Fabric |
| `/python <tarefa>` | python-expert | Python puro, scripts, APIs, CLIs, testes unitários, asyncio |
| `/dbt <tarefa>` | dbt-expert | Models, testes, snapshots, seeds, docs dbt |
| `/quality <tarefa>` | data-quality-steward | Validação de dados, profiling, SLAs de qualidade |
| `/governance <tarefa>` | governance-auditor | Auditoria, linhagem, LGPD, detecção de PII, RLS/OLS |
| `/contract <tarefa>` | data-contracts-engineer | Data Contracts ODCS, SLA, schema evolution, breaking changes |
| `/mesh <tarefa>` | data-mesh-architect | Data Mesh: domínios, Data Products, governança federada |
| `/ontology <tarefa>` | fabric-ontology | OWL 2: design, import/export Fabric OneLake |
| `/review <artefato>` | Supervisor | Review de código ou pipeline |
| `/party <query>` | Multi-agente | 2-8 agentes respondem simultaneamente (flags: `--quality`, `--arch`, `--engineering`, `--migration`, `--full`) |
| `/workflow <wf-id> <query>` | Multi-agente | Workflows colaborativos WF-01 a WF-05 com context chain |
| `/geral <pergunta>` | geral | Respostas conceituais sem Supervisor — ~95% mais barato |
| `/ship <título>` | business-analyst | Arquivar tarefa concluída com lições aprendidas |
| `/health` | — | Status de todas as plataformas configuradas |
| `/status` | — | Estado da sessão: custo, turns, PRDs gerados |
| `/memory <query>` | — | Consulta à memória persistente |
| `/sessions [all\|<id>]` | — | Lista sessões registradas (transcript + checkpoint) |
| `/resume [last\|<id>]` | — | Retoma sessão anterior reconstruindo contexto do transcript |
| `/export` | — | Exporta histórico da sessão para HTML (use Cmd+P para PDF) |

**Exemplos práticos:**

```
# Pipeline completo com aprovação prévia
/plan Crie um pipeline Bronze→Gold para dados de e-commerce com validação de qualidade

# Query SQL direta
/sql Gere a DDL da tabela de vendas com Liquid Clustering por data e categoria

# Migração de banco relacional
/migrate SQL Server ERP_PROD para Databricks poc_mas com mapeamento de tipos

# Múltiplas perspectivas simultâneas
/party --engineering Como processar um CSV de 10 GB de forma eficiente?

# Exportar a conversa atual como HTML/PDF
/export
```

---

## 13. Configuração e Credenciais

### 13.1. O arquivo `.env`

O `.env` nunca deve ir para o GitHub (está no `.gitignore`). Copie o `.env.example` e preencha:

```bash
cp .env.example .env
```

**Credenciais obrigatórias:**

```
ANTHROPIC_API_KEY=sk-ant-...           # sem isso o sistema não inicia
```

**Plataformas de dados (pelo menos uma):**

```
# Databricks
DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
DATABRICKS_TOKEN=dapiXXXXXXXXXXXXXXXXXX
DATABRICKS_SQL_WAREHOUSE_ID=XXXXXXXXXXXXXXXX

# Microsoft Fabric
AZURE_TENANT_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
AZURE_CLIENT_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
AZURE_CLIENT_SECRET=XXXX
FABRIC_WORKSPACE_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
```

**Roteamento de modelos por tier (importante):**

```
TIER_MODEL_MAP={"T1": "claude-sonnet-4-6", "T2": "claude-sonnet-4-6", "T3": "claude-sonnet-4-6"}
```

> Se `TIER_MODEL_MAP` não estiver definido, cada agente usa o modelo declarado no seu próprio arquivo em `agents/registry/`.

**MCPs externos (opcionais mas recomendados):**

```
TAVILY_API_KEY=tvly-...          # busca web — 1.000 créditos/mês grátis
GITHUB_PERSONAL_ACCESS_TOKEN=github_pat_...   # repos e PRs — gratuito
FIRECRAWL_API_KEY=fc-...         # web scraping — 500 créditos/mês grátis
POSTGRES_URL=postgresql://usuario:senha@host:5432/banco
```

### 13.2. Pré-requisitos de Sistema

**ODBC Driver 18** (para Fabric SQL e Migration Source com SQL Server):

```bash
# macOS
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18

# Linux
# https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
```

**.NET SDK 8.0** (para o MCP oficial do Fabric):

```bash
# macOS
brew install dotnet@8

# Linux: https://learn.microsoft.com/dotnet/core/install/linux
```

### 13.3. Scripts de Verificação de Saúde

```bash
python tools/databricks_health_check.py   # testa autenticação e Unity Catalog
python tools/fabric_health_check.py       # testa token Entra ID e API do Fabric
```

---

## 14. Sistema de Memória Persistente

O sistema possui dois layers de memória complementares:

### Layer 1 — Memória Episódica (`memory/`)

Captura fatos da sessão automaticamente via `memory_hook.py` e os persiste como arquivos Markdown individuais em `memory/data/{tipo}/{id}.md`. O retrieval é feito localmente via **SQLite FTS5 (BM25)** com reranking semântico opcional por embeddings ONNX — sem custo de API, latência < 5ms.

**8 tipos de memória com políticas de decay diferentes:**

| Tipo | Decay | Descrição |
|------|-------|-----------|
| `USER` | Nunca | Preferências e orientações do usuário |
| `ARCHITECTURE` | Nunca | Decisões de arquitetura do projeto |
| `DATA_ASSET` | Nunca | Tabelas, schemas, datasets e suas características |
| `PLATFORM_DECISION` | Nunca | Decisões sobre tecnologias, plataformas, integrações |
| `FEEDBACK` | 90 dias | Correções e orientações recebidas |
| `PIPELINE_STATUS` | 14 dias | Estado de execução de pipelines e jobs |
| `PROGRESS` | 7 dias | Tarefas em andamento |
| `LESSON_LEARNED` | 30 dias | Lições capturadas de erros e baixa performance — loop de aprendizado autônomo |

O retrieval é executado antes de cada query ao Supervisor: o sistema busca memórias relevantes pelo índice FTS5 e as injeta no system prompt, mantendo contexto entre sessões sem custo adicional de LLM.

#### Loop de Aprendizado Autônomo (LESSON_LEARNED)

O tipo `LESSON_LEARNED` alimenta um loop de aprendizado entre sessões: erros e eventos de baixa performance são automaticamente capturados, sumarizados via Haiku (~$0.001) e armazenados como conhecimento estruturado. Na próxima sessão, essas lições são injetadas no system prompt dos agentes T1 antes de operações de alto risco.

**Triggers de captura:**

| Trigger | Condição |
|---------|----------|
| `error` | Qualquer erro em tool MCP |
| `high_cost` | > 5 operações HIGH na sessão |
| `retries` | Mesmo agente chamado > 3× |
| `slow_op` | Tool MCP > 60 segundos de duração |

Cada lesson segue o formato *O que aconteceu / Causa raiz / Padrão para evitar*. Limite de 50 lessons por agente (deduplicação automática por sobreposição de summary > 60%).

Controle via `.env`:

```
MEMORY_ENABLED=true
MEMORY_RETRIEVAL_ENABLED=true
MEMORY_CAPTURE_ENABLED=true
MEMORY_RETRIEVAL_MAX=10           # máximo de memórias injetadas por query
```

### Layer 2 — Knowledge Graph (`memory_mcp/`)

Grafo persistente de entidades nomeadas (tabelas, pipelines, times, decisões) e suas relações. Gerenciado pelos agentes diretamente via MCP tools. Não aplica decay — persiste indefinidamente no arquivo `memory.json` do diretório de execução.

---

## 15. Roteamento de Modelos por Tier

O sistema usa uma hierarquia de configuração para determinar qual modelo Claude cada agente usa:

1. **`TIER_MODEL_MAP` no `.env`** — tem precedência máxima; sobrescreve tudo
2. **Campo `model:` no frontmatter do agente** (`agents/registry/<nome>.md`) — padrão por agente
3. **`DEFAULT_MODEL` no `.env`** — fallback global

Por padrão, o sistema usa **claude-sonnet-4-6** para todos os tiers T1/T2/T3 e **claude-haiku-4-5** para o T0 (`geral`). Para economizar custo em especialistas T2, você pode fazer override via `TIER_MODEL_MAP`:

```json
{
  "T1": "claude-sonnet-4-6",
  "T2": "claude-haiku-4-5",
  "T3": "claude-sonnet-4-6"
}
```

> **Nota:** O `geral` (T0) usa `claude-haiku-4-5` fixado no frontmatter — não é afetado pelo `TIER_MODEL_MAP`. É o tier mais barato e sem MCP, ideal para perguntas conceituais rápidas.

---

## 16. Qualidade de Código e Testes

### 16.1. Ferramentas de Qualidade

| Ferramenta | O que faz | Comando |
|------------|-----------|---------|
| **Ruff** | Linter e formatador (substitui flake8, black, isort) | `make lint` / `make format` |
| **Mypy** | Verificador de tipos estáticos | `make type-check` |
| **Bandit** | Scanner de segurança no código Python | `make security` |
| **Pre-commit** | Roda todas as verificações antes de cada `git commit` | `pre-commit install` |

### 16.2. Testes Automatizados

Cobertura mínima de 80%. Para rodar:

```bash
make test
# ou
pytest tests/ -v --tb=short --cov=agents --cov=config --cov=hooks --cov=commands
```

| Arquivo de Teste | O que testa |
|-----------------|-------------|
| `test_agents.py` | Definições dos agentes: modelo, ferramentas, prompts, tier |
| `test_commands.py` | Parser de slash commands |
| `test_exceptions.py` | Hierarquia de exceções |
| `test_hooks.py` | Bloqueios de segurança e registro de auditoria |
| `test_mcp_configs.py` | Configurações dos MCP servers |
| `test_mlflow_wrapper.py` | Wrapper MLflow |
| `test_settings.py` | Leitura e validação das configurações |
| `test_memory_lesson_learned.py` | LESSON_LEARNED: enum, CRUD, decay, prune, dedup, injeção (22 testes) |
| `test_s4_relaxation.py` | S4 Autonomous Mode: settings, log_s4_decision, constitution, supervisor prompt |

---

## 17. Deploy e CI/CD (Publicação Automática)

### 17.1. `databricks.yml` — Databricks Asset Bundles

Define três ambientes:

- **Dev:** Padrão para testes locais
- **Staging:** `/Shared/data-agents-staging` — validação antes de produção
- **Production:** `/Shared/data-agents-prod` — Service Principal dedicado

```bash
make deploy-staging    # publica em homologação
make deploy-prod       # publica em produção
```

### 17.2. GitHub Actions

**CI** (push para `main` / `develop`): Ruff → Mypy → pytest (cobertura 80%) → Bandit. Merge bloqueado em caso de falha.

**CD** (manual via `workflow_dispatch`): Deploy via `databricks bundle deploy` + sincronização das Skills para o workspace. O trigger por tag de versão foi removido — deploys são sempre manuais e deliberados.

---

## 18. Como Começar a Usar

**Pré-requisitos:**

- Python 3.11+
- .NET SDK 8.0+ (para o MCP oficial do Fabric)
- Conta Anthropic com créditos disponíveis
- Acesso a Databricks e/ou Microsoft Fabric (pelo menos um)

**Passo 1: Clonar o repositório**

```bash
git clone https://github.com/ThomazRossito/data-agents.git
cd data-agents
```

**Passo 2: Criar o ambiente virtual**

```bash
# Opção A: conda (recomendado)
conda create -n data-agents python=3.12 && conda activate data-agents

# Opção B: venv
python3 -m venv .venv && source .venv/bin/activate
```

**Passo 3: Instalar as dependências**

```bash
pip install -e ".[dev,ui,monitoring]"
```

**Passo 4: Configurar credenciais**

```bash
cp .env.example .env
# Edite .env com suas chaves reais
# Atenção especial para ANTHROPIC_API_KEY e TIER_MODEL_MAP
```

**Passo 5: Verificar pré-requisitos de sistema** (apenas se usar Fabric SQL ou Migration Source com SQL Server)

```bash
# macOS
HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
```

**Passo 6: Verificar conexões**

```bash
python tools/databricks_health_check.py
python tools/fabric_health_check.py
```

**Passo 7: Iniciar**

```bash
# Interface web Chainlit + Monitoring
./start.sh                     # acesse http://localhost:8503

# Terminal
python main.py
```

**Passo 8: Primeira verificação**

```
/health
```

Se retornar OK para as plataformas configuradas, está pronto para usar. Experimente:

```
/geral o que é arquitetura medalhão?
/sql descreva as tabelas disponíveis no catálogo
/plan crie um pipeline de ingestão incremental para dados de vendas
```

---

## 19. Conclusão

O projeto **Data Agents** representa uma abordagem madura e corporativa para o uso de IA em Engenharia de Dados, resolvendo os principais problemas que surgem em ambientes de produção:

**O problema da alucinação** é resolvido pelo Hub de Skills e Knowledge Base: a IA não inventa padrões — lê manuais verificados antes de agir, e o Supervisor valida o resultado contra a Constituição.

**O problema da segurança** é resolvido pelos 11 Hooks: nenhum comando destrutivo pode ser executado, e todas as ações ficam registradas em logs de auditoria JSONL.

**O problema do custo** é resolvido pelo Cost Guard e pelo roteamento por tier: cada tarefa usa o modelo adequado ao seu nível de complexidade, e o limite de orçamento por sessão é configurável.

**O problema da especialização** é resolvido pela arquitetura multi-agente: cada um dos 14 agentes tem papel bem definido, MCPs adequados ao seu domínio e permissões alinhadas ao seu nível de responsabilidade.

**O problema da observabilidade** é resolvido pelo Dashboard de Monitoramento (9 páginas) e pelo sistema de memória em dois layers, que mantém contexto entre sessões e acumula conhecimento sobre o projeto ao longo do tempo.

Para um profissional Junior, este projeto é um estudo de caso de como construir sistemas de IA responsáveis e prontos para o ambiente corporativo, combinando as melhores práticas de Engenharia de Software (testes, CI/CD, linting) com as melhores práticas de Engenharia de Dados (Arquitetura Medalhão, Star Schema, Liquid Clustering, Genie Spaces).
