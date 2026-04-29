# Unity Catalog Setup

## Hierarquia de Objetos
```
Metastore (por região — 1 conta Databricks)
├── Catalog: dev
│   ├── Schema: sales_latam
│   │   ├── Table: bronze_orders
│   │   ├── Table: silver_customers
│   │   └── View: gold_revenue_summary
│   └── Schema: finance_corp
├── Catalog: staging
└── Catalog: prod
```

## External Locations (Control de acesso a dados externos)
```sql
-- 1. Storage Credential
CREATE STORAGE CREDENTIAL adls_managed_id
USING AZURE_MANAGED_IDENTITY
CREDENTIAL (AZURE_SUBSCRIPTION_ID '<sub_id>', AZURE_RESOURCE_GROUP '<rg>');

-- 2. External Location
CREATE EXTERNAL LOCATION bronze_location
URL 'abfss://bronze@datalake.dfs.core.windows.net/'
WITH (STORAGE CREDENTIAL adls_managed_id);

-- 3. Validar acesso
VALIDATE STORAGE CREDENTIAL adls_managed_id;
```

## Nomenclatura Obrigatória
| Objeto | Padrão | Exemplo |
|--------|--------|---------|
| Catalog | `{env}` | `dev`, `prod` |
| Schema | `{domain}_{cluster}` | `sales_latam` |
| Table | `{layer}_{name}` | `bronze_orders` |
| Job | `{job}_{layer}_{purpose}` | `ingest_bronze_orders` |
| Pipeline | `pipe_{name}` | `pipe_sales` |
| Foreign Catalog | `ext_{source}_{env}` | `ext_sqldb_prod` |

## Foreign Catalogs (Lakehouse Federation)
Acesso federado a fontes externas sem mover dados:
```sql
CREATE CONNECTION sql_server TYPE SQLSERVER
OPTIONS (host '<host>', port '1433', user '<user>', password secret ('scope', 'key'));

CREATE FOREIGN CATALOG ext_crm_prod
USING CONNECTION sql_server
OPTIONS (database 'CRM');

-- Agora acessível via Unity Catalog
SELECT * FROM ext_crm_prod.dbo.customers LIMIT 10;
```

## AI/BI Genie (Unity Catalog)
- Genie Spaces: agentes analíticos com contexto de tabelas UC
- Requer: tabelas registradas no UC + permissões de leitura
- Usuários fazem perguntas em linguagem natural; Genie gera SQL e executa

## Grants e Permissões
```sql
-- Time de analytics: acesso read ao schema inteiro
GRANT USAGE ON CATALOG prod TO `data-analysts-group`;
GRANT USAGE ON SCHEMA prod.sales TO `data-analysts-group`;
GRANT SELECT ON ALL TABLES IN SCHEMA prod.sales TO `data-analysts-group`;

-- Service account para pipeline
GRANT ALL PRIVILEGES ON SCHEMA dev.bronze TO `svc-etl@tenant.com`;

-- Verificar permissões de um principal
SHOW GRANTS ON TABLE prod.sales.silver_customers;
```
