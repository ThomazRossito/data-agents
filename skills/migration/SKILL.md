---
updated_at: 2026-04-16
source: kb/migration/index.md
---

# Migration Expert — Skill Operacional

## Identidade

Playbook de migração de bancos relacionais (SQL Server, PostgreSQL) para Databricks ou
Microsoft Fabric com arquitetura Medallion.

## Protocolo KB-First

Antes de qualquer ação: consultar `kb/migration/index.md` para mapeamentos de tipos e
anti-padrões. Nunca assumir equivalência direta entre dialetos.

## Fluxo Padrão (5 Fases)

### Fase 1 — ASSESS

```python
# 1. Listar fontes disponíveis
migration_source_list_sources()

# 2. Diagnóstico de conexão
migration_source_diagnostics(source="NOME_FONTE")

# 3. Resumo do schema
migration_source_get_schema_summary(source="NOME_FONTE")

# 4. Inventário detalhado por schema
migration_source_count_tables_by_schema(source="NOME_FONTE")
migration_source_list_procedures(source="NOME_FONTE")
migration_source_list_functions(source="NOME_FONTE")
migration_source_list_views(source="NOME_FONTE")
```

**Output esperado:** relatório com totais de objetos por categoria e complexidade estimada.

### Fase 2 — ANALYZE

```python
# Para cada tabela prioritária:
migration_source_describe_table(schema="dbo", table="tb_clientes", source="ERP_PROD")
migration_source_get_table_ddl(schema="dbo", table="tb_clientes", source="ERP_PROD")

# Amostra para detectar PII e distribuição de dados
migration_source_sample_table(schema="dbo", table="tb_clientes", rows=20, source="ERP_PROD")
```

**Output esperado:** matriz de classificação (simples/médio/complexo/bloqueado) por objeto.

### Fase 3 — DESIGN (Medallion)

Estrutura padrão proposta:

```
Bronze  → bronze.<nome_original>              (ingestão bruta, sem transformação)
Silver  → silver.<dominio>_<entidade>         (tipagem canônica, deduplicação, validação)
Gold    → gold.<dominio>_<agregacao>          (star schema, pré-materialização)
```

**Pergunta obrigatória ao usuário:** "O destino é Databricks ou Microsoft Fabric?"

### Fase 4 — TRANSPILE

**Exemplo: SQL Server → Spark SQL (Databricks)**

```sql
-- Origem (SQL Server)
CREATE TABLE dbo.tb_clientes (
    id_cliente   INT IDENTITY(1,1) PRIMARY KEY,
    nome         NVARCHAR(200) NOT NULL,
    email        NVARCHAR(100),
    dt_criacao   DATETIME2 DEFAULT GETDATE(),
    saldo        MONEY NOT NULL,
    ativo        BIT DEFAULT 1,
    doc_federal  CHAR(14)
);

-- Destino Bronze (Spark SQL / Delta)
CREATE TABLE bronze.tb_clientes (
    id_cliente   INT,
    nome         STRING NOT NULL,
    email        STRING,
    dt_criacao   TIMESTAMP,
    saldo        DECIMAL(19,4) NOT NULL,
    ativo        BOOLEAN,
    doc_federal  STRING,
    _ingestion_date DATE,
    _source_system  STRING
)
USING DELTA
PARTITIONED BY (_ingestion_date);

-- Destino Silver (Spark SQL / Delta)
CREATE TABLE silver.erp_clientes (
    sk_cliente      BIGINT GENERATED ALWAYS AS IDENTITY,
    id_cliente_orig INT NOT NULL,
    nome            STRING NOT NULL,
    email           STRING,
    dt_criacao      TIMESTAMP,
    saldo           DECIMAL(19,4) NOT NULL,
    fl_ativo        BOOLEAN,
    doc_federal     STRING,
    _valid_from     TIMESTAMP,
    _valid_to       TIMESTAMP,
    _is_current     BOOLEAN
)
USING DELTA;
```

**Exemplo: PostgreSQL → T-SQL Fabric**

```sql
-- Origem (PostgreSQL)
CREATE TABLE public.orders (
    order_id    SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    total       NUMERIC(12,2),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    status      VARCHAR(20),
    metadata    JSONB
);

-- Destino Bronze (Fabric Lakehouse T-SQL)
CREATE TABLE bronze.orders (
    order_id    INT,
    customer_id INT,
    total       DECIMAL(12,2),
    created_at  DATETIMEOFFSET,
    status      NVARCHAR(20),
    metadata    NVARCHAR(MAX),
    _ingestion_date DATE,
    _source_system  NVARCHAR(50)
);

-- Destino Silver (Fabric Lakehouse T-SQL)
CREATE TABLE silver.sales_orders (
    sk_order        BIGINT IDENTITY(1,1),
    order_id_orig   INT NOT NULL,
    customer_id     INT,
    total           DECIMAL(12,2),
    created_at_utc  DATETIME2,
    status          NVARCHAR(20),
    metadata        NVARCHAR(MAX),
    _valid_from     DATETIME2,
    _valid_to       DATETIME2,
    _is_current     BIT DEFAULT 1
);
```

### Fase 5 — RECONCILE

```sql
-- Databricks: validação de contagem
SELECT
    'origem' AS fonte,
    COUNT(*) AS total
FROM migration_source  -- via MCP
UNION ALL
SELECT
    'destino' AS fonte,
    COUNT(*) AS total
FROM silver.erp_clientes;

-- Fabric: mesma lógica via fabric_sql_execute
```

**Critérios de aprovação:** divergência < 0.1% em contagens, soma de campos monetários ±0.01%.

## Regras de Isolamento de Plataforma

- **NUNCA** misturar tools Databricks com Fabric na mesma execução sem declarar explicitamente
- Se o usuário não especificou o destino → perguntar antes de gerar qualquer DDL
- Gerar DDL separado para cada destino quando ambos forem solicitados

## Escalação

| Situação | Agente |
|----------|--------|
| PII detectado (CPF, e-mail, cartão) | `governance-auditor` |
| Pipeline ETL de ingestão | `pipeline-architect` |
| Validação de qualidade pós-migração | `data-quality-steward` |
| Queries complexas na silver/gold | `sql-expert` |
| Jobs PySpark de ingestão | `spark-expert` |

## Anti-Padrões (resumo rápido)

- Nunca `FLOAT` para dinheiro → `DECIMAL(19,4)`
- Nunca copiar `IDENTITY`/`SERIAL` como dado → gerar surrogate key
- Nunca criar FKs em Delta Lake → documentar linhagem
- Nunca migrar direto para Gold → sempre Bronze → Silver → Gold
- Nunca `SELECT *` em jobs de ingestão → listar colunas
