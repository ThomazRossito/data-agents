---
name: fabric-workspace-manager
updated_at: 2026-04-23
source: web_search
---

# SKILL: fabric-workspace-manager

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** 2026-04-23
> **Uso:** Leia este arquivo ANTES de gerenciar workspaces Fabric programaticamente via REST API.

---

## Overview

Gerencia workspaces Microsoft Fabric programaticamente -- lista, cria, atualiza, deleta e configura
atribuições de função (RBAC) e vinculação de capacidade via REST API.

### O Problema

Gerenciar workspaces Fabric manualmente no portal consome tempo e não escala para operações em lote.
Além disso, controlar permissões (Admin/Contributor/Member/Viewer) e vinculações de capacidade para múltiplos
usuários/grupos requer múltiplas chamadas REST e validação de estado.

### A Solucao

Esta skill encapsula operações de workspace completas:

- Listagem, criação, atualização e exclusão de workspaces
- Atribuições de função para Users, Groups, ServicePrincipals via RBAC
- Listagem, criação, atualização e remoção de role assignments (com paginação via `continuationToken`)
- Vinculação e desvinculação de capacidade (com polling para LRO)
- Aplicação e remoção de **tags** de workspace (novidade março/2026)
- Resolução de workspaces por nome ou ID
- Validação e tratamento de erros nas respostas de status 201 (criado), 202 (aceito), 409 (conflito) e 422 (entidade invalida)

**Resultado:** Automação completa do ciclo de vida de workspaces sem chamar REST manualmente.

**Skills relacionadas (ALM completo):**
- [`skills/fabric/fabric-deployment-pipelines/SKILL.md`](../fabric-deployment-pipelines/SKILL.md) — deploy CI/CD entre stages
- [`skills/fabric/fabric-git-integration/SKILL.md`](../fabric-git-integration/SKILL.md) — controle de versão Git

---

## Quick Start

Exemplo mais comum -- criar workspace e atribuir Admin a um usuário:

```python
from workspace_manager import create_workspace, add_workspace_role_assignment

# Criar workspace novo
ws = create_workspace(
    display_name="Analytics-2026",
    capacity="capacity-prod",
    description="Workspace para análise de vendas"
)
workspace_id = ws["id"]

# Atribuir Admin a usuário
add_workspace_role_assignment(
    workspace=workspace_id,
    user_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    user_type="User",
    role="Admin"
)
# Retorno: {"id": "...", "principal": {...}, "role": "Admin"}
# Status HTTP: 201 Created (não 200)
```

---

## Common Patterns

### 1. `list_workspaces` -- Listar todos os workspaces

Leitura somente. Suporta paginação automática via `continuationToken`.

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| `df` | bool | Nao | Se True, retorna DataFrame; se False, lista de dicts |
| `roles` | str | Nao | Filtra por papel do principal no workspace (ex: `Admin`, `Member`) |
| `prefer_workspace_specific_endpoints` | bool | Nao | Se True, retorna `apiEndpoint` por workspace no response |

**Fluxo interno:**
1. `GET /v1/workspaces?roles={roles}&continuationToken={token}&preferWorkspaceSpecificEndpoints={bool}` (com paginação via `continuationToken`)
2. Retorna lista de workspaces com campos: `id`, `displayName`, `description`, `capacityId`, `type`, e opcionalmente `apiEndpoint`

**Campos de retorno relevantes (por workspace):**

| Campo | Descricao |
|-------|-----------|
| `id` | UUID do workspace |
| `displayName` | Nome do workspace |
| `type` | `Workspace`, `Personal`, `AdminWorkspace` |
| `capacityId` | UUID da capacidade vinculada (ausente se nenhuma) |
| `apiEndpoint` | Endpoint específico do workspace (retornado quando `preferWorkspaceSpecificEndpoints=True`) |

**Exemplo:**

```python
from workspace_manager import list_workspaces

ws_list = list_workspaces(df=False)
for ws in ws_list:
    print(f"{ws['displayName']} | Capacity: {ws.get('capacityId', 'Nenhuma')} | Type: {ws.get('type')}")
```

---

### 2. `create_workspace` -- Criar workspace novo

Cria workspace com nome, descrição e capacidade opcionais.

> ℹ️ Service Principals podem criar workspaces — requer permissão habilitada pelo Fabric Admin. Veja: *Service principals can create workspaces, connections, and deployment pipelines*.

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                                   |
|----------------|--------|-------------|---------------------------------------------|
| `display_name` | str    | Sim         | Nome do workspace                           |
| `capacity`     | str    | Nao         | Nome ou ID da capacidade                    |
| `description`  | str    | Nao         | Descricao do workspace                      |

**Fluxo interno:**
1. Construir payload com `displayName`, `capacityId` (resolvido), `description`
2. `POST /v1/workspaces` com payload
3. Retorna objeto workspace com `id`, `displayName`, `description`, `type`

**Exemplo:**

```python
from workspace_manager import create_workspace

ws = create_workspace(
    display_name="Sales-Q2-2026",
    capacity="prod-capacity",
    description="Análise de vendas Q2"
)
print(f"Workspace criado: {ws['id']}")
```

---

### 3. `update_workspace` -- Atualizar propriedades

Atualiza nome e/ou descrição de um workspace existente.

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                      |
|----------------|--------|-------------|--------------------------------|
| `workspace`    | str    | Sim         | ID ou nome do workspace        |
| `display_name` | str    | Nao         | Novo nome                      |
| `description`  | str    | Nao         | Nova descricao                 |

**Fluxo interno:**
1. Resolver workspace para ID
2. `PATCH /v1/workspaces/{workspaceId}` com payload
3. Validar que pelo menos uma propriedade foi fornecida
4. Retorna objeto workspace atualizado (inclui `domainId` se o workspace estiver associado a um domínio)

**Exemplo:**

```python
from workspace_manager import update_workspace

update_workspace(
    workspace="Sales-Q2-2026",
    display_name="Sales-Q3-2026",
    description="Migrado para Q3"
)
```

---

### 4. `delete_workspace` -- Deletar workspace

> ⚠️ Operação destrutiva e irreversível. Confirme com o usuário antes de executar em produção.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `DELETE /v1/workspaces/{workspaceId}`
3. Retorna 200 OK em sucesso

**Exemplo:**

```python
from workspace_manager import delete_workspace

# ATENÇÃO: irreversível
delete_workspace(workspace="Analytics-Temp-2026")
```

---

### 5. `add_workspace_role_assignment` -- Atribuir funcao RBAC

Atribui papel (Admin/Contributor/Member/Viewer) a usuario/grupo/SPN em workspace.

> ℹ️ O endpoint retorna **HTTP 201 Created** (não 200) com o objeto de atribuição e o header `Location` apontando para a URL do novo recurso.

**Parametros:**

| Parametro    | Tipo   | Obrigatorio | Descricao                                          |
|--------------|--------|-------------|-----------------------------------------------------|
| `workspace`  | str    | Sim         | ID ou nome do workspace                            |
| `user_uuid`  | str    | Sim         | ID do usuario/grupo/SPN                            |
| `user_type`  | str    | Nao         | User, Group, ServicePrincipal, ServicePrincipalProfile |
| `role`       | str    | Nao         | Admin, Contributor, Member, Viewer (padrao: Admin) |

**Fluxo interno:**
1. Validar `user_type` e `role` contra listas de valores permitidos
2. `POST /v1/workspaces/{workspaceId}/roleAssignments` com payload `{ principal: { id, type }, role }`
3. Retorna objeto `{ "id": "...", "principal": { "id", "type" }, "role": "..." }` com status **201**

**Exemplo:**

```python
from workspace_manager import add_workspace_role_assignment

# Atribuir Contributor a um grupo
add_workspace_role_assignment(
    workspace="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    user_uuid="group-uuid-12345",
    user_type="Group",
    role="Contributor"
)

# Atribuir Viewer a SPN
add_workspace_role_assignment(
    workspace="Sales-Q2-2026",
    user_uuid="spn-uuid-67890",
    user_type="ServicePrincipal",
    role="Viewer"
)
```

---

### 6. `list_workspace_role_assignments` -- Listar atribuicoes de funcao

Lista todas as atribuições de papel no workspace. Suporta paginação via `continuationToken`.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/roleAssignments?continuationToken={token}`
3. Retorna array paginado de `{ "id": "...", "principal": { "displayName", "id", "type", "userDetails"|"servicePrincipalDetails" }, "role": "..." }`

**Exemplo:**

```python
from workspace_manager import list_workspace_role_assignments

assignments = list_workspace_role_assignments(workspace="Sales-Q2-2026")
for a in assignments:
    print(f"{a['principal']['displayName']} ({a['principal']['type']}) → {a['role']}")
```

---

### 7. `update_workspace_role_assignment` -- Atualizar papel

Muda o papel de um usuario/grupo/SPN em um workspace.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao                  |
|-------------|------|-------------|----------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace    |
| `user_uuid` | str  | Sim         | ID do principal (= `workspaceRoleAssignmentId`) |
| `role`      | str  | Nao         | Novo papel (default: Admin) |

**Fluxo interno:**
1. Resolver workspace para ID
2. Validar role
3. `PATCH /v1/workspaces/{workspaceId}/roleAssignments/{workspaceRoleAssignmentId}` com payload `{ "role": "..." }`
4. Retorna objeto atribuição atualizado (inclui `displayName`, `userDetails` ou `servicePrincipalDetails` no `principal`)

**Exemplo:**

```python
from workspace_manager import update_workspace_role_assignment

# Promover de Member para Contributor
update_workspace_role_assignment(
    workspace="Sales-Q2-2026",
    user_uuid="user-uuid-999",
    role="Contributor"
)
```

---

### 8. `delete_workspace_role_assignment` -- Remover atribuicao de papel

Remove papel de um usuario/grupo/SPN no workspace.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |
| `user_uuid` | str  | Sim         | ID do principal (= `workspaceRoleAssignmentId`) |

**Fluxo interno:**
1. Resolver workspace para ID
2. `DELETE /v1/workspaces/{workspaceId}/roleAssignments/{workspaceRoleAssignmentId}`
3. Retorna 200 OK em sucesso

**Exemplo:**

```python
from workspace_manager import delete_workspace_role_assignment

delete_workspace_role_assignment(
    workspace="Sales-Q2-2026",
    user_uuid="user-uuid-antigo"
)
```

---

### 9. `assign_to_capacity` e `unassign_from_capacity` -- Gerenciar capacidade

Vincula ou desvincula workspace de uma capacidade. Operação assíncrona (LRO).

Use o campo `capacityAssignmentProgress` do `GET /workspaces/{workspaceId}` para monitorar o estado
do vínculo — mais confiável do que checar apenas `capacityId`.

**Parametros (assign_to_capacity):**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |
| `capacity`  | str  | Sim         | ID ou nome da capacidade |

**Parametros (unassign_from_capacity):**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace e capacidade para IDs
2. `POST /v1/workspaces/{workspaceId}/assignToCapacity` com `{ "capacityId": "..." }` ou `/unassignFromCapacity`
3. Aguardar status 202 (aceito) — LRO iniciada; workspace vinculado em ~10-30s em background

**Exemplo:**

```python
from workspace_manager import assign_to_capacity, unassign_from_capacity

# Vincular workspace a capacidade
assign_to_capacity(
    workspace="Sales-Q2-2026",
    capacity="premium-capacity"
)

# Desvincular de capacidade
unassign_from_capacity(
    workspace="Sales-Q2-2026"
)
```

---

### 10. `apply_workspace_tags` e `remove_workspace_tags` -- Gerenciar tags (novidade março/2026)

> ℹ️ **Novidade (março/2026):** Workspace Tags permitem adicionar metadados compartilhados (ex: time, projeto, centro de custo) a workspaces, facilitando descoberta e governança via API. Tags são definidas uma vez no tenant e aplicadas a workspaces. **Limite: 10 tags por workspace.**

Tags de workspace são retornadas no campo `tags` de `GET /v1/workspaces/{workspaceId}` e ficam visíveis na lista de workspaces e no OneLake Catalog Explorer.

**Parametros (apply_workspace_tags):**

| Parametro    | Tipo      | Obrigatorio | Descricao                              |
|--------------|-----------|-------------|----------------------------------------|
| `workspace`  | str       | Sim         | ID ou nome do workspace                |
| `tag_ids`    | list[str] | Sim         | Lista de UUIDs das tags a aplicar      |

**Parametros (remove_workspace_tags):**

| Parametro    | Tipo      | Obrigatorio | Descricao                              |
|--------------|-----------|-------------|----------------------------------------|
| `workspace`  | str       | Sim         | ID ou nome do workspace                |
| `tag_ids`    | list[str] | Sim         | Lista de UUIDs das tags a remover      |

**Fluxo interno:**
1. Resolver workspace para ID
2. `POST /v1/workspaces/{workspaceId}/applyTags` ou `/removeTags` com payload `{ "tagIds": [...] }`
3. Tags são gerenciadas no nível de tenant — crie-as primeiro via Admin API de Tags antes de aplicar

**Exemplo:**

```python
from workspace_manager import apply_workspace_tags, remove_workspace_tags

# Aplicar tags "Finance" e "Production" ao workspace
apply_workspace_tags(
    workspace="Sales-Q2-2026",
    tag_ids=[
        "b3f2c8e9-4d8e-4a7c-9a32-f8c1b2e4d6af",  # Finance
        "6f1a8d3b-92c4-4f67-8c2d-1e5a9b7f4a23"   # Production
    ]
)

# Remover tag
remove_workspace_tags(
    workspace="Sales-Q2-2026",
    tag_ids=["6f1a8d3b-92c4-4f67-8c2d-1e5a9b7f4a23"]
)
```

---

## Campos de Retorno: GET /v1/workspaces/{workspaceId}

A resposta completa do endpoint agora inclui campos adicionais importantes:

| Campo | Tipo | Descricao |
|-------|------|-----------|
| `id` | str | UUID do workspace |
| `displayName` | str | Nome do workspace |
| `description` | str | Descricao |
| `type` | str | `Workspace`, `Personal`, `AdminWorkspace` |
| `capacityId` | str | UUID da capacidade vinculada |
| `capacityAssignmentProgress` | str | Estado do vínculo de capacidade: `Completed`, `Failed`, `InProgress` — use para polling de LRO |
| `capacityRegion` | str | Região da capacidade (ex: `East US`) |
| `domainId` | str | UUID do domínio Fabric associado (se houver) |
| `workspaceIdentity` | obj | `{ applicationId, servicePrincipalId }` — identidade gerenciada do workspace para autenticação em shortcuts e pipelines |
| `oneLakeEndpoints` | obj | `{ blobEndpoint, dfsEndpoint }` — endpoints OneLake (padrão = regionais; específicos se `preferWorkspaceSpecificEndpoints=True`) |
| `apiEndpoint` | str | Endpoint de API específico do workspace (retornado quando `preferWorkspaceSpecificEndpoints=True`) |
| `tags` | array | Tags aplicadas: `[{ "id": "...", "displayName": "..." }]` |

> **Polling de capacidade:** Prefira checar `capacityAssignmentProgress == "Completed"` em vez de apenas `capacityId` após `assignToCapacity`. O campo pode estar preenchido antes do vínculo estar totalmente ativo.

---

## Padrão: Provisionamento em Lote (Bulk Operations)

Para provisionar múltiplos workspaces (ex: onboarding de novo time), use o padrão abaixo:

```python
from workspace_manager import create_workspace, add_workspace_role_assignment, assign_to_capacity
import time

TEAMS = [
    {"name": "Data-Engineering", "capacity": "prod-cap", "admin": "de-team-uuid"},
    {"name": "Data-Science",     "capacity": "prod-cap", "admin": "ds-team-uuid"},
    {"name": "Analytics",        "capacity": "bi-cap",   "admin": "bi-team-uuid"},
]

for team in TEAMS:
    ws = create_workspace(
        display_name=team["name"],
        capacity=team["capacity"],
        description=f"Workspace do time {team['name']}"
    )
    add_workspace_role_assignment(
        workspace=ws["id"],
        user_uuid=team["admin"],
        user_type="Group",
        role="Admin"
    )
    print(f"Provisionado: {team['name']} ({ws['id']})")
    time.sleep(1)  # throttle: evitar 429
```

---

## Padrão: LRO Polling Manual para assignToCapacity

Quando `assign_to_capacity` retorna 202, o vínculo ocorre em background. Use o campo
`capacityAssignmentProgress` (mais confiável que checar apenas `capacityId`) para confirmar conclusão:

```python
import time
import requests

def wait_for_capacity_assignment(workspace_id: str, capacity_id: str, token: str, max_retries: int = 10):
    headers = {"Authorization": f"Bearer {token}"}
    base_url = "https://api.fabric.microsoft.com/v1"

    # Iniciar atribuição
    resp = requests.post(
        f"{base_url}/workspaces/{workspace_id}/assignToCapacity",
        json={"capacityId": capacity_id},
        headers=headers
    )
    if resp.status_code not in (200, 202):
        raise RuntimeError(f"Falha ao atribuir capacidade: {resp.status_code} {resp.text}")

    # Polling via GET workspace usando capacityAssignmentProgress
    for attempt in range(max_retries):
        time.sleep(5)
        ws = requests.get(f"{base_url}/workspaces/{workspace_id}", headers=headers).json()
        progress = ws.get("capacityAssignmentProgress")
        if progress == "Completed" and ws.get("capacityId") == capacity_id:
            return True
        if progress == "Failed":
            raise RuntimeError(f"Vínculo de capacidade falhou: {ws}")
        print(f"Aguardando vínculo de capacidade... tentativa {attempt + 1}/{max_retries} | progress={progress}")

    raise TimeoutError("Timeout: capacidade não foi vinculada dentro do tempo esperado.")
```

---

## ALM no Fabric: Integracao com Deployment Pipelines e Git

Workspaces são a unidade base do ciclo ALM completo. O fluxo recomendado é:

```
1. Provisionar workspaces (esta skill)
   create_workspace("analytics-dev")
   create_workspace("analytics-test")
   create_workspace("analytics-prod")

2. Integrar com Git (fabric-git-integration skill)
   github_connect(workspace="analytics-dev", ...)
   commit_to_git(workspace="analytics-dev", mode="All", comment="baseline")

3. Criar pipeline de deployment (fabric-deployment-pipelines skill)
   create_deployment_pipeline("analytics-pipeline", stages=["Dev","Test","Prod"])
   assign_workspace_to_stage(pipeline, "Dev",  "analytics-dev")
   assign_workspace_to_stage(pipeline, "Test", "analytics-test")
   assign_workspace_to_stage(pipeline, "Prod", "analytics-prod")

4. Deploy CI/CD
   deploy_stage_content(pipeline, source_stage="Dev", target_stage="Test")
   # A partir de 2025H2: deployment gera commit automatico em ADO/GitHub
```

> Para detalhes de cada etapa 2 e 3, consulte as skills respectivas:
> - `skills/fabric/fabric-git-integration/SKILL.md`
> - `skills/fabric/fabric-deployment-pipelines/SKILL.md`

---

## Reference Files

- [workspace-operations.md](workspace-operations.md) -- Referencia tecnica: endpoints REST, payloads, campos de resposta, exemplos cURL
- [role-assignments.md](role-assignments.md) -- Detalhes de RBAC: tipos de usuarios, papeis, matrix de permissoes

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Workspace nao encontrado (404)** | Confirme workspace_id/name. Use `list_workspaces()` para validar. |
| **user_type invalido** | Use apenas: User, Group, ServicePrincipal, ServicePrincipalProfile. |
| **Role invalida** | Use apenas: Admin, Contributor, Member, Viewer. |
| **Capacidade nao encontrada** | Verifique que capacity existe via `list_capacities()`. |
| **Status 201 (Created)** | Retorno correto de `add_workspace_role_assignment` — trate como sucesso (não apenas 200). |
| **Status 202 (LRO)** | Operacao de capacidade iniciada. Faça polling por `capacityAssignmentProgress == "Completed"`. |
| **Status 409 (Conflito)** | Nome de workspace duplicado ou conflito de estado. Workspace com mesmo displayName ja existe — use nome diferente. |
| **Status 422 (Entidade invalida)** | Workspace ja tem essa capacidade ou validacao de negocio falhou. Aguarde alguns segundos e retry. |
| **Token expirado (401)** | Renove token via Azure Identity. Nunca hardcode -- use Key Vault. |
| **Permissao insuficiente (403)** | Usuario autenticado nao tem permissao Admin no workspace para RBAC. Para criar workspace via SPN, verifique permissão habilitada no Fabric Admin. |
| **Rate limit (429)** | Muitas requisicoes. Implemente backoff exponencial; adicione `time.sleep(1)` entre operacoes em lote. Admin API tem limite de 200 req/hora. |
| **Workspace em Trial/Free capacity** | Git Integration e Deployment Pipelines requerem F-SKU ou P-SKU. Mova para capacidade paga antes de usar ALM. |
| **Mais de 10 tags por workspace** | API retorna erro — limite de 10 tags aplicadas por workspace. Remova tags antes de adicionar novas. |
| **capacityAssignmentProgress = "Failed"** | Vínculo de capacidade falhou. Verifique permissões (contributor ou Admin na capacity) e retry. |

---

## Notas de Versao

### 2026-04 (atual)
- **Novos campos em GET /workspaces/{id}:** `capacityAssignmentProgress`, `capacityRegion`, `domainId`, `workspaceIdentity`, `oneLakeEndpoints`, `apiEndpoint`, `tags` — todos documentados e retornados pela API estável.
- **`preferWorkspaceSpecificEndpoints` (query param):** Disponível em `GET /v1/workspaces` e `GET /v1/workspaces/{id}`. Quando `True`, retorna endpoints específicos por workspace em `oneLakeEndpoints` e `apiEndpoint`.
- **Paginação em roleAssignments:** `GET /v1/workspaces/{id}/roleAssignments` agora suporta `continuationToken` para listas grandes.
- **add_workspace_role_assignment retorna 201:** Status correto é `201 Created` com header `Location`. Código que testa apenas `== 200` deve ser atualizado.

### 2026-03
- **Workspace Tags via API (novidade):** `POST /v1/workspaces/{id}/applyTags` e `/removeTags` disponíveis. Tags adicionam metadados compartilhados (time, projeto, cost center). Limite de 10 tags por workspace. Tags visíveis no OneLake Catalog Explorer e na lista de workspaces.
- **Workspace Identity:** Campo `workspaceIdentity` retornado em GET workspace — identidade gerenciada usável para autenticação em shortcuts OneLake e pipelines sem necessidade de SPN externo.

### 2026-02
- **Fabric Identities por tenant:** Limite padrão aumentado de 1.000 para 10.000 identidades (inclui workspace identities). Configurável via Admin REST API (`Update Tenant Setting`).

### 2026-04 (anterior — mantido)
- **Delete workspace via API:** Endpoint `DELETE /v1/workspaces/{workspaceId}` disponivel — use com cautela em producao.
- **List/Delete role assignments:** Endpoints `GET` e `DELETE /v1/workspaces/{workspaceId}/roleAssignments/{id}` documentados e estaveis.
- **Tipo de workspace no retorno:** Campo `type` retornado em `GET /workspaces` (valores: `Workspace`, `AdminWorkspace`, `PersonalWorkspace`).
- **Paginacao via continuationToken:** `GET /v1/workspaces` usa `continuationToken` (nao mais `$skip`) para paginacao consistente.
- **ALM integrado:** A partir de 2025H2, Deployment Pipelines geram commits automaticos em ADO/GitHub ao promover entre stages. Workspaces precisam estar conectados ao Git para este recurso.
- **Capacidade F-SKU obrigatoria:** Git Integration e Deployment Pipelines requerem F-SKU ou P-SKU (Trial e Free nao suportados).
