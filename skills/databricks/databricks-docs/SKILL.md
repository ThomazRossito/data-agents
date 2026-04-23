---
name: databricks-docs
description: "Databricks documentation reference via llms.txt index. Use when other skills do not cover a topic, looking up unfamiliar Databricks features, or needing authoritative docs on APIs, configurations, or platform capabilities."
updated_at: 2026-04-23
source: web_search
---

# Databricks Documentation Reference

This skill provides access to the complete Databricks documentation index via llms.txt - use it as a **reference resource** to supplement other skills and inform your use of MCP tools.

## Role of This Skill

This is a **reference skill**, not an action skill. Use it to:

- Look up documentation when other skills don't cover a topic
- Get authoritative guidance on Databricks concepts and APIs
- Find detailed information to inform how you use MCP tools
- Discover features and capabilities you may not know about

**Always prefer using MCP tools for actions** (execute_sql, manage_pipeline, etc.) and **load specific skills for workflows** (databricks-python-sdk, databricks-spark-declarative-pipelines, etc.). Use this skill when you need reference documentation.

## How to Use

Fetch the llms.txt documentation index:

**URL:** `https://docs.databricks.com/llms.txt`

Use WebFetch to retrieve this index, then:

1. Search for relevant sections/links
2. Fetch specific documentation pages for detailed guidance
3. Apply what you learn using the appropriate MCP tools

> **Nota (março/2026):** O site de documentação passou a usar uma navegação em abas (*usage guides*, *getting started*, *developer tools and partners*, *reference*, *resources*, *release notes*). Ao navegar manualmente em `docs.databricks.com`, use essas abas para localizar seções mais rapidamente.

## Documentation Structure

The llms.txt file is organized by category:

- **Overview & Getting Started** - Basic concepts, free trial, free edition, tutorials
- **Data Engineering** - Lakeflow Spark Declarative Pipelines (antigo DLT), Lakeflow Jobs (antigo Databricks Jobs), Lakeflow Connect, Spark, Delta Lake, Auto Loader
- **SQL & Analytics** - Warehouses, queries, dashboards, SQL functions, SQL data types
- **AI/ML** - MLflow 3, Mosaic AI Model Serving, Foundation Model APIs, Agent Framework, Vector Search, AI Gateway, GenAI evaluation
- **Governance** - Unity Catalog, permissions, security, ABAC (attribute-based access control), governed tags
- **Developer Tools** - SDKs (Python, Java, Go), CLI, REST API, Terraform, GitHub Actions

> ⚠️ **Renomeações de produto — atenção ao buscar nas docs:**
> - **DLT** → **Lakeflow Spark Declarative Pipelines** (renomeação concluída; documentação antiga sob "DLT" redireciona para o novo nome)
> - **Databricks Jobs** → **Lakeflow Jobs** (sem migração necessária)
> - **Databricks Assistant** → **Genie Code** (GA desde março/2026, com modo Agent para tarefas autônomas multi-step)
> - **Shared access mode** → **Standard access mode** (clusters)

## Platform Context — Mudanças Importantes (2025–2026)

Mantenha estes pontos em mente ao interpretar qualquer documentação buscada:

- **Unity Catalog é obrigatório para contas novas:** Contas criadas após dezembro de 2025 não têm acesso a DBFS root, Hive Metastore nem compute sem isolamento. Toda documentação que ainda mencione Hive Metastore reflete um modo legado.
- **MLflow 3.0 GA (junho/2025):** Versão atual é 3.x (chegou a 3.11+ em 2026). Introduz `LoggedModel` como entidade de primeiro nível, tracing nativo para 20+ frameworks GenAI, Prompt Registry com Unity Catalog, e deployment jobs integrados com Lakeflow Jobs. A migração de MLflow 2.x requer mudanças mínimas de código.
- **Lakeflow Spark Declarative Pipelines — modo de publicação padrão GA:** O `LIVE` virtual schema é legado. Pipelines novos publicam em múltiplos catálogos/schemas; `LIVE schema` só aparece em pipelines criados antes de fevereiro/2025.
- **AUTO CDC recomendado sobre APPLY CHANGES INTO:** A Databricks recomenda substituir `APPLY CHANGES INTO` pela API `AUTO CDC` em novos designs de pipelines CDC.
- **`ai_parse_document` GA (abril/2026):** Função SQL para extrair conteúdo estruturado de PDFs, imagens, Word e PowerPoint. Complementada por `ai_prep_search` (Beta) para chunking RAG-ready.
- **Mosaic AI Gateway GA (junho/2025):** Centralized governance, rate limiting, payload logging e traffic routing para model serving endpoints.
- **PATs com prazo máximo de 730 dias:** Personal access tokens agora têm limite de 2 anos. Prefira OAuth para maior segurança (recomendação oficial).

## Example: Complementing Other Skills

**Scenario:** User wants to create a Lakeflow Spark Declarative Pipeline (antigo DLT)

1. Load `databricks-spark-declarative-pipelines` skill for workflow patterns
2. Use this skill to fetch docs if you need clarification on specific pipeline features (e.g., queued execution mode, multi-catalog publishing, AUTO CDC)
3. Use `manage_pipeline(action="create_or_update")` MCP tool to actually create the pipeline

**Scenario:** User asks about an unfamiliar Databricks feature

1. Fetch llms.txt to find relevant documentation
2. Read the specific docs to understand the feature
3. Determine which skill/tools apply, then use them

**Scenario:** User needs GenAI evaluation with MLflow

1. Load `databricks-mlflow-evaluation` skill (cobre MLflow 3 GenAI workflows)
2. Use this skill para buscar detalhes de tracing, Prompt Registry ou LLM judges
3. Executar avaliações via Lakeflow Jobs + Unity Catalog governance

## Related Skills

- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** - SDK patterns for programmatic Databricks access
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Lakeflow Spark Declarative Pipelines (antigo DLT) workflows
- **[databricks-unity-catalog](../databricks-unity-catalog/SKILL.md)** - Governance and catalog management
- **[databricks-model-serving](../databricks-model-serving/SKILL.md)** - Mosaic AI Model Serving endpoints and model deployment
- **[databricks-mlflow-evaluation](../databricks-mlflow-evaluation/SKILL.md)** - MLflow 3 GenAI evaluation, tracing e Prompt Registry workflows
