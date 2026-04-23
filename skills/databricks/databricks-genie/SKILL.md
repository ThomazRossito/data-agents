---
name: databricks-genie
description: "Create and query Databricks Genie Spaces for natural language SQL exploration. Use when building Genie Spaces, exporting and importing Genie Spaces, migrating Genie Spaces between workspaces or environments, or asking questions via the Genie Conversation API."
updated_at: 2026-04-23
source: web_search
---

# Databricks Genie

Create, manage, and query Databricks Genie Spaces - natural language interfaces for SQL-based data exploration.

## Overview

Genie Spaces allow users to ask natural language questions about structured data in Unity Catalog. The system translates questions into SQL queries, executes them on a SQL warehouse, and presents results conversationally.

A Genie space is based on data registered to Unity Catalog, including managed tables, external tables, foreign tables, views, **metric views**, and materialized views. Genie uses the metadata attached to Unity Catalog objects, as well as an author-curated space-level knowledge store, to generate responses.

> ℹ️ **Genie Conversation API — Generally Available (2026):** The Genie Conversation API is now generally available. Use the API to programmatically start conversations, send questions, and retrieve results from Genie spaces.

## When to Use This Skill

Use this skill when:
- Creating a new Genie Space for data exploration
- Adding sample questions to guide users
- Connecting Unity Catalog tables (or metric views) to a conversational interface
- Asking questions to a Genie Space programmatically (Conversation API)
- Exporting a Genie Space configuration (serialized_space) for backup or migration
- Importing / cloning a Genie Space from a serialized payload
- Migrating a Genie Space between workspaces or environments (dev → staging → prod)
    - Only supports catalog remapping where catalog names differ across environments
    - Not supported for schema and/or table names that differ across environments
    - Not including migration of tables between environments (only migration of Genie Spaces)

## MCP Tools

| Tool | Purpose |
|------|---------|
| `manage_genie` | Create, get, list, delete, export, and import Genie Spaces |
| `ask_genie` | Ask natural language questions to a Genie Space |
| `get_table_stats_and_schema` | Inspect table schemas before creating a space |
| `execute_sql` | Test SQL queries directly |

### manage_genie - Space Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Idempotent create/update a space | display_name, table_identifiers (or serialized_space) |
| `get` | Get space details | space_id |
| `list` | List all spaces | (none) |
| `delete` | Delete a space | space_id |
| `export` | Export space config for migration/backup | space_id |
| `import` | Import space from serialized config | warehouse_id, serialized_space |

**Example tool calls:**
```
# MCP Tool: manage_genie
# Create a new space
manage_genie(
    action="create_or_update",
    display_name="Sales Analytics",
    table_identifiers=["catalog.schema.customers", "catalog.schema.orders"],
    description="Explore sales data with natural language",
    sample_questions=["What were total sales last month?"]
)

# MCP Tool: manage_genie
# Get space details with full config
manage_genie(action="get", space_id="space_123", include_serialized_space=True)

# MCP Tool: manage_genie
# List all spaces
manage_genie(action="list")

# MCP Tool: manage_genie
# Export for migration
exported = manage_genie(action="export", space_id="space_123")

# MCP Tool: manage_genie
# Import to new workspace
manage_genie(
    action="import",
    warehouse_id="warehouse_456",
    serialized_space=exported["serialized_space"],
    title="Sales Analytics (Prod)"
)
```

### ask_genie - Conversation API (Query)

Ask natural language questions to a Genie Space. Pass `conversation_id` for follow-up questions.

```
# MCP Tool: ask_genie
# Start a new conversation
result = ask_genie(
    space_id="space_123",
    question="What were total sales last month?"
)
# Returns: {question, conversation_id, message_id, status, sql, columns, data, row_count}

# MCP Tool: ask_genie
# Follow-up question in same conversation
result = ask_genie(
    space_id="space_123",
    question="Break that down by region",
    conversation_id=result["conversation_id"]
)
```

> **API response note:** The Genie Conversation API returns tabular query results as structured data. It does not return rendered charts or visualizations. To display charts, retrieve the query results from the `attachment_id` and render them in your application using a charting library of your choice.

> **Reasoning traces (Public Preview):** To access Genie's reasoning traces, check the `attachments` field for a `query_attachments` object of type `GenieQueryAttachments`. When present, it contains the step-by-step reasoning Genie used to generate the response.

> **Throughput:** Throughput rates for the Genie conversation API free tier are best-effort and depend on system capacity. To mitigate misuse and prevent abuse during peak usage periods, the system processes requests based on available capacity. Under normal or low-traffic conditions, the API supports up to five questions per minute per workspace. If you're seeking higher throughput support, contact your Databricks account team.

## Quick Start

### 1. Inspect Your Tables

Before creating a Genie Space, understand your data:

```
# MCP Tool: get_table_stats_and_schema
get_table_stats_and_schema(
    catalog="my_catalog",
    schema="sales",
    table_stat_level="SIMPLE"
)
```

### 2. Create the Genie Space

Table identifiers must use three-level namespace format (`catalog.schema.table`).

```
# MCP Tool: manage_genie
manage_genie(
    action="create_or_update",
    display_name="Sales Analytics",
    table_identifiers=[
        "my_catalog.sales.customers",
        "my_catalog.sales.orders"
    ],
    description="Explore sales data with natural language",
    sample_questions=[
        "What were total sales last month?",
        "Who are our top 10 customers?"
    ]
)
```

### 3. Ask Questions (Conversation API)

```
# MCP Tool: ask_genie
ask_genie(
    space_id="your_space_id",
    question="What were total sales last month?"
)
# Returns: SQL, columns, data, row_count
```

### 4. Export & Import (Clone / Migrate)

Export a space (preserves all tables, instructions, SQL examples, and layout):

```
# MCP Tool: manage_genie
exported = manage_genie(action="export", space_id="your_space_id")
# exported["serialized_space"] contains the full config
```

Clone to a new space (same catalog):

```
# MCP Tool: manage_genie
manage_genie(
    action="import",
    warehouse_id=exported["warehouse_id"],
    serialized_space=exported["serialized_space"],
    title=exported["title"],  # override title; omit to keep original
    description=exported["description"],
)
```

> **Cross-workspace migration:** Each MCP server is workspace-scoped. Configure one server entry per workspace profile in your IDE's MCP config, then `manage_genie(action="export")` from the source server and `manage_genie(action="import")` via the target server. See [spaces.md §Migration](spaces.md#migrating-across-workspaces-with-catalog-remapping) for the full workflow.

## New & Noteworthy Features (2025–2026)

### Agent Mode (Public Preview)

Agent mode extends Genie's capabilities to answer both straightforward data questions and complex business questions. It uses multi-step reasoning and hypothesis testing to uncover deeper insights.

When you ask a question, Agent mode creates and refines a research plan, running multiple SQL queries, learning from each result, and iterating until it has enough evidence to provide a comprehensive answer.

Key behaviours:
- Delivers comprehensive reports with detailed summaries, citations, visualizations, and supporting tables.
- You can export Agent mode reports as PDF files for sharing or offline review. After Agent mode completes a report, click **Download PDF** at the bottom right of the report.
- Agent mode is now the default conversation setting in Genie spaces when the Public Preview feature is enabled.
- During the Public Preview period, users can only submit Agent mode prompts through the Databricks UI — the API is not yet supported for Agent mode.

To enable: workspace admins can control access to Genie Agent mode (Public Preview) using the Previews page.

### Inspect (Public Preview)

Inspect is now in Public Preview. Inspect automatically improves standard Genie's accuracy by reviewing the initially generated SQL, authoring smaller SQL statements to verify specific aspects of the query, and generating improved SQL as needed.

Use Inspect when you want additional confidence in query accuracy, especially for complex queries involving filters, date ranges, or multiple tables.

### Unity Catalog Metric Views as Data Sources

Users can now add tables and metric views to a space and analyze them together.

Metric views are particularly effective for Genie spaces because they pre-define metrics, dimensions, and aggregations. This approach helps you stay within the limit, simplifies your data model, and can improve Genie's response accuracy.

> **Table limit:** Genie spaces support up to 30 tables or views. If your data topic requires more than 30 tables, pre-join related tables into views or metric views before adding them to your space.

> **SQL snippets/JOIN limit increased (2025):** The limit for SQL snippets and JOIN relationships in a Genie space has been increased to 200.

### Genie Space Embedding (Beta)

You can now embed a Genie space as an iframe in a website or application.

Genie space authors can generate iframe embed code from the Share dialog. Users who have access to the embedding application can send prompts and view results without editing the space configuration.

> Workspace admins must define the allowed embed destinations before authors can share a Genie space this way. See Embed a Genie space in the Databricks docs.

### New Genie API Endpoints

The following endpoints were added in 2025 and are available in Public Preview or Beta:

- Use the Genie API to list all conversations in a space, delete conversations, and delete Genie spaces.
- A new **List Spaces** Genie API endpoint retrieves all spaces the requestor has access to, including the Genie space title, description, and ID.
- The **run benchmarks** and **retrieve benchmark results** APIs are now in Beta.
- The following Genie API endpoints moved from Beta to Public Preview: list conversation messages, delete conversation message, and send thumbs up/down feedback.

### Sharing & Collaboration

- The Share modal now includes an option to share your Genie space with all account users.
- You can now share individual Genie conversations and control who can view them (Beta).
- Authors can now add descriptions to Genie spaces embedded in dashboards.

### Customer-Managed Keys

Genie spaces created after April 10, 2025 are now encrypted and compatible with customer-managed keys.

## Best Practices for Space Quality

A well-structured Genie space uses well-annotated data: Genie relies on table metadata and column comments. Verify that your Unity Catalog data sources have clear, descriptive comments.

Aim for at least five tested example SQL queries. Use benchmarks to test accuracy: add at least five benchmark questions based on anticipated user questions.

Prioritize SQL expressions and example SQL over text instructions. Use SQL expressions to define business semantics like metrics and filters. Use example SQL to teach Genie how to handle common ambiguous prompts. Use text instructions only as a last resort when SQL expressions and examples cannot address the need — structured definitions through SQL are more reliable and maintainable than plain text guidance.

## Reference Files

- [spaces.md](spaces.md) - Creating and managing Genie Spaces
- [conversation.md](conversation.md) - Asking questions via the Conversation API

## Prerequisites

Before creating a Genie Space:

1. **Tables in Unity Catalog** - Bronze/silver/gold tables with the data (managed tables, external tables, views, metric views, or materialized views)
2. **SQL Warehouse** - A Pro or Serverless SQL warehouse to execute queries (auto-detected if not specified)

### Creating Tables

Use these skills in sequence:
1. `databricks-synthetic-data-gen` - Generate raw parquet files
2. `databricks-spark-declarative-pipelines` - Create bronze/silver/gold tables

## Common Issues

See [spaces.md §Troubleshooting](spaces.md#troubleshooting) for a full list of issues and solutions.

## Related Skills

- **[databricks-agent-bricks](../databricks-agent-bricks/SKILL.md)** - Use Genie Spaces as agents inside Supervisor Agents
- **[databricks-synthetic-data-gen](../databricks-synthetic-data-gen/SKILL.md)** - Generate raw parquet data to populate tables for Genie
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Build bronze/silver/gold tables consumed by Genie Spaces
- **[databricks-unity-catalog](../databricks-unity-catalog/SKILL.md)** - Manage the catalogs, schemas, and tables Genie queries
