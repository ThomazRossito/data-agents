# Fabric CI/CD

## Visão Geral
Fabric integra com Git (Azure DevOps/GitHub) por workspace, com deploy automatizado via REST API.

## Setup: Service Principal no Fabric
```
1. Registrar SP no Azure Entra ID
   az ad sp create-for-rbac --name "svc-fabric-cicd"

2. Adicionar SP ao workspace Fabric como Member (mínimo)
   Fabric Portal → Workspace Settings → Members → Add SP

3. Conceder permissões por item (Lakehouse, Pipeline, Notebook)
   API: POST /workspaces/{id}/items/{itemId}/permissions

4. Habilitar SP na tenant admin
   Fabric Admin Portal → Developer Settings → Service Principals can use Fabric APIs = ON
```

## Conectar Workspace ao Git
```bash
# Via Fabric REST API
curl -X POST "https://api.fabric.microsoft.com/v1/workspaces/{ws_id}/git/connect" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "gitProviderDetails": {
      "organizationName": "minha-org",
      "projectName": "data-project",
      "gitProviderType": "AzureDevOps",
      "repositoryName": "fabric-pipelines",
      "branchName": "main",
      "directoryName": "/workspace"
    }
  }'

# Atualizar credenciais (SP)
curl -X PATCH "https://api.fabric.microsoft.com/v1/workspaces/{ws_id}/git/gitCredentials" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"gitCredentialsType": "ServicePrincipal"}'
```

## Fluxo de Deploy por Branch
```
feature/xyz → dev workspace (auto-sync)
            ↓ PR
test        → staging workspace (commit + sync via API)
            ↓ aprovação
main        → prod workspace (deploy via API + validação)
```

## Deploy via Azure DevOps
```yaml
# azure-pipelines.yml — deploy para staging/prod
- task: PowerShell@2
  displayName: "Deploy to Fabric"
  inputs:
    targetType: inline
    script: |
      $token = (az account get-access-token --resource "https://api.fabric.microsoft.com" | ConvertFrom-Json).accessToken
      # Pull latest from Git no workspace
      Invoke-RestMethod -Uri "https://api.fabric.microsoft.com/v1/workspaces/$WS_ID/git/updateFromGit" `
        -Method POST `
        -Headers @{Authorization="Bearer $token"; "Content-Type"="application/json"} `
        -Body '{"remoteCommitHash": "HEAD", "conflictResolution": {"conflictResolutionType": "Workspace"}}'
```

## Boas Práticas
- Um workspace por branch (dev/staging/prod) — não compartilhar workspace entre branches
- Nomear items com prefixo de ambiente em staging: `[STAGING] Pipeline_Bronze`
- Versionar apenas code e configs — não versionar dados
- SP com permissão mínima necessária (principle of least privilege)
