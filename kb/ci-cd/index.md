# KB: CI/CD

## Domínio
CI/CD para Databricks (Asset Bundles/DABs) e Microsoft Fabric (Git integration, REST API). Branch strategies, service principals, Azure DevOps.

## Quando Consultar
- Criar ou configurar `databricks.yml` (DABs)
- Integrar Fabric workspace com Git (Azure DevOps/GitHub)
- Configurar Service Principal para CI/CD automatizado
- Azure DevOps pipeline para deploy multi-ambiente
- Branch strategy: dev/staging/prod

## Arquivos de Referência Rápida
| Recurso | Arquivo |
|---------|---------|
| Cheatsheet DABs + Fabric | [quick-reference.md](quick-reference.md) |
| Databricks Asset Bundles | [patterns/databricks-asset-bundles.md](patterns/databricks-asset-bundles.md) |
| Fabric CI/CD | [patterns/fabric-cicd.md](patterns/fabric-cicd.md) |
| Azure DevOps pipeline | [patterns/azure-devops-pipeline.md](patterns/azure-devops-pipeline.md) |
| Bundle config template | [specs/bundle-config.yaml](specs/bundle-config.yaml) |

## Agentes Relacionados
- `devops_engineer` — agente primário
- `pipeline_architect` — deploy em produção
- `spark_expert` — code em jobs/pipelines

## Última Atualização
2026-04-25
