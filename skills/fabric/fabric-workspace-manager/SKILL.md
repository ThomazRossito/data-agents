---
updated_at: 2026-04-16
source: kb-crossref + skills-crossref
---

# SKILL: fabric-workspace-manager

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** 2026-04-16
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
- Listagem, criação, atualização e remoção de role assignments
- Vinculação e desvinculação de capacidade (com polling para LRO)
- Resolução de workspaces por nome ou ID
- Validação e tratamento de erros nas respostas de status 202 (aceito), 409 (conflito) e 422 (entidade invalida)

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
# Retorno: {"status": "success", "principal": {...}, "role": "Admin"}
```

---

## Common Patterns

### 1. `list_workspaces` -- Listar todos os workspaces

Leitura somente. Suporta paginação automática.

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| `df` | bool | Nao | Se True, retorna DataFrame; se False, lista de dicts |

**Fluxo interno:**
1. `GET /v1/workspaces` (com paginação via `continuationToken`)
2. Retorna lista de workspaces com campos: id, displayName, description, capacityId, type

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

**Parametros:**

| Parametro      | Tipo   | Obrigatorio | Descricao                                   |
|----------------|--------|-------------|---------------------------------------------|
| `display_name` | str    | Sim         | Nome do workspace                           |
| `capacity`     | str    | Nao         | Nome ou ID da capacidade                    |
| `description`  | str    | Nao         | Descricao do workspace                      |

**Fluxo interno:**
1. Construir payload com displayName, capacityId (resolvido), description
2. `POST /v1/workspaces` com payload
3. Retorna detalhes do workspace criado (id, displayName, etc)

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

**Parametros:**

| Parametro    | Tipo   | Obrigatorio | Descricao                                          |
|--------------|--------|-------------|-----------------------------------------------------|
| `workspace`  | str    | Sim         | ID ou nome do workspace                            |
| `user_uuid`  | str    | Sim         | ID do usuario/grupo/SPN                            |
| `user_type`  | str    | Nao         | User, Group, ServicePrincipal, ServicePrincipalProfile |
| `role`       | str    | Nao         | Admin, Contributor, Member, Viewer (padrao: Admin) |

**Fluxo interno:**
1. Validar user_type e role contra listas de valores permitidos
2. `POST /v1/workspaces/{workspaceId}/roleAssignments` com principal e role
3. Retorna detalhes da atribuicao

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

Lista todas as atribuições de papel no workspace.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/roleAssignments`
3. Retorna array de `{ "id": "...", "principal": {...}, "role": "..." }`

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
| `user_uuid` | str  | Sim         | ID do principal            |
| `role`      | str  | Nao         | Novo papel (default: Admin) |

**Fluxo interno:**
1. Resolver workspace para ID
2. Validar role
3. `PATCH /v1/workspaces/{workspaceId}/roleAssignments/{userUuid}` com payload role
4. Retorna atribuicao atualizada

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
| `user_uuid` | str  | Sim         | ID do principal         |

**Fluxo interno:**
1. Resolver workspace para ID
2. `DELETE /v1/workspaces/{workspaceId}/roleAssignments/{userUuid}`
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
2. `POST /v1/workspaces/{workspaceId}/assignToCapacity` ou `/unassignFromCapacity`
3. Aguardar status 202 (aceito) — LRO iniciada; workspace vinculado em ~10-30s em background

**Exemplo:**

```python
from workspace_manager import assign_to_capacity, unassign_from_capacity

# Vincular workspace a capacidade
assign_to_capacity(
    workspace="Sales-Q2-2026",
    capacity="premium-capacity"
)

# Desvincullar de capacidade
unassign_from_capacity(
    workspace="Sales-Q2-2026"
)
```

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

Quando `assign_to_capacity` retorna 202, o vínculo ocorre em background. Para confirmar
conclusão antes de prosseguir:

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

    # Polling via GET workspace até capacityId estar preenchido
    for attempt in range(max_retries):
        time.sleep(5)
        ws = requests.get(f"{base_url}/workspaces/{workspace_id}", headers=headers).json()
        if ws.get("capacityId") == capacity_id:
            return True
        print(f"Aguardando vínculo de capacidade... tentativa {attempt + 1}/{max_retries}")

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
| **Status 202 (LRO)** | Operacao de capacidade iniciada. O workspace sera vinculado em background; polling recomendado. |
| **Status 409 (Conflito)** | Nome de workspace duplicado ou conflito de estado. Workspace com mesmo displayName ja existe — use nome diferente. |
| **Status 422 (Entidade invalida)** | Workspace ja tem essa capacidade ou validacao de negocio falhou. Aguarde alguns segundos e retry. |
| **Token expirado (401)** | Renove token via Azure Identity. Nunca hardcode -- use Key Vault. |
| **Permissao insuficiente (403)** | Usuario autenticado nao tem permissao Admin no workspace para RBAC. |
| **Rate limit (429)** | Muitas requisicoes. Implemente backoff exponencial; adicione `time.sleep(1)` entre operacoes em lote. |
| **Workspace em Trial/Free capacity** | Git Integration e Deployment Pipelines requerem F-SKU ou P-SKU. Mova para capacidade paga antes de usar ALM. |

---

## Notas de Versao (2026-04)

- **Delete workspace via API:** Endpoint `DELETE /v1/workspaces/{workspaceId}` disponivel — use com cautela em producao.
- **List/Delete role assignments:** Endpoints `GET` e `DELETE /v1/workspaces/{workspaceId}/roleAssignments/{userUuid}` agora documentados e estaveis.
- **Tipo de workspace no retorno:** Campo `type` agora retornado em `GET /workspaces` (valores: `Workspace`, `AdminWorkspace`, `PersonalWorkspace`).
- **Paginacao via continuationToken:** `GET /v1/workspaces` agora usa `continuationToken` (nao mais `$skip`) para paginacao consistente em listas grandes.
- **ALM integrado:** A partir de 2025H2, Deployment Pipelines geram commits automaticos em ADO/GitHub ao promover entre stages (dev → test → prod). Workspaces precisam estar conectados ao Git para este recurso.
- **Capacidade F-SKU obrigatoria:** Git Integration e Deployment Pipelines requerem F-SKU ou P-SKU (Trial e Free nao suportados).
