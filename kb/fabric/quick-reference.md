# Fabric Quick Reference

## Workspace Items
| Item | Tipo | Computa | Armazena |
|------|------|---------|----------|
| Lakehouse | Storage + Compute | Spark, SQL | OneLake (Delta) |
| Warehouse | SQL-first | DWH engine | OneLake (Delta) |
| Notebook | Compute | Spark | — |
| Pipeline | Orchestration | — | — |
| Dataflow Gen2 | ETL | Dataflow engine | OneLake |
| Semantic Model | Semantic | Analysis Services | — |
| Eventstream | Streaming | KQL | KQL DB / Lakehouse |
| KQL Database | Real-time | KQL Engine | OneLake |

## F-SKU Tiers (Capacity Units)
| SKU | CU | RAM | Uso Típico |
|-----|-----|-----|-----------|
| F2 | 2 | 16 GB | Dev/sandbox |
| F4 | 4 | 32 GB | Pequenas cargas |
| F8 | 8 | 64 GB | Médias cargas |
| F16 | 16 | 128 GB | Produção média |
| F32 | 32 | 256 GB | Produção |
| F64 | 64 | 512 GB | Enterprise |

## Modos de Compute
| Modo | Quando Usar |
|------|------------|
| Spark (Notebook/PySpark) | Transformações pesadas, ML, DLT |
| SQL Endpoint | Queries analíticas ad-hoc no Lakehouse |
| Warehouse | Workloads DWH tradicionais com T-SQL |
| Serverless | Dataflow Gen2, SQL rápido sem cluster |
| Direct Lake | Semantic models sem import/DirectQuery |

## Tipos de Shortcut
| Tipo | Origem | Nota |
|------|--------|------|
| ADLS Gen2 | Azure Data Lake | Mais comum |
| S3 | AWS S3 | Cross-cloud |
| GCS | Google Cloud Storage | Cross-cloud |
| OneLake | Outro workspace Fabric | Internal shortcut |
| On-prem | Via Gateway | Precisa de gateway |

## Decision Matrix: Lakehouse vs Warehouse
| Critério | Lakehouse | Warehouse |
|----------|-----------|-----------|
| Linguagem | Spark SQL + Python | T-SQL |
| Formato | Delta Parquet | Delta Parquet |
| Schema enforcement | Opt-in | Strict DDL |
| ACID | Delta native | DWH engine |
| Melhor para | Pipelines ETL/ELT, ML | Relatórios, DWH clássico |

## Comandos Úteis (Python/SDK)
```python
# Listar items do workspace via API
import requests
headers = {"Authorization": f"Bearer {token}"}
r = requests.get(f"https://api.fabric.microsoft.com/v1/workspaces/{ws_id}/items", headers=headers)

# Git integration via Fabric API
PATCH https://api.fabric.microsoft.com/v1/workspaces/{ws_id}/git/gitCredentials
```
