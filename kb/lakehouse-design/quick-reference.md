# Lakehouse Design — Quick Reference

## Decision Matrix: Databricks vs Fabric

| Critério | Databricks | Microsoft Fabric |
|---|---|---|
| Compute principal | Spark clusters (Job/Interactive/Serverless) | Spark + Fabric Compute |
| Armazenamento | ADLS Gen2 + Delta Lake | OneLake (ADLS sob os panos) |
| Governança | Unity Catalog (metastore → catalog → schema → table) | Workspace + Fabric Admin |
| Licença | DBU por cluster | CU por capacidade (F2–F1024) |
| CI/CD nativo | DABs (bundle.yml) | Fabric REST API + Git Integration |
| Multi-cloud | Sim (AWS, Azure, GCP) | Azure only |
| Direct Lake | Não (usa Import/DirectQuery no Power BI) | Sim (modo nativo no Power BI) |
| Melhor para | Engenharia pesada + ML + streaming | Análise BI + OneLake centralizado |

## Checklist de Implantação (9 fases)

1. **Requisitos** — volumes, SLAs, fontes, consumidores downstream
2. **Plataforma** — Databricks ou Fabric (ou híbrido)
3. **Camadas Medallion** — Bronze (raw), Silver (curated), Gold (serving)
4. **Governança** — Unity Catalog / Fabric workspace, RBAC, PII scanning
5. **Ingestão** — batch (COPY INTO / ADF) ou streaming (Auto Loader / Eventstream)
6. **Transformação** — PySpark Medallion pipeline ou Dataflow Gen2
7. **Qualidade** — DQX / Great Expectations, expectations por camada
8. **CI/CD** — DABs (Databricks) ou Fabric Git Integration
9. **Observabilidade** — Delta logs, job metrics, custo (DBU/CU)

## Tiers de Capacidade Fabric

| SKU | CU (capacity units) | Spark vCores | Uso típico |
|---|---|---|---|
| F2 | 2 | 4 | Dev / sandbox |
| F4 | 4 | 8 | Dev / testes |
| F8 | 8 | 16 | Workloads pequenos |
| F16 | 16 | 32 | Prod pequeno |
| F32 | 32 | 64 | Prod médio |
| F64 | 64 | 128 | Prod grande |

## Naming Convention Lakehouse

### Databricks Unity Catalog
```
catalog: <env>                          # prod, dev, test
schema:  <domain>_<cluster>             # sales_bronze, finance_silver
table:   <entity>_<suffix>              # order_raw, customer_curated
```

### Fabric
```
workspace: <env>-<domain>               # prod-finance, dev-sales
lakehouse: <domain>_lh                  # finance_lh, sales_lh
table:     <layer>_<entity>             # bronze_order, gold_customer
```

## Particionamento Recomendado

| Tabela | Estratégia | Coluna(s) |
|---|---|---|
| Bronze (raw) | Por data de ingestão | `ingestion_date` |
| Silver | Por data de evento | `event_date` |
| Gold | Por dimensão de consulta | `region`, `year_month` |
| Streaming | Por hora | `event_hour` |

## External Locations (Databricks)
```
1. Criar Storage Credential (Managed Identity ou Service Principal)
2. CREATE EXTERNAL LOCATION nome URL 'abfss://...' WITH (STORAGE CREDENTIAL <nome>)
3. GRANT READ FILES, WRITE FILES ON EXTERNAL LOCATION nome TO <grupo>
```
