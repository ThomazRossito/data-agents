---
name: databricks-vector-search
updated_at: 2026-04-23
source: web_search
---

# Databricks Vector Search

Patterns for creating, managing, and querying vector search indexes for RAG and semantic search applications.

## When to Use

Use this skill when:
- Building RAG (Retrieval-Augmented Generation) applications
- Implementing semantic search or similarity matching
- Creating vector indexes from Delta tables
- Choosing between storage-optimized and standard endpoints
- Querying vector indexes with filters

## Overview

Databricks Vector Search (Mosaic AI Vector Search, GA) provides managed vector similarity search with automatic embedding generation and Delta Lake integration.

| Component | Description |
|-----------|-------------|
| **Endpoint** | Compute resource hosting indexes (Standard or Storage-Optimized) |
| **Index** | Vector data structure for similarity search |
| **Delta Sync** | Auto-syncs with source Delta table |
| **Direct Access** | Manual CRUD operations on vectors |

## Endpoint Types

> ⚠️ Breaking change em março/2026: Empty endpoints não geram mais cobrança. A cobrança começa apenas após a criação do primeiro índice, e cessa automaticamente 24h após a exclusão do último índice.

| Type | Latency | Capacity | Cost | Best For |
|------|---------|----------|------|----------|
| **Standard** | 20-50ms | 320M vectors (768 dim) | Higher | Real-time, low-latency; suporta `min_qps` (Beta) |
| **Storage-Optimized** | ~250ms | 1B+ vectors (768 dim) | Menor | Large-scale, cost-sensitive; 10-20x faster indexing |

**Notas de endpoint:**
- Storage-Optimized está em **Public Preview**.
- `Continuous sync` e `columns_to_sync` **não são suportados** em Storage-Optimized.
- Embedding dimension em Storage-Optimized deve ser **divisível por 16**.
- Standard endpoints suportam `min_qps` (Beta) para capacity scaling automático por QPS mínimo desejado.

## Index Types

| Type | Embeddings | Sync | Use Case |
|------|------------|------|----------|
| **Delta Sync (managed)** | Databricks computes | Auto from Delta | Easiest setup |
| **Delta Sync (self-managed)** | You provide | Auto from Delta | Custom embeddings |
| **Direct Access** | You provide | Manual CRUD | Real-time updates |
| **Full-Text Search (Beta)** | None (keyword BM25) | Triggered only | Keyword-only, sem embeddings; só Storage-Optimized |

## Search Modes

| Mode | `query_type` | Disponibilidade |
|------|-------------|----------------|
| ANN (vector similarity) | `"ANN"` (default) | Standard + Storage-Optimized |
| Hybrid (ANN + BM25) | `"HYBRID"` | Standard + Storage-Optimized |
| Full-text keyword | `"FULL_TEXT"` (Beta) | Standard + Storage-Optimized |
| Dedicated Full-Text Index | N/A (index-level) | Storage-Optimized + TRIGGERED only |

## Quick Start

### Create Endpoint

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create a standard endpoint
endpoint = vsc.create_endpoint(
    name="my-vs-endpoint",
    endpoint_type="STANDARD"  # or "STORAGE_OPTIMIZED"
)
# Ou aguardar o endpoint ficar online:
endpoint = vsc.create_endpoint_and_wait(name="my-vs-endpoint", endpoint_type="STANDARD")
```

> **Tip:** use `vsc.endpoint_exists("my-vs-endpoint")` para checagem idempotente antes de criar.

### Create Delta Sync Index (Managed Embeddings)

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Source table must have: primary key column + text column
# Standard endpoints: source table needs Change Data Feed enabled
index = vsc.create_delta_sync_index(
    endpoint_name="my-vs-endpoint",
    index_name="catalog.schema.my_index",
    source_table_name="catalog.schema.documents",
    primary_key="id",
    pipeline_type="TRIGGERED",       # ou "CONTINUOUS" (não suportado em Storage-Optimized)
    embedding_source_column="content",
    embedding_model_endpoint_name="databricks-gte-large-en",
    # Opcional: modelo separado para queries (ex.: menor latência)
    model_endpoint_name_for_query="databricks-gte-large-en"
)
```

> **Nota (`model_endpoint_name_for_query`):** permite usar um endpoint de embedding de alta throughput na ingestão e um endpoint de menor latência nas queries. Se omitido, o mesmo modelo é usado em ambos.

### Query Index

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()
index = vsc.get_index(endpoint_name="my-vs-endpoint", index_name="catalog.schema.my_index")

results = index.similarity_search(
    query_text="What is machine learning?",
    columns=["id", "content", "metadata"],
    num_results=5
)

for doc in results["result"]["data_array"]:
    score = doc[-1]  # Similarity score is last column
    print(f"Score: {score}, Content: {doc[1][:100]}...")
```

## Common Patterns

### Create Storage-Optimized Endpoint

```python
# Para deployments large-scale e cost-effective
endpoint = vsc.create_endpoint_and_wait(
    name="my-storage-endpoint",
    endpoint_type="STORAGE_OPTIMIZED"
)
```

### Delta Sync with Self-Managed Embeddings

```python
# Source table must have: primary key + embedding vector column
index = vsc.create_delta_sync_index(
    endpoint_name="my-vs-endpoint",
    index_name="catalog.schema.my_index",
    source_table_name="catalog.schema.documents",
    primary_key="id",
    pipeline_type="TRIGGERED",
    embedding_vector_column="embedding",   # coluna com embeddings pré-computados
    embedding_dimension=1024
)
```

### Direct Access Index

```python
import json
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Create index for manual CRUD
index = vsc.create_direct_access_index(
    endpoint_name="my-vs-endpoint",
    index_name="catalog.schema.direct_index",
    primary_key="id",
    embedding_vector_column="embedding",
    embedding_dimension=1024,
    schema={
        "id": "string",
        "text": "string",
        "embedding": "array<float>",
        "metadata": "string"
    }
)

# Upsert data
index.upsert([
    {"id": "1", "text": "Hello", "embedding": [0.1, 0.2, ...], "metadata": "doc1"},
    {"id": "2", "text": "World", "embedding": [0.3, 0.4, ...], "metadata": "doc2"},
])

# Delete data
index.delete(["1", "2"])
```

### Standard Endpoint — High QPS (Beta)

```python
# min_qps: apenas Standard endpoints; Storage-Optimized retorna erro
endpoint = vsc.create_endpoint(
    name="high-throughput-endpoint",
    endpoint_type="STANDARD",
    min_qps=1000  # Beta — sujeito a mudanças
)
```

### Query with Embedding Vector

```python
results = index.similarity_search(
    query_vector=[0.1, 0.2, 0.3, ...],  # Seu vetor de 1024 dimensões
    columns=["id", "text"],
    num_results=10
)
```

### Hybrid Search (Semantic + Keyword)

Hybrid search combina vector similarity (ANN) com BM25 keyword scoring. Use quando queries contêm termos exatos que devem ser encontrados — SKUs, códigos de erro, nomes próprios, terminologia técnica. Veja [search-modes.md](search-modes.md) para guia de decisão entre ANN e hybrid.

```python
results = index.similarity_search(
    query_text="SPARK-12345 executor memory error",
    columns=["id", "content"],
    query_type="HYBRID",
    num_results=10
)
```

### Full-Text Search / Keyword-Only Search (Beta)

> ⚠️ Nova feature (Beta): `query_type="FULL_TEXT"` disponível em ambos os tipos de endpoint a partir de 2025. Retorna até 200 resultados baseados em keyword matching sem embeddings.

```python
# Full-text keyword search em índice existente (standard ou storage-optimized)
results = index.similarity_search(
    query_text="executor memory error",
    columns=["id", "content"],
    query_type="FULL_TEXT",
    num_results=20
)
```

#### Índice dedicado Full-Text (sem embeddings, só Storage-Optimized + TRIGGERED)

```python
# Requer: storage-optimized endpoint + pipeline_type="TRIGGERED"
# NÃO inclui embedding_source_column, embedding_vector_column nem embedding_dimension
index = vsc.create_delta_sync_index(
    endpoint_name="my-storage-endpoint",
    index_name="catalog.schema.fulltext_index",
    source_table_name="catalog.schema.documents",
    primary_key="id",
    pipeline_type="TRIGGERED"
    # Sem colunas de embedding → índice keyword-only BM25
)
```

## Filtering

### Standard Endpoint Filters (Dictionary)

```python
# filters_json usa formato de dicionário serializado como JSON string
results = index.similarity_search(
    query_text="machine learning",
    columns=["id", "content"],
    num_results=10,
    filters={"category": "ai", "status": ["active", "pending"]}
)
```

### Storage-Optimized Filters (SQL-like string)

Storage-Optimized endpoints usam sintaxe SQL-like via parâmetro `filters` (string):

```python
from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()
index = vsc.get_index(endpoint_name="my-storage-endpoint", index_name="catalog.schema.my_index")

# SQL-like filter syntax para storage-optimized
results = index.similarity_search(
    query_text="machine learning",
    columns=["id", "content"],
    num_results=10,
    filters="category = 'ai' AND status IN ('active', 'pending')"
)

# Mais exemplos:
# filters="price > 100 AND price < 500"
# filters="department LIKE 'eng%'"
# filters="created_at >= '2024-01-01'"
# filters="language = 'en' AND country = 'us'"
```

> **Nota:** Para Storage-Optimized, os resultados são "over-fetched" e o filtro é aplicado sobre os resultados buscados. É possível que não haja resultados mesmo com matches no dataset se os scores desses documentos não estiverem entre os top-k.

### Trigger Index Sync

```python
# Para TRIGGERED pipeline type, sync manual
index.sync()

# Ou via SDK client:
vsc.get_index(endpoint_name="my-vs-endpoint", index_name="catalog.schema.my_index").sync()
```

### Scan All Index Entries

```python
# Recuperar todos os vetores (debugging/export)
scan_result = index.scan(num_results=100)
```

### Save and Sync Computed Embeddings (writeback)

```python
# Persiste embeddings gerados automaticamente em UC table: {index_name}_writeback_table
index = vsc.create_delta_sync_index(
    endpoint_name="my-vs-endpoint",
    index_name="catalog.schema.my_index",
    source_table_name="catalog.schema.documents",
    primary_key="id",
    pipeline_type="TRIGGERED",
    embedding_source_column="content",
    embedding_model_endpoint_name="databricks-gte-large-en",
    sync_computed_embeddings=True   # salva embeddings em UC table _writeback_table
)
```

## Reference Files

| Topic | File | Description |
|-------|------|-------------|
| Index Types | [index-types.md](index-types.md) | Detailed comparison of Delta Sync (managed/self-managed) vs Direct Access vs Full-Text |
| End-to-End RAG | [end-to-end-rag.md](end-to-end-rag.md) | Complete walkthrough: source table → endpoint → index → query → agent integration |
| Search Modes | [search-modes.md](search-modes.md) | When to use semantic (ANN) vs hybrid vs full-text search, decision guide |
| Operations | [troubleshooting-and-operations.md](troubleshooting-and-operations.md) | Monitoring, cost optimization, capacity planning, migration |

## CLI Quick Reference

```bash
# List endpoints
databricks vector-search endpoints list

# Create endpoint
databricks vector-search endpoints create \
    --name my-endpoint \
    --endpoint-type STANDARD

# List indexes on endpoint
databricks vector-search indexes list-indexes \
    --endpoint-name my-endpoint

# Get index status
databricks vector-search indexes get-index \
    --index-name catalog.schema.my_index

# Sync index (for TRIGGERED)
databricks vector-search indexes sync-index \
    --index-name catalog.schema.my_index

# Delete index
databricks vector-search indexes delete-index \
    --index-name catalog.schema.my_index
```

## Common Issues

| Issue | Solution |
|-------|----------|
| **Index sync slow** | Use Storage-Optimized endpoints (10-20x faster indexing) |
| **Query latency high** | Use Standard endpoint for <100ms latency |
| **filters_json not working** | Storage-Optimized usa SQL-like string via `filters`; Standard aceita dict |
| **Embedding dimension mismatch** | Verifique que query e index usam mesma dimensão |
| **Index not updating** | Cheque `pipeline_type`; use `index.sync()` para TRIGGERED |
| **Out of capacity** | Upgrade para Storage-Optimized (1B+ vectors) |
| **`query_vector` truncado por MCP tool** | MCP tool calls serializam arrays como JSON e podem truncar vetores grandes (ex.: 1024-dim). Prefira `query_text` (para managed embedding indexes) ou use SDK/CLI diretamente |
| **Storage-Optimized + `min_qps`** | `min_qps` só funciona em Standard; Storage-Optimized retorna erro |
| **Storage-Optimized + Continuous sync** | Continuous sync não é suportado; use TRIGGERED |
| **Embedding endpoint timeout** | Desative Scale-to-Zero no endpoint de embedding para evitar cold start no primeiro sync |
| **`_id` como nome de coluna** | Coluna `_id` é reservada; renomeie antes de criar o índice |
| **Self-managed → managed embeddings** | Não é possível converter; crie um novo índice e recompute embeddings |

## Embedding Models

Databricks disponibiliza modelos de embedding via Foundation Model APIs:

| Model | Dimensions | Context Window | Use Case |
|-------|------------|----------------|----------|
| `databricks-gte-large-en` | 1024 | 8192 tokens | English text, high quality (recomendado) |
| `databricks-bge-large-en` | 1024 | 512 tokens | English text, general purpose |
| `databricks-qwen3-embedding-0p6b` | até 1024 (configurável) | ~32K tokens | Multilingual (100+ langs), documentos longos |

**Recomendações por endpoint:**
- Standard: use `databricks-gte-large-en` com **provisioned throughput** serving endpoint.
- Storage-Optimized: use o model name diretamente (ex.: `databricks-gte-large-en`) — o endpoint usa `ai_query` com batch inference na ingestão. Opcionalmente, especifique `model_endpoint_name_for_query` com um endpoint de menor latência para queries.

```python
# Managed embeddings — padrão
index = vsc.create_delta_sync_index(
    ...,
    embedding_source_column="content",
    embedding_model_endpoint_name="databricks-gte-large-en",
    # Opcional: endpoint separado para queries (ex.: provisioned throughput)
    model_endpoint_name_for_query="my-gte-provisioned-endpoint"
)
```

> **Cosine similarity:** O Vector Search usa distância L2. Para usar cosine similarity, normalize seus vetores antes de indexá-los — quando normalizados, o ranking por L2 é equivalente ao de cosine.

## MCP Tools

The following MCP tools are available for managing Vector Search infrastructure. For a full end-to-end walkthrough, see [end-to-end-rag.md](end-to-end-rag.md).

### manage_vs_endpoint - Endpoint Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Create endpoint (STANDARD or STORAGE_OPTIMIZED). Idempotent | name |
| `get` | Get endpoint details | name |
| `list` | List all endpoints | (none) |
| `delete` | Delete endpoint (indexes must be deleted first) | name |

```python
# Create or update an endpoint
result = manage_vs_endpoint(action="create_or_update", name="my-vs-endpoint", endpoint_type="STANDARD")
# Returns {"name": "my-vs-endpoint", "endpoint_type": "STANDARD", "created": True}

# List all endpoints
endpoints = manage_vs_endpoint(action="list")

# Get specific endpoint
endpoint = manage_vs_endpoint(action="get", name="my-vs-endpoint")
```

### manage_vs_index - Index Management

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `create_or_update` | Create index. Idempotent, auto-triggers sync for DELTA_SYNC | name, endpoint_name, primary_key |
| `get` | Get index details | name |
| `list` | List indexes. Optional endpoint_name filter | (none) |
| `delete` | Delete index | name |

```python
# Create a Delta Sync index with managed embeddings
result = manage_vs_index(
    action="create_or_update",
    name="catalog.schema.my_index",
    endpoint_name="my-vs-endpoint",
    primary_key="id",
    index_type="DELTA_SYNC",
    delta_sync_index_spec={
        "source_table": "catalog.schema.docs",
        "embedding_source_columns": [{"name": "content", "embedding_model_endpoint_name": "databricks-gte-large-en"}],
        "pipeline_type": "TRIGGERED"
    }
)

# Get a specific index
index = manage_vs_index(action="get", name="catalog.schema.my_index")

# List all indexes on an endpoint
indexes = manage_vs_index(action="list", endpoint_name="my-vs-endpoint")

# List all indexes across all endpoints
all_indexes = manage_vs_index(action="list")
```

### query_vs_index - Query (Hot Path)

Query index with `query_text`, `query_vector`, or hybrid (`query_type="HYBRID"`), ou full-text keyword (`query_type="FULL_TEXT"`). Prefira `query_text` sobre `query_vector` — MCP tool calls podem truncar arrays grandes de embeddings (1024-dim).

```python
# Query an index
results = query_vs_index(
    index_name="catalog.schema.my_index",
    columns=["id", "content"],
    query_text="machine learning best practices",
    num_results=5
)

# Hybrid search (combines vector + keyword)
results = query_vs_index(
    index_name="catalog.schema.my_index",
    columns=["id", "content"],
    query_text="SPARK-12345 memory error",
    query_type="HYBRID",
    num_results=10
)

# Full-text keyword search (Beta)
results = query_vs_index(
    index_name="catalog.schema.my_index",
    columns=["id", "content"],
    query_text="executor memory error",
    query_type="FULL_TEXT",
    num_results=20
)
```

### manage_vs_data - Data Operations

| Action | Description | Required Params |
|--------|-------------|-----------------|
| `upsert` | Insert/update records | index_name, inputs_json |
| `delete` | Delete by primary key | index_name, primary_keys |
| `scan` | Scan index contents | index_name |
| `sync` | Trigger sync for TRIGGERED indexes | index_name |

```python
# Upsert data into a Direct Access index
manage_vs_data(
    action="upsert",
    index_name="catalog.schema.my_index",
    inputs_json=[{"id": "doc1", "content": "...", "embedding": [0.1, 0.2, ...]}]
)

# Trigger manual sync for a TRIGGERED pipeline index
manage_vs_data(action="sync", index_name="catalog.schema.my_index")

# Scan index contents
manage_vs_data(action="scan", index_name="catalog.schema.my_index", num_results=100)
```

## Notes

- **Storage-Optimized é mais novo** — melhor para a maioria dos casos, exceto quando você precisa de latência <100ms. Public Preview em abril/2026.
- **Delta Sync recomendado** — mais simples que Direct Access para a maioria dos cenários.
- **Hybrid search** — disponível para Delta Sync e Direct Access em ambos os tipos de endpoint.
- **Full-text search (Beta)** — `query_type="FULL_TEXT"` funciona em índices existentes (ambos endpoints); índice dedicado Full-Text apenas em Storage-Optimized + TRIGGERED.
- **`columns_to_sync` matters** — apenas colunas sincronizadas ficam disponíveis nos resultados de query; inclua todas as colunas necessárias. (Não suportado em Storage-Optimized.)
- **Filter syntax differs by endpoint** — Standard usa dict-format (`{"col": "val"}`), Storage-Optimized usa SQL-like string (`"col = 'val'"`).
- **`model_endpoint_name_for_query`** — parâmetro opcional para usar um modelo de embedding diferente em queries (ex.: endpoint de menor latência) vs ingestão.
- **`usage_policy_id`** substitui `budget_policy_id` (depreciado) para rastreio de custos em endpoints e índices.
- **Empty endpoints não cobram** — a partir de março/2026, cobrança só começa após criação do primeiro índice.
- **Management vs runtime** — MCP tools acima gerenciam o ciclo de vida; para tool-calling em agentes em runtime, use `VectorSearchRetrieverTool` ou o Databricks managed Vector Search MCP server (`/api/2.0/mcp/vector-search/{catalog}/{schema}/{index_name}`).
- **Service principals** — para produção, prefira service principals a PATs: podem ser até 100ms mais rápidos por query.

## Related Skills

- **[databricks-model-serving](../databricks-model-serving/SKILL.md)** - Deploy agents que usam VectorSearchRetrieverTool
- **[databricks-agent-bricks](../databricks-agent-bricks/SKILL.md)** - Knowledge Assistants usam RAG sobre documentos indexados
- **[databricks-unstructured-pdf-generation](../databricks-unstructured-pdf-generation/SKILL.md)** - Geração de documentos para indexar no Vector Search
- **[databricks-unity-catalog](../databricks-unity-catalog/SKILL.md)** - Gerenciamento dos catálogos e tabelas que alimentam Delta Sync indexes
- **[databricks-spark-declarative-pipelines](../databricks-spark-declarative-pipelines/SKILL.md)** - Construção de Delta tables usadas como fontes do Vector Search
