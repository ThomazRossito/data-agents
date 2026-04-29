# Databricks Platform Quick Reference

## Tipos de Cluster
| Tipo | Uso | Billing | Auto-terminate |
|------|-----|---------|----------------|
| **Job Cluster** | Task de job (single-use) | Por job | Sim (automático) |
| **Interactive** | Notebooks, exploração | Por hora | Configurável |
| **Serverless** | Jobs/SQL sem cluster gerenciado | Por DBU/s | N/A |
| **Single Node** | Dev local, small jobs | Por hora | Sim |

## Unity Catalog — Hierarquia
```
Metastore (1 por região)
└── Catalog (dev / staging / prod)
    └── Schema (domínio: vendas, financeiro)
        ├── Table (Delta managed/external)
        ├── View
        └── Function
```

## Segurança — Layers
| Layer | Mecanismo |
|-------|-----------|
| **Autenticação** | Entra ID (AAD), PAT tokens, service principals |
| **Autorização** | UC GRANT statements, workspace permissions |
| **Row-Level Security** | Dynamic views + `current_user()` |
| **Column-Level Security** | Column masks (UC preview) |
| **Network** | Private Link, IP ACL, VNet injection |
| **Secrets** | Azure Key Vault via `dbutils.secrets` |

## Runtime Matrix (Databricks)
| Runtime | Spark | Python | Melhor Para |
|---------|-------|--------|------------|
| 14.x LTS | 3.5 | 3.11 | Produção estável |
| 15.x | 3.5 | 3.12 | Preview novidades |
| ML 14.x | 3.5 | 3.11 | ML workloads |
| Serverless | Gerenciado | Gerenciado | SQL + jobs leves |

## Nomenclatura Padrão
```
Catalog:     {env}                          → dev, staging, prod
Schema:      {domain}_{cluster}             → sales_latam, finance_corp
Table:       {layer}_{name}                 → bronze_orders, silver_customers
Job:         {job}_{layer}_{purpose}        → ingest_bronze_orders
Pipeline:    pipe_{name}                    → pipe_sales_medallion
```

## Grants Essenciais
```sql
-- Conceder acesso a tabla
GRANT SELECT ON TABLE prod.sales.silver_orders TO `data_analyst`;

-- Conceder schema inteiro
GRANT USAGE, SELECT ON SCHEMA prod.sales TO `data_analyst`;

-- Service Account para job
GRANT ALL PRIVILEGES ON CATALOG dev TO `svc-databricks-dev@tenant.com`;
```
