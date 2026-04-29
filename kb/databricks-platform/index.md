# KB: Databricks Platform

## Domínio
Databricks: clusters, Unity Catalog, Azure integration, runtime, compute policies, segurança, nomenclatura.

## Quando Consultar
- Configurar cluster (job vs interactive vs serverless)
- Unity Catalog: external locations, grants, naming
- Integrar Databricks com Azure (Entra ID, ADLS, Key Vault)
- Diagnóstico de cluster policy ou init script
- Control Plane vs Compute Plane dúvidas

## Arquivos de Referência Rápida
| Recurso | Arquivo |
|---------|---------|
| Cheatsheet | [quick-reference.md](quick-reference.md) |
| Tipos de cluster | [patterns/cluster-config.md](patterns/cluster-config.md) |
| Integração Azure | [patterns/azure-integration.md](patterns/azure-integration.md) |
| Unity Catalog setup | [patterns/unity-catalog-setup.md](patterns/unity-catalog-setup.md) |
| Params críticos | [specs/databricks-params.yaml](specs/databricks-params.yaml) |

## Agentes Relacionados
- `pipeline_architect` — deploy em produção
- `spark_expert` — otimização de jobs
- `governance_auditor` — segurança e LGPD

## Arquitetura: Control Plane vs Compute Plane
```
Control Plane (Microsoft)     Compute Plane (Customer)
├── Workspace UI              ├── DBFS / ADLS Gen2
├── REST API                  ├── Clusters (VMs)
├── Job scheduler             ├── Spark engines
└── UC metadata store         └── Data (customer data nunca sai)
```

## Última Atualização
2026-04-25
