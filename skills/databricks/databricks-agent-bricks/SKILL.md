---
name: databricks-agent-bricks
description: "Create and manage Databricks Agent Bricks: Knowledge Assistants (KA) for document Q&A, Genie Spaces for SQL exploration, and Supervisor Agents for multi-agent orchestration. Use when building conversational AI applications on Databricks."
updated_at: 2026-04-23
source: web_search
---

# Agent Bricks

Create and manage Databricks Agent Bricks - pre-built AI components for building conversational applications.

> ⚠️ **Breaking change (2026-Q1): "Multi-Agent Supervisor (MAS)" renomeado para "Supervisor Agent".**
> O nome antigo `Multi-Agent Supervisor` e a sigla `MAS` foram descontinuados nas release notes oficiais.
> Use apenas `Supervisor Agent` em nomes de recursos, documentação e chamadas de MCP tool.
> A tool `manage_mas` mantém compatibilidade no MCP server interno do projeto — **atualize os prompts e exemplos** que referenciem "MAS" para evitar confusão com a nomenclatura atual da Databricks.

## Overview

Agent Bricks são componentes pré-construídos e gerenciados da Databricks para aplicações de IA conversacional:

| Brick | Purpose | Data Source | Status |
|-------|---------|-------------|--------|
| **Knowledge Assistant (KA)** | Document-based Q&A usando RAG com citações | PDF/text files em Volumes | **GA** (jan/2026) |
| **Genie Space** | Natural language to SQL | Unity Catalog tables | GA |
| **Supervisor Agent** | Multi-agent orchestration (ex-MAS) | Endpoints, Genie Spaces, UC Functions, MCP | **GA** (fev/2026) |

> **Disponibilidade regional**: KA e Supervisor Agent têm disponibilidade regional limitada e vêm sendo expandidos progressivamente (Mumbai/ap-south-1 em março/2026). Consulte [Features with limited regional availability](https://docs.databricks.com/aws/en/resources/feature-region-support.html) para a lista atualizada. Regiões fora dos EUA podem exigir `cross-geo processing` habilitado.

> **Compliance workspaces**: KA disponível por padrão para workspaces com compliance security profile + HIPAA desde março/2026. Supervisor Agent idem, a partir de meados de março/2026.

## Prerequisites

Before creating Agent Bricks, ensure you have the required data:

### For Knowledge Assistants
- **Documents in a Volume**: PDF, text, ou outros arquivos armazenados em um Unity Catalog Volume
- Gere documentos sintéticos com a skill `databricks-unstructured-pdf-generation` se necessário
- KA usa **Instructed Retrieval** (superior ao RAG tradicional): prioriza e combina fontes diversas automaticamente

### For Genie Spaces
- **Veja a skill `databricks-genie`** para guia completo de Genie Spaces
- Tables in Unity Catalog com os dados a explorar
- Gere dados brutos com a skill `databricks-synthetic-data-gen`
- Crie tabelas com a skill `databricks-spark-declarative-pipelines`

### For Supervisor Agents
- **Model Serving Endpoints**: Endpoints de agentes implantados (KA endpoints, agentes customizados, modelos fine-tuned)
- **Genie Spaces**: Espaços Genie existentes podem ser usados diretamente como agentes para consultas SQL
- **Long-running tasks**: Supervisor Agent agora suporta tarefas de longa duração (feature lançada em fev/2026)
- Combine endpoints, Genie Spaces, UC Functions e MCP servers no mesmo Supervisor Agent

> ⚠️ **Breaking change (set/2025 — permissões de endpoint):**
> Para agent endpoints criados **antes de 16 de setembro de 2025**, a permissão `CAN QUERY` deve ser concedida manualmente na página "Serving endpoints". Endpoints mais novos gerenciam isso automaticamente pelo Supervisor Agent.
> End users precisam de permissão explícita em **cada subagente**: `CAN QUERY` para endpoints, acesso ao Genie Space + objetos UC subjacentes para Genie, e `EXECUTE` para UC Functions.

### For Unity Catalog Functions
- **Existing UC Function**: Função já registrada no Unity Catalog
- Service principal do agente deve ter privilégio `EXECUTE` na função

### For External MCP Servers
- **Existing UC HTTP Connection**: Connection configurada com `is_mcp_connection: 'true'`
- Service principal do agente deve ter privilégio `USE CONNECTION` na connection
- **OAuth gerenciado (novo em mar/2026)**: Para Glean MCP, GitHub MCP, Google Drive API e SharePoint API, a Databricks fornece fluxos OAuth gerenciados — não é necessário registrar app OAuth próprio nem gerenciar credenciais manualmente. Veja "Install an external MCP server" na documentação oficial.
- Autenticação suportada: bearer token ou OAuth Machine-to-Machine (M2M)

## MCP Tools

### Knowledge Assistant Tool

**manage_ka** - Manage Knowledge Assistants (KA)
- `action`: "create_or_update", "get", "find_by_name", or "delete"
- `name`: Nome do KA (para create_or_update, find_by_name)
- `volume_path`: Caminho para documentos (ex: `/Volumes/catalog/schema/volume/folder`) (para create_or_update)
- `description`: (opcional) O que o KA faz (para create_or_update)
- `instructions`: (opcional) Como o KA deve responder (para create_or_update)
- `tile_id`: O tile ID do KA (para get, delete, ou update via create_or_update)
- `add_examples_from_volume`: (opcional, default: true) Auto-adiciona exemplos de arquivos JSON (para create_or_update)

Actions:
- **create_or_update**: Requer `name`, `volume_path`. Passe `tile_id` opcionalmente para atualizar.
- **get**: Requer `tile_id`. Retorna tile_id, name, description, endpoint_status, knowledge_sources, examples_count.
- **find_by_name**: Requer `name` (match exato). Retorna found, tile_id, name, endpoint_name, endpoint_status. Use para buscar um KA existente quando souber o nome mas não o tile_id.
- **delete**: Requer `tile_id`.

### Genie Space Tools

**Para guia completo de Genie, use a skill `databricks-genie`.**

Use `manage_genie` com actions:
- `create_or_update` - Criar ou atualizar um Genie Space
- `get` - Obter detalhes do Genie Space
- `list` - Listar todos os Genie Spaces
- `delete` - Deletar um Genie Space
- `export` / `import` - Para migração

Veja a skill `databricks-genie` para:
- Fluxo de inspeção de tabelas
- Boas práticas de perguntas de exemplo
- Curadoria (instruções, certified queries)

**IMPORTANTE**: Não existe system table para Genie spaces (ex: `system.ai.genie_spaces` não existe). Use `manage_genie(action="list")` para localizar spaces.

### Supervisor Agent Tool

> ⚠️ **Renomeação (2026-Q1):** O que era "Multi-Agent Supervisor (MAS)" é agora **Supervisor Agent** na nomenclatura oficial Databricks. A tool interna do projeto continua como `manage_mas` por compatibilidade — mas todos os exemplos, prompts e nomes de recursos devem referenciar "Supervisor Agent".

**manage_mas** - Manage Supervisor Agents (ex-MAS)
- `action`: "create_or_update", "get", "find_by_name", or "delete"
- `name`: Nome do Supervisor Agent (para create_or_update, find_by_name)
- `agents`: Lista de configurações de agentes (para create_or_update), cada um com:
  - `name`: Identificador do agente (obrigatório)
  - `description`: O que este agente trata — crítico para o roteamento (obrigatório)
  - `ka_tile_id`: Knowledge Assistant tile ID (use para agentes de Q&A sobre documentos — recomendado para KAs)
  - `genie_space_id`: Genie space ID (use para agentes de dados SQL)
  - `endpoint_name`: Nome do endpoint de model serving (para agentes customizados)
  - `uc_function_name`: Nome da UC function no formato `catalog.schema.function_name`
  - `connection_name`: Nome da UC connection (para MCP servers externos)
  - Nota: Forneça exatamente um de: `ka_tile_id`, `genie_space_id`, `endpoint_name`, `uc_function_name`, ou `connection_name`
- `description`: (opcional) O que o Supervisor Agent faz (para create_or_update)
- `instructions`: (opcional) Instruções de roteamento para o supervisor (para create_or_update)
- `tile_id`: O tile ID do Supervisor Agent (para get, delete, ou update via create_or_update)
- `examples`: (opcional) Lista de perguntas de exemplo com campos `question` e `guideline` (para create_or_update)

Actions:
- **create_or_update**: Requer `name`, `agents`. Passe `tile_id` opcionalmente para atualizar.
- **get**: Requer `tile_id`. Retorna tile_id, name, description, endpoint_status, agents, examples_count.
- **find_by_name**: Requer `name` (match exato). Retorna found, tile_id, name, endpoint_status, agents_count. Use para buscar um Supervisor Agent existente quando souber o nome mas não o tile_id.
- **delete**: Requer `tile_id`.

## Typical Workflow

### 1. Generate Source Data

Antes de criar Agent Bricks, gere os dados de origem:

**Para KA (document Q&A)**:
```
1. Use a skill `databricks-unstructured-pdf-generation` para gerar PDFs
2. PDFs são salvos em um Volume com arquivos JSON companion (pares question/guideline)
```

**Para Genie (SQL exploration)**:
```
1. Use a skill `databricks-synthetic-data-gen` para criar dados raw em parquet
2. Use a skill `databricks-spark-declarative-pipelines` para criar tabelas bronze/silver/gold
```

### 2. Create the Agent Brick

Use `manage_ka(action="create_or_update", ...)` ou `manage_mas(action="create_or_update", ...)` com suas fontes de dados.

### 3. Wait for Provisioning

KA e Supervisor Agent recém criados precisam de tempo para provisionar. O endpoint status evolui:
- `PROVISIONING` - Sendo criado (pode levar 2-5 minutos)
- `ONLINE` - Pronto para uso
- `OFFLINE` - Não em execução

### 4. Add Examples (Automatic)

Para KA, se `add_examples_from_volume=true`, os exemplos são extraídos automaticamente dos arquivos JSON no volume e adicionados quando o endpoint estiver `ONLINE`.

## Best Practices

1. **Use nomes significativos**: Nomes são sanitizados automaticamente (espaços viram underscores)
2. **Forneça descriptions**: Ajuda usuários a entender o que o brick faz; é crítico para roteamento no Supervisor Agent
3. **Adicione instructions**: Guie o comportamento e o tom da IA
4. **Inclua perguntas de exemplo**: Mostra aos usuários como interagir com o brick
5. **Siga o workflow**: Gere dados primeiro, depois crie o brick
6. **Gerencie permissões explicitamente**: Após criar um Supervisor Agent, garanta que cada subagente tenha as permissões corretas concedidas aos end users (especialmente endpoints criados antes de set/2025)
7. **Prefira OAuth gerenciado para MCP**: Para Glean, GitHub, Google Drive e SharePoint, use o OAuth gerenciado da Databricks em vez de credenciais manuais

## Example: Multi-Modal Supervisor Agent

```python
# ATENÇÃO: "Supervisor Agent" é o nome oficial atual (ex-"Multi-Agent Supervisor/MAS")
manage_mas(
    action="create_or_update",
    name="Enterprise Support Supervisor",
    agents=[
        {
            "name": "knowledge_base",
            "ka_tile_id": "f32c5f73-466b-...",
            "description": "Answers questions about company policies, procedures, and documentation from indexed files"
        },
        {
            "name": "analytics_engine",
            "genie_space_id": "01abc123...",
            "description": "Runs SQL analytics on usage metrics, performance stats, and operational data"
        },
        {
            "name": "ml_classifier",
            "endpoint_name": "custom-classification-endpoint",
            "description": "Classifies support tickets and predicts resolution time using custom ML model"
        },
        {
            "name": "data_enrichment",
            "uc_function_name": "support.utils.enrich_ticket_data",
            "description": "Enriches support ticket data with customer history and context"
        },
        {
            "name": "ticket_operations",
            "connection_name": "ticket_system_mcp",
            "description": "Creates, updates, assigns, and closes support tickets in external ticketing system"
        }
    ],
    description="Comprehensive enterprise support agent with knowledge retrieval, analytics, ML, data enrichment, and ticketing operations",
    instructions="""
    Route queries as follows:
    1. Policy/procedure questions → knowledge_base
    2. Data analysis requests → analytics_engine
    3. Ticket classification → ml_classifier
    4. Customer context lookups → data_enrichment
    5. Ticket creation/updates → ticket_operations

    If a query spans multiple domains, chain agents:
    - First gather information (analytics_engine or knowledge_base)
    - Then take action (ticket_operations)
    """
)
```

## Related Skills

- **[databricks-genie](../databricks-genie/SKILL.md)** - Guia completo de criação, curadoria e Conversation API de Genie Spaces
- **[databricks-unstructured-pdf-generation](../databricks-unstructured-pdf-generation/SKILL.md)** - Gerar PDFs sintéticos para alimentar Knowledge Assistants
- **[databricks-synthetic-data-gen](../databricks-synthetic-data-gen/SKILL.md)** - Criar dados brutos para tabelas de Genie Spaces
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Construir tabelas bronze/silver/gold consumidas por Genie Spaces
- **[databricks-model-serving](../databricks-model-serving/SKILL.md)** - Implantar endpoints de agentes customizados usados como subagentes
- **[databricks-vector-search](../databricks-vector-search/SKILL.md)** - Construir índices vetoriais para aplicações RAG pareadas com KAs

## See Also

- `1-knowledge-assistants.md` - Padrões e exemplos detalhados de KA
- `databricks-genie` skill - Padrões, curadoria e exemplos detalhados de Genie
- `2-supervisor-agents.md` - Padrões e exemplos detalhados de Supervisor Agent (ex-MAS)

## Changelog

| Data | Mudança |
|------|---------|
| 2026-04 | Atualização desta SKILL: renomeação MAS→Supervisor Agent, status GA de KA e Supervisor Agent, OAuth gerenciado para MCP (Glean/GitHub/Google Drive/SharePoint), long-running tasks, permissões de endpoint (set/2025), expansão regional |
| 2026-03 | KA e Supervisor Agent disponíveis em Mumbai (ap-south-1); KA GA em workspaces HIPAA/compliance |
| 2026-02 | Supervisor Agent GA; suporte a long-running tasks |
| 2026-01 | Knowledge Assistant GA em regiões US selecionadas |
