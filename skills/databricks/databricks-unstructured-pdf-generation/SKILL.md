---
name: databricks-unstructured-pdf-generation
description: "Generate PDF documents from HTML and upload to Unity Catalog volumes. Use for creating test PDFs, demo documents, reports, or evaluation datasets. Covers MCP tool usage, WeasyPrint engine, Volumes SDK, Medallion pipeline patterns, and RAG ingestion."
updated_at: 2026-04-16
source: context7
---

# PDF Generation from HTML

Convert HTML content to PDF documents and upload them to Unity Catalog Volumes.

## Overview

The `generate_and_upload_pdf` MCP tool converts HTML to PDF and uploads to a Unity Catalog Volume. You (the LLM) generate the HTML content, and the tool handles conversion and upload.

The underlying engine is **WeasyPrint** — a Python library that renders HTML/CSS to PDF with full CSS3 support. WeasyPrint runs server-side in the Databricks cluster; no browser or headless Chrome is required.

## Tool Signature

```
generate_and_upload_pdf(
    html_content: str,      # Complete HTML document
    filename: str,          # PDF filename (e.g., "report.pdf")
    catalog: str,           # Unity Catalog name
    schema: str,            # Schema name
    volume: str = "raw_data",  # Volume name (default: "raw_data")
    folder: str = None,     # Optional subfolder
)
```

**Returns:**
```json
{
    "success": true,
    "volume_path": "/Volumes/catalog/schema/volume/filename.pdf",
    "error": null
}
```

## Quick Start

Generate a simple PDF:

```
generate_and_upload_pdf(
    html_content='''<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }
        .section { margin: 20px 0; }
    </style>
</head>
<body>
    <h1>Quarterly Report Q1 2025</h1>
    <div class="section">
        <h2>Executive Summary</h2>
        <p>Revenue increased 15% year-over-year...</p>
    </div>
</body>
</html>''',
    filename="q1_report.pdf",
    catalog="my_catalog",
    schema="my_schema"
)
```

## Performance: Generate Multiple PDFs in Parallel

**IMPORTANT**: PDF generation and upload can take 2-5 seconds per document. When generating multiple PDFs, **call the tool in parallel** to maximize throughput.

### Example: Generate 5 PDFs in Parallel

Make 5 simultaneous `generate_and_upload_pdf` calls:

```
# Call 1
generate_and_upload_pdf(
    html_content="<html>...Employee Handbook content...</html>",
    filename="employee_handbook.pdf",
    catalog="hr_catalog", schema="policies", folder="2025"
)

# Call 2 (parallel)
generate_and_upload_pdf(
    html_content="<html>...Leave Policy content...</html>",
    filename="leave_policy.pdf",
    catalog="hr_catalog", schema="policies", folder="2025"
)

# Call 3 (parallel)
generate_and_upload_pdf(
    html_content="<html>...Code of Conduct content...</html>",
    filename="code_of_conduct.pdf",
    catalog="hr_catalog", schema="policies", folder="2025"
)

# Call 4 (parallel)
generate_and_upload_pdf(
    html_content="<html>...Benefits Guide content...</html>",
    filename="benefits_guide.pdf",
    catalog="hr_catalog", schema="policies", folder="2025"
)

# Call 5 (parallel)
generate_and_upload_pdf(
    html_content="<html>...Remote Work Policy content...</html>",
    filename="remote_work_policy.pdf",
    catalog="hr_catalog", schema="policies", folder="2025"
)
```

By calling these in parallel (not sequentially), 5 PDFs that would take 15-25 seconds sequentially complete in 3-5 seconds total.

## HTML Best Practices

### Use Complete HTML5 Structure

Always include the full HTML structure:

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        /* Your CSS here */
    </style>
</head>
<body>
    <!-- Your content here -->
</body>
</html>
```

### CSS Features Supported

WeasyPrint supports modern CSS3 and CSS Paged Media:
- Flexbox and Grid layouts
- CSS variables (`--var-name`)
- Web fonts (system fonts recommended; avoid external font URLs)
- Colors, backgrounds, borders
- Tables with styling
- `@page` rule for page size, margins, and headers/footers
- `page-break-before` / `page-break-after` / `break-before` / `break-after`

### CSS to Avoid

- Animations and transitions (static PDF — ignored silently)
- Interactive elements (forms, hover effects — rendered as static)
- External resources via URL — use embedded base64 for images
- CSS `position: fixed` — not supported in paged media context

### Page Control with @page (WeasyPrint)

```html
<style>
    @page {
        size: A4 portrait;
        margin: 20mm 15mm 25mm 15mm;

        @top-center {
            content: "Confidential — Internal Use Only";
            font-size: 9pt;
            color: #888;
        }
        @bottom-right {
            content: "Page " counter(page) " of " counter(pages);
            font-size: 9pt;
        }
    }

    /* Force page break before each major section */
    .section-break {
        break-before: page;
    }
</style>
```

### Professional Document Template

```html
<!DOCTYPE html>
<html>
<head>
    <style>
        :root {
            --primary: #1a73e8;
            --text: #202124;
            --gray: #5f6368;
        }
        @page {
            size: A4;
            margin: 20mm 15mm 25mm 15mm;
            @bottom-right {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 8pt;
                color: var(--gray);
            }
        }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            color: var(--text);
            line-height: 1.6;
        }
        h1 {
            color: var(--primary);
            border-bottom: 3px solid var(--primary);
            padding-bottom: 15px;
        }
        h2 { color: var(--text); margin-top: 30px; }
        .highlight {
            background: #e8f0fe;
            padding: 15px;
            border-left: 4px solid var(--primary);
            margin: 20px 0;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            border: 1px solid #dadce0;
            padding: 12px;
            text-align: left;
        }
        th { background: #f1f3f4; }
        .footer {
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #dadce0;
            color: var(--gray);
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>Document Title</h1>

    <h2>Section 1</h2>
    <p>Content here...</p>

    <div class="highlight">
        <strong>Important:</strong> Key information highlighted here.
    </div>

    <h2>Data Table</h2>
    <table>
        <tr><th>Column 1</th><th>Column 2</th><th>Column 3</th></tr>
        <tr><td>Data</td><td>Data</td><td>Data</td></tr>
    </table>

    <div class="footer">
        Generated on 2025-04-16 | Confidential
    </div>
</body>
</html>
```

## Common Patterns

### Pattern 1: Technical Documentation

Generate API documentation, user guides, or technical specs:

```
generate_and_upload_pdf(
    html_content='''<!DOCTYPE html>
<html>
<head><style>
    body { font-family: monospace; margin: 40px; }
    code { background: #f4f4f4; padding: 2px 6px; }
    pre { background: #f4f4f4; padding: 15px; overflow-x: auto; }
    .endpoint { background: #e3f2fd; padding: 10px; margin: 10px 0; }
</style></head>
<body>
    <h1>API Reference</h1>
    <div class="endpoint">
        <code>GET /api/v1/users</code>
        <p>Returns a list of all users.</p>
    </div>
    <h2>Request Headers</h2>
    <pre>Authorization: Bearer {token}
Content-Type: application/json</pre>
</body>
</html>''',
    filename="api_reference.pdf",
    catalog="docs_catalog",
    schema="api_docs"
)
```

### Pattern 2: Business Reports

```
generate_and_upload_pdf(
    html_content='''<!DOCTYPE html>
<html>
<head><style>
    body { font-family: Georgia, serif; margin: 50px; }
    .metric { display: inline-block; text-align: center; margin: 20px; }
    .metric-value { font-size: 2em; color: #1a73e8; }
    .metric-label { color: #666; }
</style></head>
<body>
    <h1>Q1 2025 Performance Report</h1>
    <div class="metric">
        <div class="metric-value">$2.4M</div>
        <div class="metric-label">Revenue</div>
    </div>
    <div class="metric">
        <div class="metric-value">+15%</div>
        <div class="metric-label">Growth</div>
    </div>
</body>
</html>''',
    filename="q1_2025_report.pdf",
    catalog="finance",
    schema="reports",
    folder="quarterly"
)
```

### Pattern 3: HR Policies

```
generate_and_upload_pdf(
    html_content='''<!DOCTYPE html>
<html>
<head><style>
    body { font-family: Arial; margin: 40px; line-height: 1.8; }
    .policy-section { margin: 30px 0; }
    .important { background: #fff3e0; padding: 15px; border-radius: 5px; }
</style></head>
<body>
    <h1>Employee Leave Policy</h1>
    <p><em>Effective: January 1, 2025</em></p>

    <div class="policy-section">
        <h2>1. Annual Leave</h2>
        <p>All full-time employees are entitled to 20 days of paid annual leave per calendar year.</p>
    </div>

    <div class="important">
        <strong>Note:</strong> Leave requests must be submitted at least 2 weeks in advance.
    </div>
</body>
</html>''',
    filename="leave_policy.pdf",
    catalog="hr_catalog",
    schema="policies"
)
```

## Workflow for Multiple Documents

When asked to generate multiple PDFs:

1. **Plan the documents**: Determine titles, content structure for each
2. **Generate HTML for each**: Create complete HTML documents
3. **Call tool in parallel**: Make multiple simultaneous `generate_and_upload_pdf` calls
4. **Report results**: Summarize successful uploads and any errors

## Generating PDFs Programmatically via Python SDK

When you need to generate PDFs inside a Databricks notebook or Job (not via MCP tool), use WeasyPrint directly and upload via `w.files.upload()`.

```python
# Install in cluster init script or notebook:
# %pip install weasyprint

import io
from weasyprint import HTML
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

def generate_and_upload(html_content: str, volume_path: str, overwrite: bool = True) -> str:
    """Render HTML to PDF bytes and upload to a Unity Catalog Volume."""
    pdf_bytes = HTML(string=html_content).write_pdf()
    w.files.upload(
        file_path=volume_path,
        contents=io.BytesIO(pdf_bytes),
        overwrite=overwrite,
    )
    return volume_path

# Example usage
html = """<!DOCTYPE html>
<html><head><style>body { font-family: Arial; }</style></head>
<body><h1>Generated Report</h1><p>Content here.</p></body>
</html>"""

path = generate_and_upload(
    html_content=html,
    volume_path="/Volumes/my_catalog/my_schema/raw_data/reports/report_2025.pdf",
)
print(f"Uploaded: {path}")
```

### Batch Generation with Parallel Uploads (SDK)

For large batches, use `ThreadPoolExecutor` to parallelize both PDF rendering and upload:

```python
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from weasyprint import HTML
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

documents = [
    {"filename": "doc_001.pdf", "html": "<html>...</html>", "folder": "batch_2025"},
    {"filename": "doc_002.pdf", "html": "<html>...</html>", "folder": "batch_2025"},
    # ...
]

BASE_VOLUME = "/Volumes/my_catalog/my_schema/raw_data"

def render_and_upload(doc: dict) -> dict:
    try:
        pdf_bytes = HTML(string=doc["html"]).write_pdf()
        path = f"{BASE_VOLUME}/{doc['folder']}/{doc['filename']}"
        w.files.upload(file_path=path, contents=io.BytesIO(pdf_bytes), overwrite=True)
        return {"filename": doc["filename"], "success": True, "path": path}
    except Exception as e:
        return {"filename": doc["filename"], "success": False, "error": str(e)}

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(render_and_upload, doc): doc for doc in documents}
    results = [f.result() for f in as_completed(futures)]

failures = [r for r in results if not r["success"]]
if failures:
    print(f"Failed: {failures}")
```

## Medallion Pipeline: Bronze → Silver (Generated PDFs as Source)

When generated PDFs serve as a source for downstream pipelines (e.g., RAG datasets or evaluation corpora), organize storage with the Medallion pattern:

```
/Volumes/<catalog>/bronze/<volume>/pdfs/raw/      ← PDFs gerados (landing)
/Volumes/<catalog>/silver/<volume>/parsed_text/   ← texto extraído por ai_parse_document
/Volumes/<catalog>/gold/<volume>/chunks/          ← chunks para Vector Search
```

### Bronze → Silver: Extraindo texto dos PDFs gerados

After generating PDFs into the bronze volume, parse them with `ai_parse_document` in a DLT pipeline:

```python
import dlt
from pyspark.sql.functions import expr, current_timestamp

BRONZE_PATH = "/Volumes/my_catalog/bronze/docs/pdfs/raw/"

@dlt.table(comment="Texto bruto extraído dos PDFs gerados (bronze → silver)")
def silver_parsed_pdf_text():
    return (
        spark.readStream
            .format("binaryFile")
            .option("pathGlobFilter", "*.pdf")
            .option("recursiveFileLookup", "true")
            .load(BRONZE_PATH)
        .repartition(8, expr("crc32(path) % 8"))
        .withColumn("parsed", expr("""
            ai_parse_document(content, map('version', '2.0', 'descriptionElementTypes', '*'))
        """))
        .withColumn("text", expr("""
            concat_ws('\n\n', transform(
                try_cast(parsed:document:elements AS ARRAY),
                e -> try_cast(e:content AS STRING)
            ))
        """))
        .withColumn("parse_error", expr("try_cast(parsed:error_status AS STRING)"))
        .withColumn("ingested_at", current_timestamp())
        .select("path", "text", "parse_error", "ingested_at")
    )
```

### Silver → Gold: Chunking para Vector Search

```sql
CREATE OR REPLACE TABLE my_catalog.gold.pdf_chunks AS
WITH elements AS (
  SELECT
    path,
    explode(variant_get(parsed, '$.document.elements', 'ARRAY<VARIANT>')) AS element,
    ingested_at
  FROM my_catalog.silver.parsed_pdf_text
  WHERE parse_error IS NULL
)
SELECT
  md5(concat(path, variant_get(element, '$.content', 'STRING'))) AS chunk_id,
  path                                                            AS source_path,
  variant_get(element, '$.content', 'STRING')                    AS content,
  variant_get(element, '$.type', 'STRING')                       AS element_type,
  ingested_at
FROM elements
WHERE length(trim(variant_get(element, '$.content', 'STRING'))) > 20;

-- Enable CDF for Vector Search Delta Sync
ALTER TABLE my_catalog.gold.pdf_chunks
SET TBLPROPERTIES (delta.enableChangeDataFeed = true);
```

## Integration with Databricks Vector Search (RAG)

After chunking, index the Gold table in Vector Search for RAG pipelines:

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    DeltaSyncVectorIndexSpecRequest,
    EmbeddingSourceColumn,
    VectorIndexType,
    PipelineType,
)

w = WorkspaceClient()

w.vector_search_indexes.create_index(
    name="my_catalog.gold.pdf_chunks_index",
    endpoint_name="my_vs_endpoint",
    primary_key="chunk_id",
    index_type=VectorIndexType.DELTA_SYNC,
    delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
        source_table="my_catalog.gold.pdf_chunks",
        pipeline_type=PipelineType.TRIGGERED,
        embedding_source_columns=[
            EmbeddingSourceColumn(
                name="content",
                embedding_model_endpoint_name="databricks-gte-large-en",
            )
        ],
    ),
)
```

Query the index in a RAG context:

```python
results = w.vector_search_indexes.query_index(
    index_name="my_catalog.gold.pdf_chunks_index",
    columns=["chunk_id", "source_path", "content"],
    query_text="quarterly revenue growth",
    num_results=5,
)
for r in results.result.data_array:
    print(r)
```

## Prerequisites

- Unity Catalog schema must exist
- Volume must exist (default: `raw_data`)
- User must have `WRITE VOLUME` permission on the volume
- WeasyPrint must be installed on the cluster (add `weasyprint` to cluster libraries or init script) when using the Python SDK path

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Volume does not exist" | Create the volume first or use an existing one |
| "Schema does not exist" | Create the schema or check the name |
| PDF looks wrong | Check HTML/CSS syntax; use WeasyPrint-supported CSS features |
| Slow generation (sequential) | Call multiple PDFs in parallel, not sequentially |
| Font missing / garbled text | Use system fonts (Arial, Helvetica, Georgia) — avoid Google Fonts CDN URLs |
| External image not rendered | Embed images as base64 `data:image/png;base64,...` — WeasyPrint does not fetch external URLs in sandboxed clusters |
| `@page` footer not showing | Ensure `@page` rule is inside `<style>` tag in `<head>`, not inline |
| WeasyPrint import error on cluster | Install via init script: `pip install weasyprint` or add to cluster libraries |
| Large PDF upload slow | Use `w.files.upload_from()` with `use_parallel=True` (SDK v0.72.0+) for files > 100 MB |
| `explode()` fails on parsed VARIANT | Use `variant_get(doc, '$.document.elements', 'ARRAY<VARIANT>')` to cast before exploding |
