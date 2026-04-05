# Manual e Relatório Técnico: Projeto Data Agents

---

Repositório:  [github.com/ThomazRossito/data-agents](https://github.com/ThomazRossito/data-agents)

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

1. [O que é este projeto?](#1-o-que-%C3%A9-este-projeto)
2. [Conceitos Fundamentais (Glossário para Iniciantes)](#2-conceitos-fundamentais-gloss%C3%A1rio-para-iniciantes)
3. [Arquitetura Geral do Sistema](#3-arquitetura-geral-do-sistema)
4. [Os Agentes: A Equipe Virtual](#4-os-agentes-a-equipe-virtual)
5. [O Método BMAD: Como a IA Trabalha](#5-o-m%C3%A9todo-bmad-como-a-ia-trabalha)
6. [Estrutura de Arquivos e Pastas](#6-estrutura-de-arquivos-e-pastas)
7. [Análise Detalhada de Cada Componente](#7-an%C3%A1lise-detalhada-de-cada-componente)
8. [Segurança e Controle de Custos (Hooks)](#8-seguran%C3%A7a-e-controle-de-custos-hooks)
9. [O Hub de Conhecimento (Skills)](#9-o-hub-de-conhecimento-skills)
10. [Conexões com a Nuvem (MCP Servers)](#10-conex%C3%B5es-com-a-nuvem-mcp-servers)
11. [Comandos Disponíveis (Slash Commands)](#11-comandos-dispon%C3%ADveis-slash-commands)
12. [Configuração e Credenciais](#12-configura%C3%A7%C3%A3o-e-credenciais)
13. [Qualidade de Código e Testes](#13-qualidade-de-c%C3%B3digo-e-testes)
14. [Deploy e CI/CD (Publicação Automática)](#14-deploy-e-cicd-publica%C3%A7%C3%A3o-autom%C3%A1tica)
15. [Como Começar a Usar](#15-como-come%C3%A7ar-a-usar)
16. [Conclusão](#16-conclus%C3%A3o)

---

## 1. O que é este projeto?

O **Data Agents** é um sistema de **múltiplos agentes de Inteligência Artificial** especializado em Engenharia de Dados. Em termos simples, é como ter uma equipe de engenheiros de dados virtuais que trabalham juntos para resolver problemas complexos de dados, desde escrever consultas SQL até criar e executar pipelines completos em plataformas de nuvem como Databricks e Microsoft Fabric.

O sistema é construído sobre o modelo de linguagem **Claude** da empresa Anthropic e utiliza uma tecnologia chamada **MCP (Model Context Protocol)** para que a IA possa interagir diretamente com as plataformas de dados, como se fosse um engenheiro humano acessando o painel de controle.

O grande diferencial deste projeto em relação a um simples "chatbot de programação" é a sua **camada de governança e conhecimento**. A IA não inventa soluções do zero; ela é obrigada a ler manuais de boas práticas (chamados de "Skills") antes de agir, garantindo que o código gerado seja seguro, eficiente e alinhado com os padrões corporativos modernos.

---

## 2. Conceitos Fundamentais (Glossário para Iniciantes)

Antes de mergulhar nos detalhes técnicos, é essencial entender alguns termos que aparecem frequentemente no projeto. Esta seção serve como um dicionário rápido.

| Termo                                  | O que significa na prática                                                                                                                                                                                    |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Agente de IA**                 | Um programa de IA que pode tomar decisões, usar ferramentas e executar tarefas de forma autônoma, não apenas responder perguntas.                                                                           |
| **LLM (Large Language Model)**   | O "cérebro" da IA. No caso deste projeto, é o Claude da Anthropic. É o modelo que entende o que você pede e gera as respostas.                                                                             |
| **MCP (Model Context Protocol)** | Uma "tomada universal" que permite que a IA se conecte a ferramentas externas (como o Databricks) de forma padronizada e segura.                                                                               |
| **Databricks**                   | Uma plataforma de nuvem especializada em processamento de grandes volumes de dados usando Apache Spark. É muito usada por grandes empresas para análise de dados.                                            |
| **Microsoft Fabric**             | A plataforma de dados da Microsoft, que integra armazenamento, processamento e visualização de dados em um único ambiente.                                                                                  |
| **Apache Spark**                 | Uma tecnologia de processamento de dados em larga escala. Imagine que você precisa processar bilhões de linhas de uma planilha; o Spark faz isso de forma distribuída em vários servidores ao mesmo tempo. |
| **Pipeline de Dados**            | Uma "linha de montagem" para dados. Os dados entram brutos de um lado, passam por várias etapas de transformação e saem limpos e organizados do outro.                                                      |
| **Arquitetura Medalhão**        | Um padrão de organização de dados em três camadas: Bronze (dados brutos), Silver (dados limpos) e Gold (dados prontos para análise).                                                                      |
| **SQL**                          | A linguagem padrão para consultar bancos de dados. É como fazer perguntas ao banco de dados: "Mostre-me todos os clientes que compraram em janeiro".                                                         |
| **PySpark**                      | Python + Spark. É a forma de programar o Spark usando a linguagem Python.                                                                                                                                     |
| **Delta Lake**                   | Um formato de armazenamento de dados que adiciona funcionalidades como histórico de versões e transações seguras ao armazenamento em nuvem.                                                                |
| **Unity Catalog**                | O sistema de catálogo e governança de dados do Databricks. É como um índice centralizado de todos os dados da empresa, com controle de quem pode acessar o quê.                                           |
| **Star Schema**                  | Um modelo de organização de dados para análise, com uma tabela central de fatos (ex: vendas) rodeada por tabelas de dimensões (ex: clientes, produtos, datas).                                             |
| **Hook**                         | Um "gancho" de código que é executado automaticamente antes ou depois de uma ação. Neste projeto, os hooks interceptam as ações da IA para garantir segurança.                                          |
| **JSONL**                        | Um formato de arquivo onde cada linha é um objeto JSON independente. Muito usado para logs porque é fácil de processar linha por linha.                                                                     |
| **API Key**                      | Uma senha especial que identifica quem está fazendo uma chamada a um serviço externo (como a API da Anthropic).                                                                                              |
| **PRD**                          | *Product Requirements Document*. Um documento que descreve o que precisa ser construído, como e por quê.                                                                                                   |

---

## 3. Arquitetura Geral do Sistema

Para entender como tudo se encaixa, imagine o seguinte fluxo:

```
 Você digita um comando no terminal
        │
        ▼
┌─────────────────────────────────────────┐
│             main.py (Interface)         │
│  Recebe o comando, exibe o resultado    │
└───────────────────┬─────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│        Supervisor (Gerente)             │
│  Lê Skills → Cria PRD → Delega tarefa   │
└──────┬──────────┬───────────────┬───────┘
       │          │               │
       ▼          ▼               ▼
 SQL Expert  Spark Expert   Pipeline Architect
 (Consultas) (Código Spark) (Execução na Nuvem)
       │          │              │
       └──────────┴──────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         MCP Servers (Pontes)            │
│  Databricks │ Fabric │ Fabric RTI       │
└─────────────────────────────────────────┘
                  │
                  ▼
         Plataformas de Nuvem Reais
```

Em paralelo a todo esse fluxo, os **Hooks** ficam monitorando cada ação: bloqueando comandos perigosos, registrando tudo em logs e alertando sobre custos elevados.

---

## 4. Os Agentes: A Equipe Virtual

### 4.1. O Supervisor

**Arquivo:** `agents/supervisor.py`**Modelo de IA:** `claude-opus-4-6` (o modelo mais poderoso e caro da família Claude)**Analogia:** O Gerente de Projetos Sênior.

O Supervisor é o ponto de entrada de todas as interações. Ele utiliza o modelo mais avançado porque precisa ter a capacidade de raciocínio mais sofisticada para planejar, coordenar e delegar corretamente.

Suas responsabilidades incluem: analisar o pedido do usuário, identificar quais manuais de boas práticas (Skills) são relevantes, criar um documento de arquitetura (PRD), acionar o especialista correto e, ao final, validar e sintetizar o resultado.

O Supervisor tem acesso a todos os servidores MCP (Databricks, Fabric, Fabric RTI) e possui hooks de segurança e controle de custos ativos em suas operações.

### 4.2. SQL Expert

**Arquivo:** `agents/definitions/sql_expert.py`**Modelo de IA:** `claude-sonnet-4-6` (modelo intermediário, equilibrado entre capacidade e custo)**Limite de turnos:** 15 interações por tarefa**Analogia:** O Analista de Dados.

O SQL Expert é especializado em linguagens de consulta de dados: SQL padrão, T-SQL (versão da Microsoft), Spark SQL (versão do Databricks) e KQL (*Kusto Query Language*, usada no Microsoft Fabric Real-Time Intelligence).

Uma característica fundamental deste agente é que ele tem **permissão apenas de leitura**. Isso significa que ele pode consultar dados, inspecionar estruturas de tabelas e gerar código SQL, mas não pode apagar tabelas, executar jobs ou mover dados. Essa restrição é uma medida de segurança importante.

As ferramentas disponíveis para ele são filtradas para incluir apenas operações que começam com `list_`, `get_`, `describe_`, `sample_` ou `export_`, que são todas operações não destrutivas.

### 4.3. Spark Expert

**Arquivo:** `agents/definitions/spark_expert.py`**Modelo de IA:** `claude-sonnet-4-6`**Limite de turnos:** 20 interações por tarefa**Analogia:** O Desenvolvedor Back-end de Big Data.

O Spark Expert é o gerador de código PySpark e Spark SQL. Ele é especializado em criar pipelines de dados no padrão moderno do Databricks, incluindo:

- **Spark Declarative Pipelines (SDP/LakeFlow/DLT):** A forma mais moderna de criar pipelines no Databricks, onde você declara o que quer (resultado final) e o sistema descobre como fazer.
- **Operações Delta Lake:** Como fazer MERGE (atualizar dados de forma eficiente), OPTIMIZE (reorganizar arquivos para melhor performance) e VACUUM (limpar arquivos antigos).
- **SCD Tipo 1 e Tipo 2:** Técnicas para rastrear mudanças históricas em dados (ex: quando um cliente muda de endereço, você quer manter o endereço antigo para análises históricas).

**Importante:** O Spark Expert **não se conecta diretamente à nuvem**. Ele apenas gera código. Isso é uma decisão de design intencional: ele recebe o contexto (esquemas de tabelas, regras de negócio) do Supervisor e devolve código pronto, que depois é executado pelo Pipeline Architect.

### 4.4. Pipeline Architect

**Arquivo:** `agents/definitions/pipeline_architect.py`**Modelo de IA:** `claude-opus-4-6` (o mais poderoso, pois toma decisões críticas)**Limite de turnos:** 30 interações por tarefa**Analogia:** O Engenheiro de DevOps / DataOps.

O Pipeline Architect é o único agente com **permissões amplas de execução**. Ele pode:

- Executar jobs no Databricks (`run_job_now`).
- Iniciar e parar pipelines (`start_pipeline`, `stop_pipeline`).
- Fazer upload e download de arquivos no OneLake (armazenamento do Microsoft Fabric).
- Criar e configurar pipelines no Data Factory do Fabric.
- Executar comandos via terminal (`Bash`).

Ele tem acesso a todas as ferramentas disponíveis nos três servidores MCP, exceto operações KQL destrutivas no Fabric RTI.

A tabela abaixo resume as diferenças entre os agentes:

| Agente             | Modelo            | Pode Escrever?        | Pode Executar Jobs? | Acessa Nuvem?         |
| ------------------ | ----------------- | --------------------- | ------------------- | --------------------- |
| Supervisor         | claude-opus-4-6   | Sim (PRDs)            | Não                | Sim (leitura)         |
| SQL Expert         | claude-sonnet-4-6 | Não                  | Não                | Sim (só leitura)     |
| Spark Expert       | claude-sonnet-4-6 | Sim (arquivos locais) | Não                | Não                  |
| Pipeline Architect | claude-opus-4-6   | Sim                   | **Sim**       | **Sim (total)** |

---

## 5. O Método BMAD: Como a IA Trabalha

O **BMAD** (*Breakthrough Method for Agile AI-Driven Development*) é o protocolo central que governa como os agentes trabalham. Ele foi criado para evitar o problema mais comum com IAs generativas: gerar código bonito mas incorreto, sem seguir os padrões da empresa.

### Os 5 Passos do BMAD

**Passo 0 — Triage (Triagem):** O Supervisor recebe o seu pedido e classifica o tipo de tarefa. É uma consulta SQL simples? É um pipeline completo? Precisa de aprovação antes de executar?

**Passo 1 — Context Engineering (Engenharia de Contexto):** Antes de qualquer ação, o Supervisor é *obrigado* a ler os arquivos de Skills relevantes. Se você pediu um pipeline no Databricks, ele vai ler `skills/databricks/databricks-spark-declarative-pipelines/SKILL.md`. Isso garante que a IA saiba as melhores práticas antes de agir.

**Passo 2 — PRD (Documento de Requisitos):** Para tarefas complexas (modo `/plan`), o Supervisor cria um documento de arquitetura detalhado e o salva na pasta `output/`. Você pode revisar esse documento antes de autorizar a execução.

**Passo 3 — Delegação:** Com o plano aprovado, o Supervisor aciona o especialista correto e passa todas as informações necessárias (esquemas de tabelas, regras de negócio, padrões a seguir).

**Passo 4 — Síntese:** O resultado é validado e entregue a você com um resumo do que foi feito, quanto custou e quantas interações foram necessárias.

### Modos de Operação

O sistema oferece dois modos principais de trabalho:

**BMAD Full (****`/plan`****):** Executa todos os 5 passos, incluindo a criação do PRD e a pausa para aprovação. Ideal para tarefas grandes e críticas onde você quer revisar antes de executar.

**BMAD Express (****`/sql`****, ****`/spark`****, ****`/pipeline`****, ****`/fabric`****):** Pula a criação do PRD e vai direto ao especialista. Ideal para tarefas menores e mais diretas.

---

## 6. Estrutura de Arquivos e Pastas

A tabela abaixo apresenta uma visão completa da estrutura do projeto:

| Caminho                              | Tipo                      | Descrição                                                            |
| ------------------------------------ | ------------------------- | ---------------------------------------------------------------------- |
| `main.py`                          | Arquivo Python            | Ponto de entrada do sistema; interface de linha de comando             |
| `pyproject.toml`                   | Arquivo de Configuração | Dependências e metadados do projeto Python                            |
| `Makefile`                         | Arquivo de Automação    | Atalhos para tarefas comuns (instalar, testar, rodar)                  |
| `.env.example`                     | Arquivo de Modelo         | Template para configurar credenciais (nunca versionar o `.env` real) |
| `databricks.yml`                   | Arquivo YAML              | Configuração para deploy no Databricks via Asset Bundles             |
| `fabric_environment.yml`           | Arquivo YAML              | Configuração do ambiente conda para uso em notebooks do Fabric       |
| `.pre-commit-config.yaml`          | Arquivo de Configuração | Regras de qualidade que rodam antes de cada commit no Git              |
| `agents/`                          | Pasta                     | Definições, prompts e lógica de todos os agentes                    |
| `agents/supervisor.py`             | Arquivo Python            | Lógica de orquestração do Supervisor                                |
| `agents/mlflow_wrapper.py`         | Arquivo Python            | Integração com MLflow para deploy em Model Serving do Databricks     |
| `agents/definitions/`              | Pasta                     | Definições dos agentes especialistas                                 |
| `agents/prompts/`                  | Pasta                     | Instruções de comportamento de cada agente                           |
| `config/`                          | Pasta                     | Configurações globais do sistema                                     |
| `config/settings.py`               | Arquivo Python            | Leitura e validação das variáveis de ambiente                       |
| `config/exceptions.py`             | Arquivo Python            | Hierarquia de erros personalizados do sistema                          |
| `config/mcp_servers.py`            | Arquivo Python            | Registro e ativação dos servidores MCP                               |
| `config/logging_config.py`         | Arquivo Python            | Configuração do sistema de logs                                      |
| `commands/`                        | Pasta                     | Lógica dos slash commands (`/sql`, `/spark`, etc.)                |
| `hooks/`                           | Pasta                     | Interceptadores de segurança, auditoria e custo                       |
| `hooks/security_hook.py`           | Arquivo Python            | Bloqueio de 17 padrões destrutivos e 11 de evasão                    |
| `hooks/audit_hook.py`              | Arquivo Python            | Registro de todas as ações em JSONL                                  |
| `hooks/cost_guard_hook.py`         | Arquivo Python            | Monitoramento e alerta de custos por tier                              |
| `mcp_servers/`                     | Pasta                     | Configurações de conexão com plataformas de nuvem                   |
| `mcp_servers/databricks/`          | Pasta                     | Configuração e lista de ferramentas do Databricks                    |
| `mcp_servers/fabric/`              | Pasta                     | Configuração e lista de ferramentas do Microsoft Fabric              |
| `mcp_servers/fabric_rti/`          | Pasta                     | Configuração para Real-Time Intelligence do Fabric                   |
| `mcp_servers/_template/`           | Pasta                     | Template para adicionar novas plataformas                              |
| `skills/`                          | Pasta                     | Hub de Conhecimento: manuais de boas práticas                         |
| `skills/pipeline_design.md`        | Arquivo Markdown          | Arquitetura Medalhão e regras por camada                              |
| `skills/spark_patterns.md`         | Arquivo Markdown          | Padrões PySpark modernos                                              |
| `skills/sql_generation.md`         | Arquivo Markdown          | Padrões SQL com Liquid Clustering                                     |
| `skills/star_schema_design.md`     | Arquivo Markdown          | 5 regras de design da camada Gold                                      |
| `skills/databricks/`               | Pasta                     | 26 Skills específicas do Databricks                                   |
| `skills/fabric/`                   | Pasta                     | 5 Skills específicas do Microsoft Fabric                              |
| `tools/`                           | Pasta                     | Scripts utilitários para o usuário                                   |
| `tools/databricks_health_check.py` | Arquivo Python            | Valida autenticação e conexão com Databricks                        |
| `tools/fabric_health_check.py`     | Arquivo Python            | Valida autenticação e conexão com Microsoft Fabric                  |
| `tests/`                           | Pasta                     | Suíte de testes automatizados (pytest)                                |
| `output/`                          | Pasta                     | Artefatos gerados pelos agentes (PRDs)                                 |
| `logs/`                            | Pasta                     | Arquivos de log de auditoria e sistema                                 |
| `.github/`                         | Pasta                     | Workflows de CI/CD do GitHub Actions                                   |

---

## 7. Análise Detalhada de Cada Componente

### 7.1. `main.py` — A Interface Principal

Este é o arquivo que você executa para iniciar o sistema. Ele tem duas funções principais:

**Modo Interativo:** Quando você roda `python main.py` sem argumentos, ele abre um loop de conversa no terminal. Você digita um comando, a IA processa e responde, e o ciclo se repete até você digitar `sair`.

**Modo de Consulta Única:** Quando você passa um argumento direto (ex: `python main.py "Analise a tabela de vendas"`), ele processa aquela consulta específica e encerra.

O arquivo também é responsável por exibir o progresso em tempo real enquanto a IA trabalha, mostrando qual ferramenta está sendo usada no momento (ex: "Lendo skill de pipeline..."), e por exibir o custo total e o número de interações ao final de cada resposta.

### 7.2. `config/settings.py` — O Painel de Controle

Este arquivo usa uma biblioteca chamada **Pydantic Settings** para ler as variáveis de ambiente do arquivo `.env` e transformá-las em um objeto Python tipado e validado.

As configurações disponíveis são:

| Variável                       | Padrão                | Descrição                                      |
| ------------------------------- | ---------------------- | ------------------------------------------------ |
| `ANTHROPIC_API_KEY`           | (obrigatório)         | Chave de acesso à API do Claude                 |
| `DATABRICKS_HOST`             | (opcional)             | URL do workspace Databricks                      |
| `DATABRICKS_TOKEN`            | (opcional)             | Token de autenticação do Databricks            |
| `DATABRICKS_SQL_WAREHOUSE_ID` | (opcional)             | ID do SQL Warehouse para executar queries        |
| `AZURE_TENANT_ID`             | (opcional)             | ID do tenant Azure para autenticação no Fabric |
| `AZURE_CLIENT_ID`             | (opcional)             | ID do Service Principal Azure                    |
| `AZURE_CLIENT_SECRET`         | (opcional)             | Senha do Service Principal Azure                 |
| `FABRIC_WORKSPACE_ID`         | (opcional)             | ID do workspace do Microsoft Fabric              |
| `KUSTO_SERVICE_URI`           | (opcional)             | URL do Eventhouse (banco KQL do Fabric RTI)      |
| `DEFAULT_MODEL`               | `claude-opus-4-6`    | Modelo padrão do Claude a ser usado             |
| `MAX_BUDGET_USD`              | `5.0`                | Limite máximo de gasto em dólares por sessão  |
| `MAX_TURNS`                   | `50`                 | Número máximo de interações por sessão      |
| `LOG_LEVEL`                   | `INFO`               | Nível de detalhe dos logs                       |
| `AUDIT_LOG_PATH`              | `./logs/audit.jsonl` | Caminho do arquivo de auditoria                  |

O sistema também realiza um **diagnóstico automático na inicialização**: verifica quais plataformas têm credenciais configuradas e emite avisos se alguma estiver faltando. Se a chave da Anthropic não estiver configurada, o sistema nem inicia.

### 7.3. `config/exceptions.py` — Hierarquia de Erros

Este arquivo define uma família de erros personalizados para o projeto. Em vez de erros genéricos do Python, o sistema usa erros específicos que facilitam o diagnóstico:

| Classe de Erro             | Quando ocorre                                     |
| -------------------------- | ------------------------------------------------- |
| `DataAgentsError`        | Erro base; todos os outros herdam dele            |
| `MCPConnectionError`     | Falha ao conectar com Databricks ou Fabric        |
| `AuthenticationError`    | Credenciais inválidas ou ausentes                |
| `BudgetExceededError`    | Custo da sessão ultrapassou o limite configurado |
| `MaxTurnsExceededError`  | Número de interações ultrapassou o limite      |
| `SecurityViolationError` | Comando bloqueado pelo hook de segurança         |
| `SkillNotFoundError`     | Arquivo de skill referenciado não encontrado     |
| `ConfigurationError`     | Erro nas configurações do sistema               |

### 7.4. `agents/mlflow_wrapper.py` — Integração com MLflow

Este arquivo permite que o Data Agent seja publicado como um **endpoint de API** dentro do Databricks, usando o framework MLflow. Isso significa que, em vez de usar o sistema pelo terminal, uma empresa poderia integrá-lo a um sistema interno e fazer chamadas via API HTTP.

O wrapper implementa a interface `mlflow.pyfunc.PythonModel`, que é o padrão do Databricks para servir modelos de Machine Learning e agentes de IA. Ele recebe requisições no formato OpenAI Messages (o mesmo formato usado pelo ChatGPT), o que facilita a integração com outras ferramentas.

---

## 8. Segurança e Controle de Custos (Hooks)

Os hooks são um dos componentes mais importantes do projeto do ponto de vista de governança. Eles funcionam como interceptadores que são ativados automaticamente antes (`PreToolUse`) ou depois (`PostToolUse`) de cada ação da IA.

### 8.1. `hooks/security_hook.py` — O Segurança

Este hook é ativado **antes** de qualquer execução de comando no terminal (ferramenta `Bash`). Ele verifica o comando contra uma lista de 17 padrões destrutivos e 11 padrões de evasão usando expressões regulares.

Exemplos de comandos que seriam bloqueados:

- `DROP TABLE` ou `DROP DATABASE` (apagar tabelas ou bancos de dados)
- `DELETE FROM` sem cláusula `WHERE` (apagar todos os registros de uma tabela)
- `rm -rf` (apagar arquivos recursivamente no Linux)
- `TRUNCATE TABLE` (esvaziar uma tabela)
- Qualquer tentativa de acessar arquivos de credenciais (`.env`, `.ssh/`)

Quando um comando bloqueado é detectado, o hook retorna uma decisão `deny` (negar) com uma mensagem explicando o motivo do bloqueio, e a ação nunca é executada.

### 8.2. `hooks/audit_hook.py` — O Contador

Este hook é ativado **depois** de cada uso de ferramenta pela IA. Ele registra em um arquivo JSONL (`logs/audit.jsonl`) um registro com:

- Timestamp (data e hora exatos da ação)
- Nome da ferramenta usada
- Tipo de operação (leitura, escrita, execução, etc.)
- Nomes dos parâmetros usados (mas não os valores, por segurança)

Isso cria um histórico completo de auditoria: você pode sempre voltar e ver exatamente o que a IA fez, quando fez e com quais parâmetros. O hook possui um mecanismo de fallback: se não conseguir escrever no arquivo, tenta registrar via `stderr` para garantir que nenhuma ação fique sem registro.

### 8.3. `hooks/cost_guard_hook.py` — O Controlador de Orçamento

Este hook classifica cada operação em três níveis de custo e emite alertas:

| Tier                      | Operações                                        | Ação do Hook                                                            |
| ------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------- |
| **HIGH** (Alto)     | Executar Jobs, Iniciar Clusters, Iniciar Pipelines | Emite `WARNING` no log; alerta se mais de 5 operações HIGH na sessão |
| **MEDIUM** (Médio) | Executar SQL no Warehouse                          | Emite `INFO` no log                                                     |
| **LOW** (Baixo)     | Consultar histórico de queries, Queries KQL       | Emite `DEBUG` no log                                                    |

O hook também mantém contadores de sessão, permitindo que você veja um resumo de quantas operações de cada tipo foram realizadas (disponível via `/status`).

---

## 9. O Hub de Conhecimento (Skills)

A pasta `skills/` é o coração intelectual do projeto. Ela contém dezenas de arquivos Markdown que funcionam como manuais técnicos que os agentes são obrigados a ler antes de agir.

### 9.1. Skills Gerais

**`skills/pipeline_design.md`** — Ensina a Arquitetura Medalhão:

- **Bronze:** Dados brutos, sem transformação. Adicione apenas metadados como timestamp de ingestão e nome do arquivo fonte.
- **Silver:** Dados limpos e padronizados. Aplique tipagem, remoção de duplicatas e regras de qualidade.
- **Gold:** Dados agregados e modelados para análise. Aqui fica o Star Schema com tabelas de dimensões e fatos.

**`skills/spark_patterns.md`** — Padrões modernos de PySpark, incluindo como ler e escrever dados no Delta Lake corretamente.

**`skills/sql_generation.md`** — Padrões SQL para o Databricks, com foco no **Liquid Clustering** (uma tecnologia moderna que substitui o antigo `PARTITIONED BY + ZORDER BY` para organizar dados de forma mais eficiente).

**`skills/star_schema_design.md`** — As 5 regras de ouro para criar tabelas Gold:

1. Tabelas de dimensão (`dim_*`) nunca derivam de tabelas de fatos.
2. A dimensão de data é sempre gerada sinteticamente (não extraída dos dados).
3. Chaves substitutas (`sk_*`) são geradas com `SEQUENCE` ou `ROW_NUMBER`.
4. Tabelas fato fazem `INNER JOIN` em todas as dimensões (sem dados órfãos).
5. Dimensões são autônomas e têm sua própria fonte de dados.

### 9.2. Skills Databricks (26 skills)

A pasta `skills/databricks/` contém manuais específicos para cada tecnologia do ecossistema Databricks:

| Skill                                       | O que ensina                                             |
| ------------------------------------------- | -------------------------------------------------------- |
| `databricks-spark-declarative-pipelines/` | Como criar pipelines SDP/LakeFlow/DLT modernos           |
| `databricks-spark-structured-streaming/`  | Processamento de dados em tempo real com Spark Streaming |
| `databricks-jobs/`                        | Como criar e orquestrar Jobs multi-tarefa no Databricks  |
| `databricks-bundles/`                     | CI/CD com Databricks Asset Bundles (DABs)                |
| `databricks-unity-catalog/`               | Governança de dados com Unity Catalog                   |
| `databricks-mlflow/`                      | Rastreamento de experimentos e modelos com MLflow        |
| `databricks-vector-search/`               | Busca semântica e RAG (Retrieval-Augmented Generation)  |
| `databricks-synthetic-data-gen/`          | Geração de dados sintéticos para testes               |
| `spark-python-data-source/`               | Como criar conectores customizados para o Spark          |
| `databricks-zerobus-ingest/`              | Ingestão de dados via protocolo ZeroBus                 |

### 9.3. Skills Microsoft Fabric (5 skills)

A pasta `skills/fabric/` cobre as principais tecnologias do Microsoft Fabric:

| Skill                      | O que ensina                                                       |
| -------------------------- | ------------------------------------------------------------------ |
| `fabric-medallion/`      | Arquitetura Medalhão no Fabric Lakehouse com PySpark e T-SQL      |
| `fabric-direct-lake/`    | Como configurar o Direct Lake para Power BI ler dados sem importar |
| `fabric-eventhouse-rti/` | Real-Time Intelligence com Eventhouse e KQL                        |
| `fabric-data-factory/`   | Pipelines de ingestão com Data Factory no Fabric                  |
| `fabric-cross-platform/` | Integração entre Fabric e Databricks                             |

---

## 10. Conexões com a Nuvem (MCP Servers)

A pasta `mcp_servers/` contém as configurações que permitem à IA interagir com as plataformas de nuvem. Cada subpasta representa uma "ponte" para uma plataforma diferente.

### 10.1. Databricks MCP (`mcp_servers/databricks/`)

Utiliza o pacote oficial `databricks-mcp-server` da Databricks. Expõe mais de 50 ferramentas organizadas em categorias:

| Categoria                             | Ferramentas Disponíveis                                               |
| ------------------------------------- | ---------------------------------------------------------------------- |
| **Unity Catalog**               | Listar catálogos, schemas, tabelas; descrever tabelas; amostrar dados |
| **SQL**                         | Executar SQL, listar warehouses, consultar histórico                  |
| **Jobs & Workflows**            | Listar, disparar, cancelar e monitorar jobs                            |
| **Spark Declarative Pipelines** | Listar, criar, iniciar, parar e monitorar pipelines                    |
| **Clusters**                    | Listar, iniciar e inspecionar clusters                                 |
| **Workspace & Notebooks**       | Navegar, exportar e importar notebooks                                 |
| **Files & Volumes**             | Listar, ler e fazer upload de arquivos                                 |

### 10.2. Microsoft Fabric MCP (`mcp_servers/fabric/`)

Utiliza dois servidores: o oficial da Microsoft (em .NET) e um servidor da comunidade (em Python). Juntos, expõem ferramentas para:

- Gerenciar workspaces e itens do Fabric.
- Fazer upload e download de arquivos no OneLake.
- Consultar especificações da API do Fabric.
- Listar instâncias de jobs e schedules.
- Consultar linhagem e dependências de dados.

### 10.3. Fabric RTI MCP (`mcp_servers/fabric_rti/`)

Dedicado ao componente de **Real-Time Intelligence** do Fabric. Expõe ferramentas para:

- Executar queries KQL no Eventhouse.
- Listar bancos de dados e tabelas.
- Ingerir dados inline.
- Gerenciar Eventstreams (pipelines de dados em tempo real).
- Criar triggers de alerta com o Activator.

### 10.4. Template para Novas Plataformas (`mcp_servers/_template/`)

O projeto inclui um template documentado para facilitar a adição de novas plataformas (como Snowflake, BigQuery, etc.). O processo envolve copiar o template, implementar a função de configuração e registrar o novo servidor no arquivo `config/mcp_servers.py`.

---

## 11. Comandos Disponíveis (Slash Commands)

Os slash commands são atalhos que você digita no terminal para interagir com o sistema. Eles são definidos na pasta `commands/`.

| Comando                 | Modo         | Agente Acionado    | Quando Usar                                                                         |
| ----------------------- | ------------ | ------------------ | ----------------------------------------------------------------------------------- |
| `/plan <tarefa>`      | BMAD Full    | Supervisor         | Para tarefas complexas que precisam de planejamento e aprovação antes de executar |
| `/sql <tarefa>`       | BMAD Express | SQL Expert         | Para gerar queries SQL, analisar schemas, modelagem dimensional                     |
| `/spark <tarefa>`     | BMAD Express | Spark Expert       | Para gerar código PySpark, pipelines SDP/LakeFlow                                  |
| `/pipeline <tarefa>`  | BMAD Express | Pipeline Architect | Para criar e executar pipelines completos no Databricks                             |
| `/fabric <tarefa>`    | BMAD Express | Pipeline Architect | Para trabalhar com Microsoft Fabric (Lakehouse, Data Factory, RTI)                  |
| `/health`             | Internal     | Supervisor         | Para verificar se as conexões com Databricks e Fabric estão funcionando           |
| `/status`             | Internal     | Supervisor         | Para listar os PRDs gerados na pasta `output/`                                    |
| `/review [arquivo]`   | Internal     | Supervisor         | Para revisar ou continuar um PRD existente                                          |
| `/help`               | —           | —                 | Para exibir a lista de todos os comandos                                            |
| `sair` ou `exit`    | —           | —                 | Para encerrar a sessão                                                             |
| `limpar` ou `clear` | —           | —                 | Para limpar a tela e iniciar uma nova sessão                                       |

**Exemplos práticos de uso:**

Para criar um pipeline completo com aprovação prévia:

```
/plan Crie um pipeline SDP Bronze→Silver→Gold para dados de e-commerce
```

Para gerar uma query SQL rapidamente:

```
/sql Gere a DDL da tabela de vendas com Liquid Clustering por data e categoria
```

Para verificar se tudo está funcionando:

```
/health
```

---

## 12. Configuração e Credenciais

### 12.1. O arquivo `.env`

O arquivo `.env` é onde você armazena todas as senhas e chaves de acesso. Ele nunca deve ser enviado para o GitHub (está no `.gitignore`). O projeto fornece um modelo chamado `.env.example` que você deve copiar e preencher.

```
# Chave obrigatória — sem ela o sistema não funciona
ANTHROPIC_API_KEY=sk-ant-...

# Credenciais do Databricks
DATABRICKS_HOST=https://adb-XXXXXXXXXXXXXXXX.XX.azuredatabricks.net
DATABRICKS_TOKEN=dapiXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
DATABRICKS_SQL_WAREHOUSE_ID=XXXXXXXXXXXXXXXX

# Credenciais do Microsoft Fabric (via Azure Service Principal )
AZURE_TENANT_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
AZURE_CLIENT_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
AZURE_CLIENT_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
FABRIC_WORKSPACE_ID=XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX

# Configurações do sistema
MAX_BUDGET_USD=5.0
MAX_TURNS=50
LOG_LEVEL=INFO
```

### 12.2. Scripts de Verificação

Antes de usar o sistema em um ambiente novo, é recomendado rodar os scripts de health check:

**Para Databricks:**

```bash
python tools/databricks_health_check.py
```

Este script testa: autenticação, informações do workspace, lista de SQL Warehouses disponíveis e catálogos do Unity Catalog.

**Para Microsoft Fabric:**

```bash
python tools/fabric_health_check.py
```

Este script testa: geração de token Entra ID e conectividade real com a API do Fabric (lista os workspaces acessíveis).

---

## 13. Qualidade de Código e Testes

O projeto possui uma estrutura robusta de garantia de qualidade, com múltiplas camadas de verificação.

### 13.1. Ferramentas de Qualidade

| Ferramenta           | O que faz                                                                        | Comando                         |
| -------------------- | -------------------------------------------------------------------------------- | ------------------------------- |
| **Ruff**       | Linter e formatador de código Python (substitui flake8, black e isort)          | `make lint` / `make format` |
| **Mypy**       | Verificador de tipos estáticos (garante que as variáveis são do tipo correto) | `make type-check`             |
| **Bandit**     | Scanner de segurança (detecta vulnerabilidades comuns no código Python)        | `make security`               |
| **Pre-commit** | Roda todas as verificações automaticamente antes de cada `git commit`        | `pre-commit install`          |

### 13.2. Testes Automatizados

A pasta `tests/` contém 7 arquivos de testes que cobrem os principais componentes:

| Arquivo de Teste           | O que testa                                                                            |
| -------------------------- | -------------------------------------------------------------------------------------- |
| `test_agents.py`         | Verifica se as definições dos agentes estão corretas (modelo, ferramentas, prompts) |
| `test_commands.py`       | Testa o parser de slash commands com 15 casos diferentes                               |
| `test_exceptions.py`     | Verifica a hierarquia de exceções com 10 casos                                       |
| `test_hooks.py`          | Testa os bloqueios de segurança e o registro de auditoria                             |
| `test_mcp_configs.py`    | Verifica se as configurações dos servidores MCP estão corretas                      |
| `test_mlflow_wrapper.py` | Testa o wrapper MLflow com 9 casos                                                     |
| `test_settings.py`       | Valida a leitura e validação das configurações com 10 casos                        |

O projeto exige uma **cobertura mínima de 80%** dos testes. Isso significa que pelo menos 80% do código deve ser executado durante os testes. Para rodar todos os testes:

```bash
make test
# ou
pytest tests/ -v --tb=short --cov=agents --cov=config --cov=hooks --cov=commands
```

---

## 14. Deploy e CI/CD (Publicação Automática)

### 14.1. `databricks.yml` — Databricks Asset Bundles

Este arquivo configura o deploy do projeto no Databricks usando a tecnologia **Asset Bundles (DABs)**. Ele define três ambientes:

- **Dev (Desenvolvimento):** Ambiente padrão para testes locais.
- **Staging (Homologação):** Ambiente intermediário para validação antes da produção. Fica em `/Shared/data-agents-staging`.
- **Production (Produção):** Ambiente final. Fica em `/Shared/data-agents-prod` e usa um Service Principal dedicado para maior segurança.

Para fazer o deploy:

```bash
make deploy-staging    # Publica no ambiente de homologação
make deploy-prod       # Publica no ambiente de produção
```

### 14.2. GitHub Actions (`.github/workflows/`)

O projeto possui dois workflows automatizados que rodam no GitHub:

**CI (Integração Contínua):** Roda em todo `push` para as branches `main` e `develop`. Executa em sequência: verificação de qualidade de código (Ruff, Mypy), testes automatizados com cobertura e scan de segurança (Bandit). Se qualquer etapa falhar, o merge é bloqueado.

**CD (Entrega Contínua):** Roda automaticamente quando uma tag de versão (ex: `v1.2.0`) é criada no GitHub. Faz o deploy no ambiente de produção via `databricks bundle deploy` e sincroniza os arquivos de Skills para o workspace do Databricks.

---

## 15. Como Começar a Usar

Esta seção apresenta o passo a passo completo para um profissional Junior colocar o projeto para funcionar do zero.

**Pré-requisitos:**

- Python 3.11 ou superior instalado.
- .NET SDK 8.0 ou superior (para o servidor MCP do Fabric).
- Uma conta na Anthropic com créditos disponíveis.
- Acesso a um workspace Databricks ou Microsoft Fabric (pelo menos um dos dois).

**Passo 1: Clonar o repositório**

```bash
git clone https://github.com/ThomazRossito/data-agents.git
cd data-agents
```

**Passo 2: Criar o ambiente virtual Python**

```bash
python3 -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
```

**Passo 3: Instalar as dependências**

```bash
pip install -e "."          # Apenas produção
pip install -e ".[dev]"     # Produção + ferramentas de desenvolvimento
```

**Passo 4: Configurar as credenciais**

```bash
cp .env.example .env
# Abra o arquivo .env em um editor de texto e preencha com suas credenciais reais
```

**Passo 5: Verificar as conexões**

```bash
python tools/databricks_health_check.py   # Se usar Databricks
python tools/fabric_health_check.py       # Se usar Fabric
```

**Passo 6: Iniciar o sistema**

```bash
python main.py
# ou
data-agents
```

**Passo 7: Fazer sua primeira pergunta**

```
/health
```

Este comando verifica se tudo está funcionando. Se retornar "OK" para as plataformas configuradas, você está pronto para usar!

---

## 16. Conclusão

O projeto **Data Agents** representa uma abordagem madura e corporativa para o uso de IA em Engenharia de Dados. Ele resolve os principais problemas que surgem quando se tenta usar IAs generativas em ambientes de produção:

**O problema da alucinação** é resolvido pelo Hub de Skills: a IA não inventa padrões, ela os lê de manuais verificados antes de agir.

**O problema da segurança** é resolvido pelos Hooks: nenhum comando destrutivo pode ser executado, e tudo é registrado em logs de auditoria.

**O problema do custo** é resolvido pelo Cost Guard: o sistema monitora e alerta sobre operações caras, com um limite máximo configurável por sessão.

**O problema da especialização** é resolvido pela arquitetura multi-agente: cada agente tem um papel bem definido, com permissões adequadas ao seu nível de responsabilidade.

Para um profissional Junior, este projeto é um excelente estudo de caso de como construir sistemas de IA responsáveis e prontos para o ambiente corporativo, combinando as melhores práticas de Engenharia de Software (testes, CI/CD, linting ) com as melhores práticas de Engenharia de Dados (Arquitetura Medalhão, Star Schema, Liquid Clustering).
