---
name: databricks-metric-views
description: "Unity Catalog metric views: define, create, query, and manage governed business metrics in YAML. Use when building standardized KPIs, revenue metrics, order analytics, or any reusable business metrics that need consistent definitions across teams and tools."
updated_at: 2026-04-23
source: web_search
---

# Unity Catalog Metric Views

> ⚠️ **Breaking change em DBR 17.3 / DBSQL 2025.30:** Semantic metadata (`display_name`, `format`, `synonyms`) requer **DBR 17.3+** (não apenas 17.2). Snowflake-schema joins requerem **DBR 17.1+**. O prerequisito mínimo para criar/consultar metric views continua sendo **DBR 16.4+** (DBSQL preview channel 2025.16). Inline YAML comments (`#`) são **removidos automaticamente** ao salvar com versão 1.1 via UI — preserve-os usando `ALTER VIEW` em notebook.

Define reusable, governed business metrics in YAML that separate measure definitions from dimension groupings for flexible querying.

## When to Use

Use this skill when:
- Defining **standardized business metrics** (revenue, order counts, conversion rates)
- Building **KPI layers** shared across dashboards, Genie, and SQL queries
- Creating metrics with **complex aggregations** (ratios, distinct counts, filtered measures)
- Defining **window measures** (moving averages, running totals, period-over-period, YTD)
- Modeling **star or snowflake schemas** with joins in metric definitions
- Enabling **materialization** for pre-computed metric aggregations
- Adding **semantic metadata** (display names, formats, synonyms) for AI/BI Genie and dashboards
- Building **composed metrics** that reuse simpler measures via `MEASURE()`

## Prerequisites

- **DBR 16.4+** (minimum para criar/consultar metric views; DBSQL preview channel 2025.16)
- **DBR 17.1+** para snowflake-schema joins (joins aninhados multi-hop)
- **DBR 17.3+** para semantic metadata (`display_name`, `format`, `synonyms`) e `DESCRIBE TABLE` com coluna `metadata`
- SQL warehouse com `CAN USE` permissions
- `SELECT` nas tabelas-fonte, `CREATE TABLE` + `USE SCHEMA` no schema-alvo
- `USE CATALOG` no catálogo-pai

## Quick Start

### Inspect Source Table Schema

Before creating a metric view, call `get_table_stats_and_schema` to understand available columns for dimensions and measures:

```
get_table_stats_and_schema(
    catalog="catalog",
    schema="schema",
    table_names=["orders"],
    table_stat_level="SIMPLE"  # Use "DETAILED" for cardinality, min/max, histograms
)
```

### Create a Metric View

```sql
CREATE OR REPLACE VIEW catalog.schema.orders_metrics
WITH METRICS
LANGUAGE YAML
AS $$
  version: 1.1
  comment: "Orders KPIs for sales analysis"
  source: catalog.schema.orders
  filter: order_date > '2020-01-01'
  dimensions:
    - name: Order Month
      expr: DATE_TRUNC('MONTH', order_date)
      comment: "Month of order"
    - name: Order Status
      expr: CASE
        WHEN status = 'O' THEN 'Open'
        WHEN status = 'P' THEN 'Processing'
        WHEN status = 'F' THEN 'Fulfilled'
        END
      comment: "Human-readable order status"
  measures:
    - name: Order Count
      expr: COUNT(1)
    - name: Total Revenue
      expr: SUM(total_price)
      comment: "Sum of total price"
    - name: Revenue per Customer
      expr: SUM(total_price) / COUNT(DISTINCT customer_id)
      comment: "Average revenue per unique customer"
$$
```

### Query a Metric View

All measures must use the `MEASURE()` function. `SELECT *` is NOT supported.

```sql
SELECT
  `Order Month`,
  `Order Status`,
  MEASURE(`Total Revenue`) AS total_revenue,
  MEASURE(`Order Count`) AS order_count
FROM catalog.schema.orders_metrics
WHERE extract(year FROM `Order Month`) = 2024
GROUP BY ALL
ORDER BY ALL
```

## Reference Files

| Topic | File | Description |
|-------|------|-------------|
| YAML Syntax | [yaml-reference.md](yaml-reference.md) | Complete YAML spec: dimensions, measures, joins, materialization |
| Patterns & Examples | [patterns.md](patterns.md) | Common patterns: star schema, snowflake, filtered measures, window measures, ratios |

## MCP Tools

Use the `manage_metric_views` tool for all metric view operations:

| Action | Description |
|--------|-------------|
| `create` | Create a metric view with dimensions and measures |
| `alter` | Update a metric view's YAML definition |
| `describe` | Get the full definition and metadata |
| `query` | Query measures grouped by dimensions |
| `drop` | Drop a metric view |
| `grant` | Grant SELECT privileges to users/groups |

### Create via MCP

```python
manage_metric_views(
    action="create",
    full_name="catalog.schema.orders_metrics",
    source="catalog.schema.orders",
    or_replace=True,
    comment="Orders KPIs for sales analysis",
    filter_expr="order_date > '2020-01-01'",
    dimensions=[
        {"name": "Order Month", "expr": "DATE_TRUNC('MONTH', order_date)", "comment": "Month of order"},
        {"name": "Order Status", "expr": "status"},
    ],
    measures=[
        {"name": "Order Count", "expr": "COUNT(1)"},
        {"name": "Total Revenue", "expr": "SUM(total_price)", "comment": "Sum of total price"},
    ],
)
```

### Query via MCP

```python
manage_metric_views(
    action="query",
    full_name="catalog.schema.orders_metrics",
    query_measures=["Total Revenue", "Order Count"],
    query_dimensions=["Order Month"],
    where="extract(year FROM `Order Month`) = 2024",
    order_by="ALL",
    limit=100,
)
```

### Describe via MCP

```python
manage_metric_views(
    action="describe",
    full_name="catalog.schema.orders_metrics",
)
```

### Grant Access

```python
manage_metric_views(
    action="grant",
    full_name="catalog.schema.orders_metrics",
    principal="data-consumers",
    privileges=["SELECT"],
)
```

## YAML Spec Quick Reference

```yaml
version: 1.1                    # Required: "1.1" para DBR 16.4+. Padrão atual.
comment: "Description"          # Optional: descrição da metric view
source: catalog.schema.table    # Required: tabela, view, outra metric view, ou SQL query inline
filter: column > value          # Optional: WHERE global aplicado a todas as queries

dimensions:                     # Required: pelo menos uma
  - name: Display Name          # Backtick-quoted em queries
    expr: sql_expression        # Referência a coluna ou transformação SQL
    comment: "Description"      # Optional (v1.1+)
    display_name: "Label"       # Optional (v1.1+, DBR 17.3+): label em ferramentas de BI
    synonyms:                   # Optional (v1.1+, DBR 17.3+): até 10, máx 255 chars cada
      - alternative name
    format:                     # Optional (v1.1+, DBR 17.3+): date, number, currency, etc.
      type: date
      date_format: year_month_day

measures:                       # Required: pelo menos uma
  - name: Display Name          # Queried via MEASURE(`name`)
    expr: AGG_FUNC(column)      # Deve ser expressão de agregação
    comment: "Description"      # Optional (v1.1+)
    display_name: "Label"       # Optional (v1.1+, DBR 17.3+)
    synonyms:                   # Optional (v1.1+, DBR 17.3+)
      - alternative name
    format:                     # Optional (v1.1+, DBR 17.3+): number, currency, percentage
      type: currency
      currency_code: USD

joins:                          # Optional: star/snowflake schema (DBR 17.1+ para snowflake)
  - name: dim_table
    source: catalog.schema.dim_table
    on: source.fk = dim_table.pk
    joins:                      # Nested joins para snowflake schema (DBR 17.1+)
      - name: sub_dim
        source: catalog.schema.sub_dim
        on: dim_table.fk = sub_dim.pk

materialization:                # Optional (experimental)
  schedule: every 6 hours
  mode: relaxed
```

### Source como SQL Query (novo)

O campo `source` aceita uma query SQL inline diretamente no YAML, além de nomes de tabelas:

```yaml
version: 1.1
source: >
  SELECT * FROM samples.tpch.orders o
  LEFT JOIN samples.tpch.customer c ON o.o_custkey = c.c_custkey
dimensions:
  - name: Order key
    expr: o_orderkey
measures:
  - name: Order Count
    expr: COUNT(o_orderkey)
```

> Quando usar SQL query como source com JOINs, prefira definir primary/foreign key constraints nas tabelas com `RELY` para otimização de queries.

### Composabilidade entre Measures

Measures podem referenciar outras measures definidas anteriormente no mesmo YAML usando `MEASURE()`:

```yaml
measures:
  - name: Total Revenue
    expr: SUM(total_price)
  - name: Fulfilled Orders
    expr: COUNT(1) FILTER (WHERE status = 'F')
  - name: Total Orders
    expr: COUNT(1)
  - name: Fulfillment Rate          # medida composta
    expr: MEASURE(Fulfilled Orders) / MEASURE(Total Orders)
    display_name: "Order Fulfillment Rate"
    format:
      type: percentage
```

> Prefira composabilidade a duplicar lógica de agregação. Se `Total Revenue` mudar, todas as medidas compostas que o referenciam atualizam automaticamente.

### Semantic Metadata (DBR 17.3+)

Adicione `display_name`, `format` e `synonyms` para melhorar visualizações e precisão do AI/BI Genie:

```yaml
version: 1.1
source: catalog.schema.orders
dimensions:
  - name: order_date
    expr: o_orderdate
    display_name: Order Date
    synonyms:
      - order time
      - date of order
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true
measures:
  - name: total_revenue
    expr: SUM(o_totalprice)
    display_name: Total Revenue
    synonyms:
      - revenue
      - total sales
    format:
      type: currency
      currency_code: USD
      decimal_places:
        type: exact
        places: 2
      abbreviation: compact
```

> Sinônimos são importados automaticamente pelo Genie para melhorar a descoberta de métricas via linguagem natural. Cada dimensão/medida suporta até 10 sinônimos, máximo de 255 caracteres cada.

> ⚠️ **Atenção com YAML comments (#) em v1.1:** Ao salvar via UI ou `CREATE/ALTER VIEW`, inline comments (`#`) são removidos automaticamente. Para preservá-los, use `ALTER VIEW` diretamente num notebook/SQL editor.

## Key Concepts

### Dimensions vs Measures

| | Dimensions | Measures |
|---|---|---|
| **Purpose** | Categorize and group data | Aggregate numeric values |
| **Examples** | Region, Date, Status | SUM(revenue), COUNT(orders) |
| **In queries** | Used in SELECT and GROUP BY | Wrapped in `MEASURE()` |
| **SQL expressions** | Any SQL expression | Must use aggregate functions |
| **Composability** | Can reference earlier dimensions | Can reference earlier measures via `MEASURE()` |

### Why Metric Views vs Standard Views?

| Feature | Standard Views | Metric Views |
|---------|---------------|--------------|
| Aggregation locked at creation | Yes | No - flexible at query time |
| Safe re-aggregation of ratios | No | Yes |
| Star/snowflake schema joins | Manual | Declarative in YAML |
| Materialization | Separate MV needed | Built-in (experimental) |
| AI/BI Genie integration | Limited | Native |
| Semantic metadata (display name, format, synonyms) | No | Yes (v1.1+, DBR 17.3+) |
| Composable measures | No | Yes (`MEASURE()` referências) |
| SQL query inline como source | N/A | Yes (v1.1+) |
| Metric view como source de outra metric view | No | Yes (composabilidade entre views) |

### Feature Availability by Runtime

| Feature | Requisito mínimo |
|---------|-----------------|
| Criar e consultar metric views | DBR 16.4+ / DBSQL 2025.16 preview |
| YAML v1.1 com `comment` em dimensões/measures | DBR 17.2+ / DBSQL 2025.30 preview |
| Snowflake-schema joins (joins aninhados) | DBR 17.1+ |
| Semantic metadata (`display_name`, `format`, `synonyms`) | DBR 17.3+ / DBSQL 2025.30 preview |
| `DESCRIBE TABLE` com coluna `metadata` | DBR 17.3+ |

## Common Issues

| Issue | Solution |
|-------|----------|
| **SELECT * not supported** | Must explicitly list dimensions and use MEASURE() for measures |
| **"Cannot resolve column"** | Dimension/measure names with spaces need backtick quoting |
| **JOIN at query time fails** | Joins must be in the YAML definition, not in the SELECT query |
| **MEASURE() required** | All measure references must be wrapped: `MEASURE(\`name\`)` |
| **DBR version error** | Mínimo DBR 16.4+ para metric views; DBR 17.1+ para snowflake joins; DBR 17.3+ para semantic metadata |
| **Materialization not working** | Requires serverless compute enabled; currently experimental |
| **YAML comments desapareceram** | Inline `#` comments são removidos ao salvar em v1.1. Use `ALTER VIEW` num notebook para preservá-los. |
| **Backtick no início de expressão YAML** | Expressões que começam com backtick devem ser envolvidas em aspas duplas: `expr: "\`Order Month\`"` |
| **MAP type columns em joins** | Joined tables não suportam MAP type columns — use `explode()` antes. |

## Integrations

Metric views work natively with:
- **AI/BI Dashboards** - Use as datasets; `display_name` e `format` são aplicados automaticamente
- **AI/BI Genie** - Natural language querying; `synonyms` são importados automaticamente
- **Alerts** - Set threshold-based alerts on measures
- **SQL Editor** - Direct SQL querying with MEASURE()
- **Catalog Explorer UI** - Visual creation (low-code editor) and YAML editor with built-in validation
- **Sigma Computing** - Integração direta com metric views em real-time
- **Hex** - Navegação e query de metric views no Data browser
- **Tableau** - Integração planejada (late 2026)

## Resources

- [Metric Views Documentation](https://docs.databricks.com/aws/en/business-semantics/metric-views)
- [Create and Edit Metric Views](https://docs.databricks.com/aws/en/business-semantics/metric-views/create-edit)
- [YAML Syntax Reference](https://docs.databricks.com/aws/en/business-semantics/metric-views/yaml-reference)
- [Model Metric Views (source, joins, composability)](https://docs.databricks.com/aws/en/business-semantics/metric-views/basic-modeling)
- [Semantic Metadata (display_name, format, synonyms)](https://docs.databricks.com/aws/en/metric-views/data-modeling/semantic-metadata)
- [Composability](https://docs.databricks.com/gcp/en/metric-views/data-modeling/composability)
- [Joins](https://docs.databricks.com/aws/en/business-semantics/metric-views/yaml-reference#joins)
- [Window Measures](https://docs.databricks.com/aws/en/metric-views/data-modeling/window-measures) (Experimental)
- [Materialization](https://docs.databricks.com/en/metric-views/materialization)
- [MEASURE() Function](https://docs.databricks.com/en/sql/language-manual/functions/measure)
- [Tutorial: Build a complete metric view with joins](https://docs.databricks.com/aws/en/business-semantics/metric-views/tpch-example)
