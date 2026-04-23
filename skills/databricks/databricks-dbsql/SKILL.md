---
name: databricks-dbsql
description: >-
  Databricks SQL (DBSQL) advanced features and SQL warehouse capabilities.
  This skill MUST be invoked when the user mentions: "DBSQL", "Databricks SQL",
  "SQL warehouse", "SQL scripting", "stored procedure", "CALL procedure",
  "materialized view", "CREATE MATERIALIZED VIEW", "pipe syntax", "|>",
  "geospatial", "H3", "ST_", "spatial SQL", "collation", "COLLATE",
  "ai_query", "ai_classify", "ai_extract", "ai_gen", "AI function",
  "ai_parse_document", "http_request", "remote_query", "read_files",
  "Lakehouse Federation", "recursive CTE", "WITH RECURSIVE",
  "multi-statement transaction", "BEGIN ATOMIC", "BEGIN TRANSACTION",
  "temp table", "temporary view", "pipe operator".
  SHOULD also invoke when the user asks about SQL best practices, data modeling
  patterns, or advanced SQL features on Databricks.
updated_at: 2026-04-23
source: web_search
---

# Databricks SQL (DBSQL) - Advanced Features

## Quick Reference

| Feature | Key Syntax | Since | Status | Reference |
|---------|-----------|-------|--------|-----------|
| SQL Scripting | `BEGIN...END`, `DECLARE`, `IF/WHILE/FOR` | DBR 16.3+ / DBSQL 2025.15 | **GA** | [sql-scripting.md](sql-scripting.md) |
| Stored Procedures | `CREATE PROCEDURE`, `CALL` | DBR 17.0+ / DBSQL 2025.20 | **GA** | [sql-scripting.md](sql-scripting.md) |
| Recursive CTEs | `WITH RECURSIVE`, `LIMIT ALL` | DBR 17.0+ / DBSQL 2025.20 | **GA** | [sql-scripting.md](sql-scripting.md) |
| Transactions (non-interactive) | `BEGIN ATOMIC...END` | DBR 18.0+ / all warehouses | **Public Preview** | [sql-scripting.md](sql-scripting.md) |
| Transactions (interactive) | `BEGIN TRANSACTION`, `COMMIT`, `ROLLBACK` | All SQL warehouses | **Public Preview** | [sql-scripting.md](sql-scripting.md) |
| Materialized Views | `CREATE MATERIALIZED VIEW` | Pro/Serverless | GA | [materialized-views-pipes.md](materialized-views-pipes.md) |
| Temp Tables | `CREATE TEMPORARY TABLE` | All | **GA** | [materialized-views-pipes.md](materialized-views-pipes.md) |
| Pipe Syntax | `\|>` operator (or `\|` on DBR 18.0+) | DBR 16.2+ | GA | [materialized-views-pipes.md](materialized-views-pipes.md) |
| Geospatial (H3) | `h3_longlatash3()`, `h3_polyfillash3()` | DBR 11.2+ | GA | [geospatial-collations.md](geospatial-collations.md) |
| Geospatial (ST) | `ST_Point()`, `ST_Contains()`, `ST_ExteriorRing()`, 80+ funcs | DBR 16.0+ | GA | [geospatial-collations.md](geospatial-collations.md) |
| Collations | `COLLATE`, `DEFAULT COLLATION`, `UTF8_LCASE`, locale-aware | DBR 16.1+ | GA | [geospatial-collations.md](geospatial-collations.md) |
| AI Functions | `ai_query()`, `ai_classify()`, `ai_parse_document()`, 13+ funcs | DBR 15.1+ | GA/Beta | [ai-functions.md](ai-functions.md) |
| http_request | `http_request(conn, ...)` | Pro/Serverless | GA | [ai-functions.md](ai-functions.md) |
| remote_query | `SELECT * FROM remote_query(...)` | Pro/Serverless | GA | [ai-functions.md](ai-functions.md) |
| read_files | `SELECT * FROM read_files(...)` | All | GA | [ai-functions.md](ai-functions.md) |
| Data Modeling | Star schema, Liquid Clustering | All | GA | [best-practices.md](best-practices.md) |

---

## Common Patterns

### SQL Scripting - Procedural ETL

> ⚠️ Breaking change em DBSQL 2026 (GA): SQL Scripting é agora **Generally Available**. A keyword `VAR` é aceita como sinônimo de `VARIABLE` para declaração de variáveis. `DECLARE` agora aceita múltiplas variáveis do mesmo tipo em uma só declaração.

```sql
BEGIN
  -- Múltiplas variáveis na mesma DECLARE (novo desde DBSQL 2025.30)
  DECLARE v_count INT, v_status STRING DEFAULT 'pending';

  SET v_count = (SELECT COUNT(*) FROM catalog.schema.raw_orders WHERE status = 'new');

  IF v_count > 0 THEN
    INSERT INTO catalog.schema.processed_orders
    SELECT *, current_timestamp() AS processed_at
    FROM catalog.schema.raw_orders
    WHERE status = 'new';

    SET v_status = 'completed';
  ELSE
    SET v_status = 'skipped';
  END IF;

  SELECT v_status AS result, v_count AS rows_processed;
END
```

### Stored Procedure with Error Handling

> ⚠️ Breaking change em DBSQL 2025.20 (GA): Stored Procedures agora são **Generally Available** e governados pelo Unity Catalog. Nested e recursive procedure calls são suportados.

```sql
CREATE OR REPLACE PROCEDURE catalog.schema.upsert_customers(
  IN p_source STRING,
  OUT p_rows_affected INT
)
LANGUAGE SQL
SQL SECURITY INVOKER
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    SET p_rows_affected = -1;
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = concat('Upsert failed for source: ', p_source);
  END;

  MERGE INTO catalog.schema.dim_customer AS t
  USING (SELECT * FROM identifier(p_source)) AS s
  ON t.customer_id = s.customer_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *;

  SET p_rows_affected = (SELECT COUNT(*) FROM identifier(p_source));
END;

-- Invoke:
CALL catalog.schema.upsert_customers('catalog.schema.staging_customers', ?);
```

### Transactions - Multi-Statement Atomic Operations

> ⚠️ Novo em DBSQL / DBR 18.0 (Public Preview, março 2026): Transactions são agora multi-statement e multi-table. Existem dois modos: `BEGIN ATOMIC` (non-interactive, commit/rollback automático, requer DBR 18.0+ para clusters) e `BEGIN TRANSACTION` (interactive, commit/rollback manual, SQL warehouses apenas).

```sql
-- Modo não-interativo: BEGIN ATOMIC (recomendado para ETL/jobs)
-- Suportado em: SQL warehouses, serverless compute, clusters DBR 18.0+
BEGIN ATOMIC
  -- Limpa staging
  DELETE FROM catalog.schema.staging_orders WHERE load_date = current_date();

  -- Carrega novos dados
  INSERT INTO catalog.schema.staging_orders
  SELECT *, current_date() AS load_date
  FROM catalog.schema.raw_orders
  WHERE order_date = current_date() - INTERVAL 1 DAY;

  -- Valida (falha → rollback automático de tudo)
  IF (SELECT COUNT(*) FROM catalog.schema.staging_orders WHERE load_date = current_date()) = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'No orders loaded for yesterday';
  END IF;

  -- Merge em produção
  MERGE INTO catalog.schema.fact_orders AS t
  USING catalog.schema.staging_orders AS s ON t.order_id = s.order_id
  WHEN MATCHED THEN UPDATE SET *
  WHEN NOT MATCHED THEN INSERT *;
END;

-- Modo interativo: BEGIN TRANSACTION (SQL warehouses apenas)
BEGIN TRANSACTION;
  UPDATE catalog.schema.accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE catalog.schema.accounts SET balance = balance + 100 WHERE id = 2;
  INSERT INTO catalog.schema.audit_log VALUES (1, 2, 100, current_timestamp());
COMMIT;
```

### Materialized View with Scheduled Refresh

```sql
CREATE OR REPLACE MATERIALIZED VIEW catalog.schema.daily_revenue
  CLUSTER BY (order_date)
  SCHEDULE EVERY 1 HOUR
  COMMENT 'Hourly-refreshed daily revenue by region'
AS SELECT
    order_date,
    region,
    SUM(amount) AS total_revenue,
    COUNT(DISTINCT customer_id) AS unique_customers
FROM catalog.schema.fact_orders
JOIN catalog.schema.dim_store USING (store_id)
GROUP BY order_date, region;
```

### Pipe Syntax - Readable Transformations

> ⚠️ Atualização de versão: Pipe syntax disponível desde DBR **16.2** (a skill anterior mencionava 16.1). A partir do DBR 18.0, o token `|` (pipe único) pode ser usado como alternativa ao `|>`.

```sql
-- Pipe syntax com AGGREGATE (operador correto — não usar SUM() dentro de SELECT com pipes)
FROM catalog.schema.fact_orders
  |> WHERE order_date >= current_date() - INTERVAL 30 DAYS
  |> AGGREGATE SUM(amount) AS total, COUNT(*) AS cnt GROUP BY region, product_category
  |> WHERE total > 10000
  |> ORDER BY total DESC
  |> LIMIT 20;

-- Operadores adicionais: EXTEND (adiciona colunas), SET (substitui coluna), DROP (remove coluna)
FROM catalog.schema.fact_orders
  |> WHERE order_date = current_date()
  |> EXTEND amount * 0.1 AS tax_amount          -- adiciona coluna sem remover existentes
  |> SET amount = amount + tax_amount            -- substitui valor de coluna
  |> DROP tax_amount                             -- remove coluna intermediária
  |> ORDER BY amount DESC
  |> LIMIT 100;

-- DBR 18.0+: pipe único | como alternativa a |>
FROM catalog.schema.fact_orders
  | WHERE status = 'completed'
  | AGGREGATE COUNT(*) AS cnt GROUP BY region
  | ORDER BY cnt DESC;
```

### AI Functions - Enrich Data with LLMs

> ⚠️ Atualização de API em 2025/2026: `ai_classify()` recebe agora `labels` como STRING JSON (array ou objeto com descrições) e retorna `VARIANT`. O parâmetro `ARRAY(...)` (v1) ainda funciona, mas a nova assinatura com JSON string (v2) é recomendada. Nova função `ai_parse_document()` disponível em beta.

```sql
-- ai_classify: nova assinatura com labels como JSON string e opções
SELECT
  ticket_id,
  description,
  ai_classify(
    description,
    '["billing", "technical", "account", "feature_request"]',
    MAP('instructions', 'Classify customer support tickets by topic.')
  ) AS category,
  ai_analyze_sentiment(description) AS sentiment
FROM catalog.schema.support_tickets
LIMIT 100;

-- ai_classify com labels descritivos (JSON object) para maior precisão
SELECT
  ticket_id,
  ai_classify(
    description,
    '{"billing_error": "Payment, invoice, or refund issues",
      "product_defect": "Any malfunction, bug, or breakage",
      "account_issue": "Login failures, password resets",
      "feature_request": "Customer suggestions for improvements"}'
  ) AS category
FROM catalog.schema.support_tickets;

-- ai_parse_document (Beta): converte PDFs/documentos não-estruturados em tabelas
-- Combinável com ai_classify via VARIANT
WITH parsed_docs AS (
  SELECT path,
    ai_parse_document(content, MAP('version', '2.0')) AS parsed_content
  FROM READ_FILES('/Volumes/catalog/schema/contracts/', format => 'binaryFile')
)
SELECT
  path,
  ai_classify(
    parsed_content,
    '["nda", "service_agreement", "purchase_order", "amendment"]',
    MAP('instructions', 'Classify legal documents by type.')
  ) AS doc_type
FROM parsed_docs;

-- Extract entities from text
SELECT
  doc_id,
  ai_extract(content, ARRAY('person_name', 'company', 'dollar_amount')) AS entities
FROM catalog.schema.contracts;

-- General-purpose AI query com structured output
SELECT ai_query(
  'databricks-meta-llama-3-3-70b-instruct',
  concat('Summarize this customer feedback in JSON with keys: topic, sentiment, action_items. Feedback: ', feedback),
  returnType => 'STRUCT<topic STRING, sentiment STRING, action_items ARRAY<STRING>>'
) AS analysis
FROM catalog.schema.customer_feedback
LIMIT 50;
```

### Geospatial - Proximity Search with H3

> ⚠️ Novo em DBSQL 2025.30: função `ST_ExteriorRing()` adicionada ao conjunto de funções ST (extrai o anel exterior de um polígono como linestring).

```sql
-- Find stores within 5km of each customer using H3 indexing
WITH customer_h3 AS (
  SELECT *, h3_longlatash3(longitude, latitude, 7) AS h3_cell
  FROM catalog.schema.customers
),
store_h3 AS (
  SELECT *, h3_longlatash3(longitude, latitude, 7) AS h3_cell
  FROM catalog.schema.stores
)
SELECT
  c.customer_id,
  s.store_id,
  ST_Distance(
    ST_Point(c.longitude, c.latitude),
    ST_Point(s.longitude, s.latitude)
  ) AS distance_m
FROM customer_h3 c
JOIN store_h3 s ON h3_ischildof(c.h3_cell, h3_toparent(s.h3_cell, 5))
WHERE ST_Distance(
  ST_Point(c.longitude, c.latitude),
  ST_Point(s.longitude, s.latitude)
) < 5000;

-- ST_ExteriorRing: extrair anel exterior de polígono (novo em DBSQL 2025.30)
SELECT
  zone_id,
  ST_ExteriorRing(boundary_polygon) AS boundary_line
FROM catalog.schema.delivery_zones;
```

### Collation - Case-Insensitive Search

> ⚠️ Novo em DBSQL 2025.15: é possível definir `DEFAULT COLLATION` no nível de tabela/view inteira (não apenas por coluna). Novo em DBSQL 2025.30: `LIKE` agora funciona em colunas com collation (`UTF8_Binary`, `UTF8_Binary_RTRIM`, `UTF8_LCASE`, `UTF8_LCASE_RTRIM`). Novo em DBSQL 2025.20: `DEFAULT COLLATION` suportado também em `CREATE FUNCTION`.

```sql
-- Create table com collation default no nível da tabela (novo em DBSQL 2025.15)
CREATE TABLE catalog.schema.products
  DEFAULT COLLATION UTF8_LCASE
(
  product_id BIGINT GENERATED ALWAYS AS IDENTITY,
  name       STRING,   -- herda UTF8_LCASE da tabela
  category   STRING,   -- herda UTF8_LCASE da tabela
  price      DECIMAL(10, 2)
);

-- Ou por coluna (forma anterior, ainda válida)
CREATE TABLE catalog.schema.products_v2 (
  product_id BIGINT GENERATED ALWAYS AS IDENTITY,
  name       STRING COLLATE UTF8_LCASE,
  category   STRING COLLATE UTF8_LCASE,
  price      DECIMAL(10, 2)
);

-- Queries automaticamente case-insensitive (no LOWER() needed)
SELECT * FROM catalog.schema.products
WHERE name = 'MacBook Pro';       -- matches 'macbook pro', 'MACBOOK PRO', etc.

-- LIKE agora funciona com collation (novo em DBSQL 2025.30)
SELECT * FROM catalog.schema.products
WHERE name LIKE '%macbook%';      -- case-insensitive LIKE
```

### http_request - Call External APIs

```sql
-- Set up connection first (one-time)
CREATE CONNECTION my_api_conn
  TYPE HTTP
  OPTIONS (host 'https://api.example.com', bearer_token secret('scope', 'token'));

-- Call API from SQL
SELECT
  order_id,
  http_request(
    conn => 'my_api_conn',
    method => 'POST',
    path => '/v1/validate',
    json => to_json(named_struct('order_id', order_id, 'amount', amount))
  ).text AS api_response
FROM catalog.schema.orders
WHERE needs_validation = true;
```

### read_files - Ingest Raw Files

```sql
-- Read JSON files from a Volume with schema hints
SELECT *
FROM read_files(
  '/Volumes/catalog/schema/raw/events/',
  format => 'json',
  schemaHints => 'event_id STRING, timestamp TIMESTAMP, payload MAP<STRING, STRING>',
  pathGlobFilter => '*.json',
  recursiveFileLookup => true
);

-- Read CSV with options
SELECT *
FROM read_files(
  '/Volumes/catalog/schema/raw/sales/',
  format => 'csv',
  header => true,
  delimiter => '|',
  dateFormat => 'yyyy-MM-dd',
  schema => 'sale_id INT, sale_date DATE, amount DECIMAL(10,2), store STRING'
);
```

### Recursive CTE - Hierarchy Traversal

> ⚠️ Novo em DBSQL 2025.35: `LIMIT ALL` pode ser usado para remover a restrição de tamanho total em CTEs recursivas.

```sql
WITH RECURSIVE org_chart AS (
  -- Anchor: top-level managers
  SELECT employee_id, name, manager_id, 0 AS depth, ARRAY(name) AS path
  FROM catalog.schema.employees
  WHERE manager_id IS NULL

  UNION ALL

  -- Recursive: direct reports
  SELECT e.employee_id, e.name, e.manager_id, o.depth + 1, array_append(o.path, e.name)
  FROM catalog.schema.employees e
  JOIN org_chart o ON e.manager_id = o.employee_id
  WHERE o.depth < 10  -- safety limit (ou use LIMIT ALL para remover restrição de tamanho)
)
SELECT * FROM org_chart ORDER BY depth, name;
```

### remote_query - Federated Queries

```sql
-- Query PostgreSQL via Lakehouse Federation
SELECT *
FROM remote_query(
  'my_postgres_connection',
  database => 'my_database',
  query    => 'SELECT customer_id, email, created_at FROM customers WHERE active = true'
);
```

---

## Reference Files

Load these for detailed syntax, full parameter lists, and advanced patterns:

| File | Contents | When to Read |
|------|----------|--------------|
| [sql-scripting.md](sql-scripting.md) | SQL Scripting (GA), Stored Procedures (GA), Recursive CTEs, Transactions (Public Preview) | User needs procedural SQL, error handling, loops, dynamic SQL, transactions |
| [materialized-views-pipes.md](materialized-views-pipes.md) | Materialized Views, Temp Tables/Views (GA), Pipe Syntax (DBR 16.2+, `\|` single pipe em DBR 18.0+) | User needs MVs, refresh scheduling, temp objects, pipe operator |
| [geospatial-collations.md](geospatial-collations.md) | 39 H3 functions, 80+ ST functions (incl. `ST_ExteriorRing`), Collation types, table-level DEFAULT COLLATION, LIKE com collation | User needs spatial analysis, H3 indexing, case/accent handling |
| [ai-functions.md](ai-functions.md) | 13+ AI functions (incl. `ai_parse_document` beta), nova assinatura `ai_classify` com JSON labels, http_request, remote_query, read_files | User needs AI enrichment, API calls, federation, file ingestion, document parsing |
| [best-practices.md](best-practices.md) | Data modeling, performance, Liquid Clustering, anti-patterns | User needs architecture guidance, optimization, or modeling advice |

---

## Key Guidelines

- **Always use Serverless SQL warehouses** for AI functions, MVs, and http_request
- **SQL Scripting e Stored Procedures são GA** — use em produção; `VAR` é sinônimo de `VARIABLE`
- **Transactions (`BEGIN ATOMIC`) são Public Preview** — use para ETL atômico em DBR 18.0+; preferir modo `BEGIN ATOMIC` (não-interativo) sobre `BEGIN TRANSACTION` em jobs/pipelines
- **Use `LIMIT` durante desenvolvimento** com AI functions para controlar custos; em produção, submeta o dataset completo em uma única query (AI Functions gerenciam paralelismo automaticamente)
- **`ai_classify` v2**: prefira labels como JSON string com `MAP('instructions', '...')` para maior precisão; `ARRAY(...)` (v1) ainda funciona mas é legado
- **`ai_parse_document`**: use para ingerir PDFs/documentos não-estruturados diretamente em SQL (beta); combina com `ai_classify` via `VARIANT`
- **Prefer Liquid Clustering over partitioning** para novas tabelas (1-4 keys max)
- **Use `CLUSTER BY AUTO`** quando incerto sobre clustering keys
- **Star schema in Gold layer** para BI; OBT aceitável em Silver
- **Define PK/FK constraints** em modelos dimensionais para otimização de queries
- **Use `DEFAULT COLLATION UTF8_LCASE`** no nível da tabela para simplificar colunas case-insensitive; `LIKE` agora funciona com collation (DBSQL 2025.30+)
- **Pipe syntax**: use `AGGREGATE` para agrupamentos em pipes (não `SELECT` com funções de agregação); `EXTEND`/`SET`/`DROP` eliminam subqueries para transformações coluna a coluna
- **Use MCP tools** (`execute_sql`, `execute_sql_multi`) para testar e validar todo SQL antes de deploy
