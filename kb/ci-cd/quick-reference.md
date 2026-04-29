# CI/CD Quick Reference

## DABs (Databricks Asset Bundles) — Comandos
| Comando | Ação |
|---------|------|
| `databricks bundle validate` | Valida databricks.yml localmente |
| `databricks bundle deploy -t dev` | Deploy para target dev |
| `databricks bundle deploy -t prod` | Deploy para target prod |
| `databricks bundle run <job>` | Executa job após deploy |
| `databricks bundle destroy -t dev` | Remove recursos do target |
| `databricks bundle generate job <id>` | Importa job existente para bundle |

## Branch Strategy Recomendada
```
feature/* → dev (CI automático)
           ↓ PR + review
test/staging → staging (CI + smoke test)
           ↓ PR aprovado
main → prod (deploy manual ou aprovação)
```

## Service Principal — Setup Mínimo
1. Registrar SP no Azure Entra ID
2. Adicionar SP como Contributor no workspace Databricks
3. Para Fabric: adicionar SP como Member no workspace
4. Configurar Client Secret no Key Vault
5. Referenciar nas variáveis do pipeline CI/CD

## Fabric REST API — Endpoints Principais
| Ação | Endpoint |
|------|----------|
| Conectar workspace ao Git | `POST /workspaces/{id}/git/connect` |
| Atualizar credenciais Git | `PATCH /workspaces/{id}/git/gitCredentials` |
| Commit e push | `POST /workspaces/{id}/git/commitToGit` |
| Pull do repositório | `POST /workspaces/{id}/git/updateFromGit` |
| Deploy item | `POST /workspaces/{id}/items/{id}/deploy` |

## Variáveis de Ambiente para CI/CD
```bash
DATABRICKS_HOST=https://<workspace>.azuredatabricks.net
DATABRICKS_TOKEN=<PAT ou SP token>
AZURE_CLIENT_ID=<SP client id>
AZURE_CLIENT_SECRET=<SP secret>
AZURE_TENANT_ID=<tenant id>
```
