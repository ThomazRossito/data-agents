---
updated_at: 2026-04-16
source: firecrawl + skill-cross-reference
---

# SKILL: fabric-deployment-pipelines

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** 2026-04-16
> **Uso:** Leia este arquivo ANTES de gerenciar pipelines de deploy Fabric via REST API.

---

## Overview

Gerencia pipelines de deployment (CI/CD dev->test->prod) programaticamente -- cria pipelines,
configura estagios, atribui workspaces, executa deploys e monitora operacoes via REST API com
suporte a LRO (Long Running Operation) polling.

### O Problema

Deploy manual de conteudo entre workspaces consome tempo, nao escala e introduz risco de erro humano.
Alem disso, cada deployment requer multiplas chamadas REST para inicializar operacao, fazer polling,
validar conflitos e monitorar progresso ate conclusao.

### A Solucao

Esta skill encapsula o ciclo completo de CI/CD:

- Criacao de pipelines com multiplos estagios (Dev, Test, Prod)
- Atribuicao de workspaces a estagios
- Deploy seletivo de items (todos ou selecionados)
- Polling automatico de LRO ate conclusao (sucesso/falha)
- Listagem de operacoes e detalhes
- Atribuicoes de papel para gerenciar acesso ao pipeline

**Resultado:** Deploy CI/CD completo em 1-2 chamadas encapsuladas (criar pipeline + deploy).

---

## Deployment Pipelines vs Git Integration — Quando Usar Cada Um

> Esta decisao e recorrente. Use a tabela abaixo antes de escolher a abordagem.

| Criterio | Deployment Pipelines | Git Integration |
|----------|---------------------|-----------------|
| **Objetivo principal** | Promover conteudo entre ambientes (Dev→Test→Prod) | Versionar conteudo no Git (GitHub/ADO) |
| **Controle de versao** | Nao (sem historico Git) | Sim (commits, branches, PRs) |
| **Rastreabilidade de mudancas** | Limitada (historico de deploys interno) | Completa (Git log, diff, blame) |
| **Deploy entre workspaces** | Sim (nativo) | Nao (exige automacao extra) |
| **Resolucao de conflito** | PreferRemote / PreferWorkspace | PreferRemote / PreferWorkspace |
| **Automacao CI/CD** | Sim (REST API, LRO) | Sim (REST API, LRO) |
| **Deployment Rules** | Sim (regras por item/stage) | Nao (Git nao tem conceito equivalente) |
| **Rollback** | Via historico de operacoes + re-deploy | Via `git revert` + `updateFromGit` |
| **Requer Git configurado** | Nao | Sim |
| **Ideal para** | Equipes com workspaces Dev/Test/Prod separados | Equipes com fluxo de PR e code review |

**Regra do projeto:** Use Deployment Pipelines quando o fluxo e workspace-to-workspace.
Use Git Integration quando o fluxo e workspace-to-repo (code review, auditoria, backup).

**A partir de 2025H2 (integracao combinada):** Deployment Pipelines podem gerar commits
automaticos em ADO/GitHub ao promover entre stages (dev->test->prod). Para habilitar, configure
Git Integration no workspace de destino antes de executar o deploy. O commit e gerado com a
nota do deploy como mensagem.

---

## Quick Start

Exemplo mais comum -- criar pipeline 3-estagios e fazer deploy de Dev para Test:

```python
from deployment_pipelines import create_deployment_pipeline, assign_workspace_to_stage, deploy_stage_content

# 1. Criar pipeline com 3 estagios
pipeline = create_deployment_pipeline(
    display_name="DataLake-Pipeline",
    stages=[
        {"displayName": "Development", "description": "Dev", "isPublic": False},
        {"displayName": "Testing", "description": "Test", "isPublic": False},
        {"displayName": "Production", "description": "Prod", "isPublic": True}
    ]
)
pipeline_id = pipeline["id"]

# 2. Atribuir workspaces
assign_workspace_to_stage(pipeline_id, "Development", "dev-workspace")
assign_workspace_to_stage(pipeline_id, "Testing", "test-workspace")
assign_workspace_to_stage(pipeline_id, "Production", "prod-workspace")

# 3. Fazer deploy com LRO polling
deploy_stage_content(
    pipeline=pipeline_id,
    source_stage="Development",
    target_stage="Testing",
    note="Deploy automatizado Q2-2026"
)
# Retorno: {"status": "success", "deploymentId": "...", "executionTime": "120s"}
```

---

## Common Patterns

### 1. `create_deployment_pipeline` -- Criar pipeline novo

Cria pipeline com nome, estagios e descricao opcionais.

**Parametros:**

| Parametro      | Tipo | Obrigatorio | Descricao                                          |
|----------------|------|-------------|-----------------------------------------------------|
| `display_name` | str  | Sim         | Nome do pipeline                                   |
| `stages`       | list | Sim         | Lista de dicts com displayName, description, isPublic |
| `description`  | str  | Nao         | Descricao do pipeline                              |

**Fluxo interno:**
1. Validar que stages nao esta vazio
2. `POST /v1/deploymentPipelines` com payload stages
3. Retorna detalhes do pipeline com IDs de estagios

**Exemplo:**

```python
from deployment_pipelines import create_deployment_pipeline

stages = [
    {"displayName": "Dev", "description": "Development", "isPublic": False},
    {"displayName": "Stage", "description": "Staging", "isPublic": False},
    {"displayName": "Prod", "description": "Production", "isPublic": True}
]

pipeline = create_deployment_pipeline(
    display_name="MyPipeline",
    stages=stages,
    description="3-stage CI/CD pipeline"
)
print(f"Pipeline criado: {pipeline['id']}")
```

---

### 2. `assign_workspace_to_stage` -- Vincular workspace a estagios

Atribui workspace a um estagios especifico do pipeline.

**Parametros:**

| Parametro  | Tipo | Obrigatorio | Descricao                      |
|------------|------|-------------|--------------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace        |
| `pipeline` | str  | Sim         | ID ou nome do pipeline         |
| `stage`    | str  | Sim         | Nome ou ID do estagios         |

**Fluxo interno:**
1. Resolver pipeline, estagios e workspace para IDs
2. `POST /v1/deploymentPipelines/{pipelineId}/stages/{stageId}/assignWorkspace`
3. Retorna detalhes do estagios atualizado

**Exemplo:**

```python
from deployment_pipelines import assign_workspace_to_stage

assign_workspace_to_stage(
    workspace="dev-analytics",
    pipeline="MyPipeline",
    stage="Dev"
)
```

---

### 3. `deploy_stage_content` -- Executar deploy com LRO polling

Faz deploy de conteudo de um estagios para outro com suporte a deploy seletivo.

**Parametros:**

| Parametro       | Tipo | Obrigatorio | Descricao                                      |
|-----------------|------|-------------|------------------------------------------------|
| `pipeline`      | str  | Sim         | ID ou nome do pipeline                         |
| `source_stage`  | str  | Sim         | Nome ou ID do estagios origem                  |
| `target_stage`  | str  | Sim         | Nome ou ID do estagios destino                 |
| `items`         | list | Nao         | Lista de items para deploy seletivo            |
| `note`          | str  | Nao         | Anotacao/comentario do deploy                  |
| `options`       | dict | Nao         | Opcoes adicionais (allowCrossRegionDeployment) |

**Fluxo interno:**
1. Resolver pipeline, estagios para IDs
2. Construir payload com sourceStageId, targetStageId, items (optional), note
3. `POST /v1/deploymentPipelines/{pipelineId}/deploy` com LRO support
4. Polling automatico ate status == "Succeeded" ou "Failed"
5. Retorna detalhes da operacao com tempo de execucao

**Exemplo - Deploy tudo:**

```python
from deployment_pipelines import deploy_stage_content

result = deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Stage",
    note="Producao de semantico models"
)
```

**Exemplo - Deploy seletivo (items especificos):**

```python
from deployment_pipelines import deploy_stage_content

items = [
    {"sourceItemId": "model-uuid-1", "itemType": "SemanticModel"},
    {"sourceItemId": "report-uuid-2", "itemType": "Report"}
]

result = deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Stage",
    items=items,
    note="Deploy seletivo de 2 items"
)
```

**Exemplo - Deploy com resolucao de conflito:**

```python
from deployment_pipelines import deploy_stage_content

result = deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Stage",
    options={
        "conflictResolution": {
            "conflictResolutionPolicy": "PreferRemote"
        },
        "allowCrossRegionDeployment": False
    },
    note="Deploy com sobrescrita de conflitos"
)
```

---

### 4. `list_deployment_pipeline_operations` -- Monitorar historico

Lista todas as operacoes (deploys) executadas em um pipeline.

**Parametros:**

| Parametro  | Tipo | Obrigatorio | Descricao          |
|------------|------|-------------|---------------------|
| `pipeline` | str  | Sim         | ID ou nome pipeline |

**Fluxo interno:**
1. Resolver pipeline para ID
2. `GET /v1/deploymentPipelines/{pipelineId}/operations` (com paginacao)
3. Retorna lista de operacoes com status, timestamp, itens deployados

**Exemplo:**

```python
from deployment_pipelines import list_deployment_pipeline_operations

ops = list_deployment_pipeline_operations(pipeline="MyPipeline")
for op in ops:
    print(f"{op['createdTime']} | {op['status']} | Items: {op['itemsCount']}")
```

---

### 5. `add_deployment_pipeline_role_assignment` -- RBAC pipeline

Atribui papel (Admin/Contributor/Member/Viewer) a usuario/grupo/SPN no pipeline.

**Parametros:**

| Parametro    | Tipo | Obrigatorio | Descricao                        |
|--------------|------|-------------|----------------------------------|
| `pipeline`   | str  | Sim         | ID ou nome do pipeline           |
| `user_uuid`  | str  | Sim         | ID do usuario/grupo/SPN          |
| `user_type`  | str  | Nao         | User, Group, ServicePrincipal... |
| `role`       | str  | Nao         | Admin, Contributor, Member, Viewer |

**Fluxo interno:**
1. Validar user_type e role
2. `POST /v1/deploymentPipelines/{pipelineId}/roleAssignments`
3. Retorna detalhes da atribuicao

**Exemplo:**

```python
from deployment_pipelines import add_deployment_pipeline_role_assignment

add_deployment_pipeline_role_assignment(
    pipeline="MyPipeline",
    user_uuid="devops-team-uuid",
    user_type="Group",
    role="Admin"
)
```

---

## Deployment Rules

Deployment Rules permitem sobrescrever configuracoes de items especificos no estagios destino
sem alterar o artefato no estagios origem. Sao configuradas por item e por stage via UI ou REST.

### Casos de Uso Tipicos

- Apontar DataSource de conexao para ambiente correto (Dev DB -> Prod DB)
- Alterar parametros de Lakehouse/Warehouse entre ambientes
- Sobrescrever workspace IDs referenciados em Semantic Models

### Como Funcionam

1. Item e deployado normalmente do estagio origem para destino
2. Deployment Rule e aplicada **pos-deploy** no estagios destino
3. Item no destino reflete a regra; item na origem permanece inalterado

### Tipos de Regras Suportadas

| Tipo de Item | Configuracao Disponivel |
|---|---|
| Semantic Model | Data source connection (servidor, banco, credencial) |
| Report | Semantic model vinculado (trocar modelo por ambiente) |
| Dataflow Gen2 | Connection string e parametros |
| Data Pipeline | Linked service e parametros |

### Boas Praticas de Deployment Rules

- Configure Rules antes do primeiro deploy entre ambientes.
- Nao dependa de nomes de workspace nos parametros — use IDs.
- Para Semantic Models: use `DirectQuery` parametrizado ou `connection strings` que podem ser
  sobrescritas por Rule, nunca hardcode de server/database no modelo.
- Documente as Rules no campo `note` do deploy para auditoria.

> As Deployment Rules sao configuradas via UI do Fabric (menu de cada stage) ou via REST API.
> Nao existe endpoint direto para criar Rules programaticamente na v1 da API; use a UI para
> configuracao inicial e REST API para execucao dos deploys.

---

## Deployment Notes — Boas Praticas

O campo `note` no payload de deploy e armazenado no historico de operacoes e serve como
auditoria de cada promocao. Use-o consistentemente.

### Formato Recomendado

```
[AMBIENTE] [TIPO] [VERSAO/SPRINT] — [DESCRICAO BREVE]
```

**Exemplos:**

```
DEV->TEST Sprint-23 — Novos relatorios de qualidade de dados
TEST->PROD v2.4.1 — Deploy apos aprovacao QA em 2026-04-15
DEV->TEST Hotfix — Correcao urgente no pipeline de ingestao
```

### Por que importa

- O campo `note` aparece no historico de operacoes (`GET /operations`)
- E a unica descricao disponivel para auditores revisando `list_deployment_pipeline_operations`
- A partir de 2025H2, se Git Integration estiver configurada no workspace destino, a `note`
  vira a mensagem do commit automatico gerado pelo deploy

---

## Rollback via Historico de Operacoes

Nao existe endpoint nativo de "rollback" nos Deployment Pipelines. O padrao do projeto e:

### Estrategia 1 — Re-deploy de versao anterior (preferencial)

1. Identifique o `operationId` do deploy que estava funcionando via `list_deployment_pipeline_operations`
2. Obtenha os `itemsCount` e detalhes do deploy anterior via `GET /operations/{operationId}`
3. No estagio origem (Dev/Test), restaure os items para a versao anterior (via Git Integration + `updateFromGit`)
4. Execute novo deploy do estagio origem para o destino

### Estrategia 2 — Rollback via Git Integration

Se Git Integration estiver configurada nos workspaces:

```python
from git_integration import update_from_git
from deployment_pipelines import deploy_stage_content

# 1. Revert no workspace Dev para commit anterior via Git
# (executado fora do SDK — git revert + push)

# 2. Sincronizar workspace Dev com o commit revertido
update_from_git(
    workspace="dev-analytics",
    conflict_resolution_policy="PreferRemote"  # Git e a fonte de verdade
)

# 3. Re-promover versao anterior para Prod
deploy_stage_content(
    pipeline="MyPipeline",
    source_stage="Dev",
    target_stage="Prod",
    note="ROLLBACK para v2.3.0 — revert de incidente 2026-04-16"
)
```

### Consultar Historico para Auditoria

```python
from deployment_pipelines import list_deployment_pipeline_operations

# Ver ultimos 10 deploys
ops = list_deployment_pipeline_operations(pipeline="DataLake-Pipeline")
for op in ops[:10]:
    print(f"ID: {op['id']}")
    print(f"  Status:    {op['status']}")
    print(f"  Iniciado:  {op['createdTime']}")
    print(f"  Items:     {op['itemsCount']}")
    print(f"  Nota:      {op.get('note', '(sem nota)')}")
    print()
```

---

## Automacao via PowerShell

Para automacao em pipelines CI/CD (Azure DevOps, GitHub Actions), use o modulo
`MicrosoftFabric` do PowerShell ou chamadas REST diretas com `az` CLI.

### Instalar modulo PowerShell

```powershell
Install-Module -Name MicrosoftFabric -Force -AllowClobber
Import-Module MicrosoftFabric
```

### Autenticar com Service Principal

```powershell
$tenantId     = $env:AZURE_TENANT_ID
$clientId     = $env:AZURE_CLIENT_ID
$clientSecret = $env:AZURE_CLIENT_SECRET

$token = (Get-AzAccessToken -ResourceUrl "https://api.fabric.microsoft.com" `
    -TenantId $tenantId).Token

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type"  = "application/json"
}
```

### Executar deploy em pipeline CI/CD

```powershell
# Obter pipeline ID
$pipelines = Invoke-RestMethod `
    -Uri "https://api.fabric.microsoft.com/v1/deploymentPipelines" `
    -Headers $headers -Method GET

$pipelineId = ($pipelines.value | Where-Object { $_.displayName -eq "DataLake-Pipeline" }).id

# Obter stage IDs
$pipeline = Invoke-RestMethod `
    -Uri "https://api.fabric.microsoft.com/v1/deploymentPipelines/$pipelineId" `
    -Headers $headers -Method GET

$devStageId  = ($pipeline.stages | Where-Object { $_.displayName -eq "Dev" }).id
$testStageId = ($pipeline.stages | Where-Object { $_.displayName -eq "Test" }).id

# Iniciar deploy (LRO)
$body = @{
    sourceStageId = $devStageId
    targetStageId = $testStageId
    note          = "CI/CD automatizado - branch: $env:GITHUB_REF_NAME"
} | ConvertTo-Json

$response = Invoke-RestMethod `
    -Uri "https://api.fabric.microsoft.com/v1/deploymentPipelines/$pipelineId/deploy" `
    -Headers $headers -Method POST -Body $body

$operationId = $response.id

# Polling LRO
do {
    Start-Sleep -Seconds 10
    $status = Invoke-RestMethod `
        -Uri "https://api.fabric.microsoft.com/v1/deploymentPipelines/$pipelineId/operations/$operationId" `
        -Headers $headers -Method GET
    Write-Host "Status: $($status.status)"
} while ($status.status -eq "Running" -or $status.status -eq "NotStarted")

if ($status.status -ne "Succeeded") {
    Write-Error "Deploy falhou: $($status.status)"
    exit 1
}
Write-Host "Deploy concluido com sucesso"
```

### GitHub Actions — Exemplo de Step

```yaml
- name: Deploy Dev to Test (Fabric)
  env:
    AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
    AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
    AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
    PIPELINE_NAME: "DataLake-Pipeline"
  shell: pwsh
  run: |
    # Autenticar e executar deploy
    ./scripts/fabric-deploy.ps1 `
      -SourceStage "Dev" `
      -TargetStage "Test" `
      -Note "CI deploy - PR #${{ github.event.number }}"
```

---

## Reference Files

- [deployment-operations.md](deployment-operations.md) -- Payloads REST, estrategias de conflito, opcoes de deployment, exemplos cURL

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Pipeline nao encontrado (404)** | Confirme pipeline_id/name. Use `list_deployment_pipelines()`. |
| **Estagios nao encontrado (404)** | Verifique nome do estagios. Stage IDs sao gerados na criacao do pipeline. |
| **Workspace nao atribuido ao estagios** | Execute `assign_workspace_to_stage()` antes de deploy. |
| **Deploy falha com conflito (422)** | Item com mesmo nome existe no target stage. Use conflict resolution (PreferRemote/PreferWorkspace). |
| **LRO timeout** | Deploy grande pode demorar >120s. Aumente timeout para 300s ou implemente polling customizado. |
| **Status 202 (LRO iniciada)** | Deploy aceitado. Polling comeca automaticamente; aguarde ate conclusao. |
| **Permissao insuficiente (403)** | Usuario nao tem Admin no pipeline. Peca ao proprietario para atribuir papel. |
| **Token expirado (401)** | Renove token via MSAL. Configure Azure Identity ou Key Vault. |
| **Deployment Rule nao aplicada** | Rules sao configuradas via UI. Confirme que Rule esta ativa no stage destino antes do deploy. |
| **Commit automatico nao gerado (2025H2+)** | Git Integration deve estar configurada no workspace destino antes do deploy. Verifique `git/connection`. |
| **allowCrossRegionDeployment negado** | Por padrao, deploys cross-region sao bloqueados. Habilite explicitamente em `options`. |

---

## Notas de Versao (2025H2 / 2026-04)

- **Integracao com Git (2025H2):** Pipelines de deployment agora podem gerar commits automaticos
  em ADO/GitHub ao promover entre stages. Requer Git Integration configurada no workspace destino.
  O campo `note` do deploy vira mensagem do commit.
- **Conflict Resolution no payload:** O campo `options.conflictResolution.conflictResolutionPolicy`
  agora e suportado diretamente no payload de deploy (anteriormente apenas via UI).
- **Paginacao em `/operations`:** O endpoint `GET /operations` suporta `$top` e `$skip`
  para pipelines com historico extenso.
- **allowCrossRegionDeployment:** Flag agora documentada oficialmente; necessaria para
  workspaces em regioes Azure distintas.
