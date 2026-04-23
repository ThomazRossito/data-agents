---
name: databricks-ai-functions
description: "Use Databricks built-in AI Functions (ai_classify, ai_extract, ai_summarize, ai_mask, ai_translate, ai_fix_grammar, ai_gen, ai_analyze_sentiment, ai_similarity, ai_parse_document, ai_query, ai_forecast) to add AI capabilities directly to SQL and PySpark pipelines without managing model endpoints. Also covers document parsing and building custom RAG pipelines (parse → chunk → index → query)."
updated_at: 2026-04-23
source: web_search
---

# Databricks AI Functions

> **Official Docs:** https://docs.databricks.com/aws/en/large-language-models/ai-functions
> Individual function reference: https://docs.databricks.com/aws/en/sql/language-manual/functions/

## Overview

Databricks AI Functions are built-in SQL and PySpark functions that call Foundation Model APIs directly from your data pipelines — no model endpoint setup, no API keys, no boilerplate. They operate on table columns as naturally as `UPPER()` ou `LENGTH()`, e são otimizadas para batch inference em escala.

There are three categories:

| Category | Functions | Use when |
|---|---|---|
| **Task-specific** | `ai_analyze_sentiment`, `ai_classify`, `ai_extract`, `ai_fix_grammar`, `ai_gen`, `ai_mask`, `ai_similarity`, `ai_summarize`, `ai_translate`, `ai_parse_document` | The task is well-defined — prefer these always |
| **General-purpose** | `ai_query` | Complex nested JSON, custom endpoints, multimodal — **last resort only** |
| **Table-valued** | `ai_forecast` | Time series forecasting |

**Function selection rule — always prefer a task-specific function over `ai_query`:**

| Task | Use this | Fall back to `ai_query` when... |
|---|---|---|
| Sentiment scoring | `ai_analyze_sentiment` | Never |
| Fixed-label routing | `ai_classify` (2–500 labels; add descriptions for accuracy) | Never |
| Entity / field extraction | `ai_extract` | Never |
| Summarization | `ai_summarize` | Never — use `max_words=0` for uncapped |
| Grammar correction | `ai_fix_grammar` | Never |
| Translation | `ai_translate` | Target language not in the supported list |
| PII redaction | `ai_mask` | Never |
| Free-form generation | `ai_gen` | Need structured JSON output |
| Semantic similarity | `ai_similarity` | Never |
| PDF / document parsing | `ai_parse_document` | Need image-level reasoning |
| Complex JSON / reasoning | — | **This is the intended use case for `ai_query`** |

## Prerequisites

- Databricks SQL warehouse (**not Classic**) or cluster with DBR **15.1+**
- DBR **15.4 ML LTS** recommended for batch workloads
- DBR **17.1+** required for `ai_parse_document`
- `ai_forecast` requires a **Pro or Serverless** SQL warehouse
- Workspace in a supported AWS/Azure region for batch AI inference
- Models run under Apache 2.0, Meta Llama community licenses, or third-party terms (Anthropic, Google, OpenAI) — customers are responsible for compliance with each provider's usage policy

> ℹ️ **Modelos hospedados pela Databricks (prefixo `databricks-`):** use sempre esses endpoints provisionless em AI Functions — eles são totalmente gerenciados, escalam automaticamente, e são otimizados para batch inference. Não use provisioned throughput endpoints com AI Functions.

## Foundation Models disponíveis (abril 2026)

Os modelos com prefixo `databricks-` são os recomendados para uso em AI Functions. O catálogo evolui continuamente — consulte a [página de modelos suportados](https://docs.databricks.com/aws/en/machine-learning/foundation-model-apis/supported-models) para a lista atual. Exemplos notáveis:

| Família | Endpoint de exemplo | Notas |
|---|---|---|
| Meta Llama | `databricks-llama-4-maverick` | Suporta multimodal (`files =>`) |
| Anthropic Claude | `databricks-claude-sonnet-4-5` / `databricks-claude-haiku-4-5` | Dentro do perímetro de segurança Databricks |
| OpenAI GPT | `databricks-gpt-oss-120b` | Hospedado pela Databricks |
| Google Gemini | `databricks-gemini-3-flash` | Requer cross-geography routing habilitado |

> ⚠️ **Modelos depreciados:** `databricks-meta-llama-3-1-405b-instruct` foi removido de pay-per-token. `DBRX` e `Mixtral` foram aposentados de Foundation Model APIs. Atualize referências hardcoded nos pipelines — prefira centralizar o nome do modelo em `config.yml` (veja [4-document-processing-pipeline.md](4-document-processing-pipeline.md)).

## Quick Start

Classify, extract, and score sentiment from a text column in a single query:

```sql
SELECT
    ticket_id,
    ticket_text,
    ai_classify(ticket_text, ARRAY('urgent', 'not urgent', 'spam')) AS priority,
    ai_extract(ticket_text, ARRAY('product', 'error_code', 'date'))  AS entities,
    ai_analyze_sentiment(ticket_text)                                 AS sentiment
FROM support_tickets;
```

```python
from pyspark.sql.functions import expr

df = spark.table("support_tickets")
df = (
    df.withColumn("priority",  expr("ai_classify(ticket_text, array('urgent', 'not urgent', 'spam'))"))
      .withColumn("entities",  expr("ai_extract(ticket_text, array('product', 'error_code', 'date'))"))
      .withColumn("sentiment", expr("ai_analyze_sentiment(ticket_text)"))
)
# Access nested STRUCT fields from ai_extract
df.select("ticket_id", "priority", "sentiment",
          "entities.product", "entities.error_code", "entities.date").display()
```

## Common Patterns

### Pattern 1: Text Analysis Pipeline

Chain multiple task-specific functions to enrich a text column in one pass:

```sql
SELECT
    id,
    content,
    ai_analyze_sentiment(content)               AS sentiment,
    ai_summarize(content, 30)                   AS summary,
    ai_classify(content,
        ARRAY('technical', 'billing', 'other')) AS category,
    ai_fix_grammar(content)                     AS content_clean
FROM raw_feedback;
```

### Pattern 2: PII Redaction Before Storage

```python
from pyspark.sql.functions import expr

df_clean = (
    spark.table("raw_messages")
    .withColumn(
        "message_safe",
        expr("ai_mask(message, array('person', 'email', 'phone', 'address'))")
    )
)
df_clean.write.format("delta").mode("append").saveAsTable("catalog.schema.messages_safe")
```

### Pattern 3: Document Ingestion from a Unity Catalog Volume

> ⚠️ **Breaking change (setembro 2025): `ai_parse_document` — novo parâmetro `version`**
> O schema de output foi atualizado em 22 de setembro de 2025. Workloads criados antes dessa data devem migrar para o schema atualizado especificando o parâmetro `version` explicitamente na chamada SQL. Consulte a [documentação de migração](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document) para os passos detalhados.

Parse PDFs/Office docs, then enrich with task-specific functions:

```python
from pyspark.sql.functions import expr

df = (
    spark.read.format("binaryFile")
    .load("/Volumes/catalog/schema/landing/documents/")
    # Adicione version => '2' (ou a versão atual) para workloads pós-set/2025
    .withColumn("parsed", expr("ai_parse_document(content)"))
    .selectExpr("path",
                "parsed:pages[*].elements[*].content AS text_blocks",
                "parsed:error AS parse_error")
    .filter("parse_error IS NULL")
    .withColumn("summary",  expr("ai_summarize(text_blocks, 50)"))
    .withColumn("entities", expr("ai_extract(text_blocks, array('date', 'amount', 'vendor'))"))
)
```

### Pattern 4: Semantic Matching / Deduplication

```sql
-- Find near-duplicate company names
SELECT a.id, b.id, ai_similarity(a.name, b.name) AS score
FROM companies a
JOIN companies b ON a.id < b.id
WHERE ai_similarity(a.name, b.name) > 0.85;
```

### Pattern 5: Complex JSON Extraction with `ai_query` (last resort)

Use only when the output schema has nested arrays or requires multi-step reasoning that no task-specific function handles.

`responseFormat` suporta dois estilos — prefira **JSON Schema com `"strict": true`** para maior previsibilidade de output:

```python
from pyspark.sql.functions import expr, from_json, col

# Estilo recomendado: json_schema com strict:true
# O campo .response retorna diretamente o objeto estruturado quando responseFormat é especificado
df = (
    spark.table("parsed_documents")
    .withColumn("ai_response", expr("""
        ai_query(
            'databricks-claude-sonnet-4-5',
            concat('Extract invoice as JSON with nested itens array: ', text_blocks),
            responseFormat => '{
                "type": "json_schema",
                "json_schema": {
                    "name": "invoice",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "numero":  {"type": "string"},
                            "total":   {"type": "number"},
                            "itens":   {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "codigo":    {"type": "string"},
                                        "descricao": {"type": "string"},
                                        "qtde":      {"type": "number"},
                                        "vlrUnit":   {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "strict": true
                }
            }',
            failOnError => false
        )
    """))
    .withColumn("invoice", from_json(
        col("ai_response.response"),
        "STRUCT<numero:STRING, total:DOUBLE, "
        "itens:ARRAY<STRUCT<codigo:STRING, descricao:STRING, qtde:DOUBLE, vlrUnit:DOUBLE>>>"
    ))
)
```

> **Alternativa DDL-style** (mais concisa, mas menos portável entre modelos):
> ```sql
> responseFormat => 'STRUCT<numero:STRING, total:DOUBLE, itens:ARRAY<STRUCT<codigo:STRING, descricao:STRING>>>'
> ```

**Multimodal com `files =>`** (use `databricks-llama-4-maverick` ou outro modelo multimodal):

```sql
SELECT *, ai_query(
    'databricks-llama-4-maverick',
    'Describe the contents of this image',
    files => content
) AS output
FROM READ_FILES("/Volumes/catalog/schema/images/")
WHERE content IS NOT NULL;
```

### Pattern 6: Time Series Forecasting

```sql
SELECT *
FROM ai_forecast(
    observed  => TABLE(SELECT date, sales FROM daily_sales),
    horizon   => '2026-12-31',
    time_col  => 'date',
    value_col => 'sales'
);
-- Returns: date, sales_forecast, sales_upper, sales_lower
```

## Reference Files

- [1-task-functions.md](1-task-functions.md) — Full syntax, parameters, SQL + PySpark examples for all 9 task-specific functions (`ai_analyze_sentiment`, `ai_classify`, `ai_extract`, `ai_fix_grammar`, `ai_gen`, `ai_mask`, `ai_similarity`, `ai_summarize`, `ai_translate`) and `ai_parse_document`
- [2-ai-query.md](2-ai-query.md) — `ai_query` complete reference: all parameters, structured output com `responseFormat` (DDL-style e `json_schema`), multimodal `files =>`, UDF patterns, and error handling
- [3-ai-forecast.md](3-ai-forecast.md) — `ai_forecast` parameters, single-metric, multi-group, multi-metric, and confidence interval patterns
- [4-document-processing-pipeline.md](4-document-processing-pipeline.md) — End-to-end batch document processing pipeline using AI Functions in a Lakeflow Declarative Pipeline; includes `config.yml` centralization (recomendado para evitar hardcode de nomes de modelo), function selection logic, custom RAG pipeline (parse → chunk → Vector Search), and DSPy/LangChain guidance for near-real-time variants

## Common Issues

| Issue | Solution |
|---|---|
| `ai_parse_document` not found | Requires DBR **17.1+**. Check cluster runtime. |
| `ai_parse_document` retorna schema inesperado | Workloads criados antes de 22/09/2025 precisam migrar para o schema atualizado — use o parâmetro `version` explicitamente. Veja a [doc de migração](https://docs.databricks.com/aws/en/sql/language-manual/functions/ai_parse_document). |
| `ai_forecast` fails | Requires **Pro or Serverless** SQL warehouse — not available on Classic or Starter. |
| All functions return NULL | Input column is NULL. Filter with `WHERE col IS NOT NULL` before calling. |
| `ai_translate` fails for a language | Supported: English, German, French, Italian, Portuguese, Hindi, Spanish, Thai. Use `ai_query` with a multilingual model for others. |
| `ai_classify` returns unexpected labels | Use clear, mutually exclusive label names. Fewer labels (2–5) produces more reliable results. |
| `ai_query` raises on some rows in a batch job | Add `failOnError => false` — returns a STRUCT with `.response` and `.error` instead of raising. |
| Batch job runs slowly | Use DBR **15.4 ML LTS** cluster (not serverless or interactive) for optimized batch inference throughput. Submit o dataset completo em uma única query — AI Functions gerenciam paralelização e retries automaticamente. |
| Modelo não encontrado / endpoint depreciado | `DBRX`, `Mixtral` e `Meta-Llama-3.1-405B` foram aposentados. Substitua por modelos `databricks-*` atuais (ex: `databricks-llama-4-maverick`, `databricks-claude-sonnet-4-5`). Centralize nomes em `config.yml`. |
| Want to swap models without editing pipeline code | Store all model names and prompts in `config.yml` — see [4-document-processing-pipeline.md](4-document-processing-pipeline.md) for the pattern. |
| `responseFormat` com `{"type":"json_object"}` retorna output inconsistente | Prefira `{"type":"json_schema", "json_schema": {...}, "strict": true}` — garante schema estrito e output previsível. O estilo `json_object` não valida a estrutura. |
