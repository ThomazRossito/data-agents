---
name: fabric-git-integration
description: Integração Git (GitHub/ADO) com Fabric via REST API para CI/CD, versionamento de workspace e sincronização commit/pull.
updated_at: 2026-04-16
---

# SKILL: fabric-git-integration

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** 2026-04-16
> **Uso:** Leia este arquivo ANTES de integrar Git (GitHub/ADO) com Fabric via REST API.

---

## Overview

Integra workspaces Fabric com GitHub ou Azure DevOps para controle de versao programaticamente --
conecta repositorios, sincroniza conteudo (commit/pull), gerencia credenciais e permite CI/CD
automatizada via REST API.

### O Problema

Versionamento manual de Fabric items (notebook, relatorio, modelo semantico) em Git requer
múltiplas etapas manuais: conectar repo, resolver conflitos, sincronizar branches, gerenciar
credenciais. Alem disso, estrategias de merge (PreferWorkspace vs PreferRemote) e credenciais
(SPN vs User) nao sao faceis de controlar programaticamente.

### A Solucao

Esta skill encapsula o ciclo completo de Git:

- Conexao com GitHub ou Azure DevOps
- Inicializacao com estrategia de sincronizacao (PreferWorkspace/PreferRemote)
- Status do Git e commits pendentes
- Commit para Git (All/Selective modes)
- Pull do Git com politica de resolucao de conflito
- Desconexao segura
- Gerenciamento de credenciais (SPN, User, Automatic)

**Resultado:** Git workflow completo em 2-3 chamadas encapsuladas (conectar + commit + sync).

---

## Quick Start

Exemplo mais comum -- conectar GitHub, fazer commit e puxar atualizacoes:

```python
from git_integration import github_connect, commit_to_git, update_from_git

# 1. Conectar workspace ao repositorio GitHub
github_connect(
    workspace="analytics-dev",
    connection="github-conn",
    owner_name="myorg",
    repository_name="fabric-analytics",
    branch_name="main",
    credential_type="spn"
)

# 2. Fazer commit de todas as mudancas
commit_to_git(
    workspace="analytics-dev",
    mode="All",
    comment="Atualizacao automatica do pipeline"
)

# 3. Sincronizar com remote (pull + merge)
update_from_git(
    workspace="analytics-dev",
    conflict_resolution_policy="PreferWorkspace"
)
# Retorno: True (sincronizado com sucesso)
```

---

## Common Patterns

### 1. `github_connect` -- Conectar ao GitHub

Conecta workspace ao repositorio GitHub com credenciais especificadas.

**Parametros:**

| Parametro       | Tipo | Obrigatorio | Descricao                            |
|-----------------|------|-------------|--------------------------------------|
| `workspace`     | str  | Sim         | ID ou nome do workspace              |
| `connection`    | str  | Sim         | ID ou nome da conexao Git            |
| `owner_name`    | str  | Sim         | Owner do repo (user ou org)          |
| `repository_name` | str | Sim         | Nome do repositorio                  |
| `branch_name`   | str  | Nao         | Branch a conectar (padrao: main)     |
| `directory_name` | str  | Nao         | Diretorio do repo (padrao: /)        |
| `credential_type` | str | Nao         | spn ou user (padrao: spn)           |

**Fluxo interno:**
1. Resolver workspace e connection para IDs
2. Construir payload gitProviderDetails (GitHub) e myGitCredentials
3. `POST /v1/workspaces/{workspaceId}/git/connect`
4. Retorna bool indicando sucesso

**Exemplo:**

```python
from git_integration import github_connect

github_connect(
    workspace="fabric-dev",
    connection="my-github-token",
    owner_name="DataTeam",
    repository_name="fabric-repository",
    branch_name="develop",
    directory_name="/notebooks"
)
```

---

### 2. `ado_connect` -- Conectar ao Azure DevOps

Conecta workspace a repositorio Azure DevOps.

**Parametros:**

| Parametro         | Tipo | Obrigatorio | Descricao                      |
|-------------------|------|-------------|--------------------------------|
| `workspace`       | str  | Sim         | ID ou nome do workspace        |
| `connection_id`   | str  | Sim         | ID da conexao ADO              |
| `organization_name` | str | Sim         | Organizacao ADO               |
| `project_name`    | str  | Sim         | Projeto ADO                    |
| `repository_name` | str  | Sim         | Repositorio do projeto         |
| `branch_name`     | str  | Nao         | Branch (padrao: develop)       |
| `directory_name`  | str  | Nao         | Diretorio (padrao: src)        |

**Fluxo interno:**
1. Resolver workspace para ID
2. Construir payload gitProviderDetails (AzureDevOps)
3. `POST /v1/workspaces/{workspaceId}/git/connect`

**Exemplo:**

```python
from git_integration import ado_connect

ado_connect(
    workspace="fabric-prod",
    connection_id="ado-connection-uuid",
    organization_name="MyOrg",
    project_name="AnalyticsProject",
    repository_name="fabric-content",
    branch_name="main"
)
```

---

### 3. `git_status` -- Verificar status

Obtem status atual do Git (commits pendentes, branch, hash remoto).

**Parametros:**

| Parametro | Tipo | Obrigatorio | Descricao               |
|-----------|------|-------------|-------------------------|
| `workspace` | str | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/git/status`
3. Retorna dict com remoteCommitHash, workspaceHead, branch, etc

**Exemplo:**

```python
from git_integration import git_status

status = git_status(workspace="fabric-dev")
print(f"Remote: {status['remoteCommitHash']}")
print(f"Local: {status['workspaceHead']}")
print(f"Sincronizado: {status['remoteCommitHash'] == status['workspaceHead']}")
```

---

### 4. `commit_to_git` -- Fazer commit

Faz commit de conteudo workspace para Git (All ou Selective).

**Parametros:**

| Parametro           | Tipo | Obrigatorio | Descricao                                  |
|---------------------|------|-------------|---------------------------------------------|
| `workspace`         | str  | Sim         | ID ou nome do workspace                    |
| `mode`              | str  | Nao         | All (todos items) ou Selective (selecionados) |
| `comment`           | str  | Nao         | Mensagem do commit                         |
| `selective_payload` | dict | Nao         | Payload com items selecionados (para Selective) |

**Fluxo interno:**
1. Resolver workspace para ID
2. Construir payload com mode e comment
3. Se mode==Selective, incluir selective_payload (estrutura: {"items": [...]})
4. `POST /v1/workspaces/{workspaceId}/git/commitToGit` com LRO support
5. Polling ate conclusao

**Exemplo - Commit All:**

```python
from git_integration import commit_to_git

result = commit_to_git(
    workspace="fabric-dev",
    mode="All",
    comment="Pipeline automatizado - versao 2.0"
)
# Retorno: {"status": "success", "commitHash": "abc123..."}
```

**Exemplo - Commit Seletivo:**

```python
from git_integration import commit_to_git

selective = {
    "items": [
        {"itemId": "notebook-uuid", "itemType": "Notebook"},
        {"itemId": "model-uuid", "itemType": "SemanticModel"}
    ]
}

result = commit_to_git(
    workspace="fabric-dev",
    mode="Selective",
    comment="Commit seletivo de 2 items",
    selective_payload=selective
)
```

---

### 5. `update_from_git` -- Sincronizar com Git (Pull)

Sincroniza workspace com remote (polling + merge com resolucao de conflito).

**Parametros:**

| Parametro                  | Tipo | Obrigatorio | Descricao                          |
|----------------------------|------|-------------|-------------------------------------|
| `workspace`                | str  | Sim         | ID ou nome do workspace            |
| `conflict_resolution_policy` | str | Nao         | PreferWorkspace ou PreferRemote    |
| `allow_override_items`     | bool | Nao         | Permitir sobrescrever items (default: True) |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/git/status` -- obter remote e local hashes
3. Se ja sincronizado, retornar True
4. Se nao, fazer `POST /v1/workspaces/{workspaceId}/git/updateFromGit`
5. Polling ate workspace sincronizar (até 10 tentativas)

**Exemplo:**

```python
from git_integration import update_from_git

# Sincronizar com preferencia para remote (sobrescreve local)
success = update_from_git(
    workspace="fabric-prod",
    conflict_resolution_policy="PreferRemote"
)

if success:
    print("Workspace sincronizado com sucesso!")
```

---

### 6. `git_disconnect` -- Desconectar do Git

Desconecta workspace do repositorio Git.

**Parametros:**

| Parametro  | Tipo | Obrigatorio | Descricao               |
|------------|------|-------------|-------------------------|
| `workspace` | str | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `POST /v1/workspaces/{workspaceId}/git/disconnect`
3. Retorna bool

**Exemplo:**

```python
from git_integration import git_disconnect

git_disconnect(workspace="fabric-dev")
print("Desconectado do Git")
```

---

## Reference Files

- [git-operations.md](git-operations.md) -- Payloads REST, connection strings, estrategias de branch, credenciais (SPN/User)

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Connection nao encontrada (404)** | Confirme que conexao Git existe no workspace. Create via Fabric UI se necessario. |
| **Repository nao encontrado (404)** | Verifique owner_name, repository_name, branch_name. Confirme token tem acesso. |
| **Conflito de merge (422)** | Items divergiram. Use `conflict_resolution_policy=PreferRemote` ou `PreferWorkspace`. |
| **Credencial invalida (401)** | Token expirado ou permissoes insuficientes. Renew via `update_my_git_credentials()`. |
| **LRO timeout no update** | Workspace grande pode demorar >120s. Polling retenta ate 10x (200s aprox). |
| **Branch nao encontrada** | Confirme branch_name existe no repo remoto. |
| **Directory invalido** | Se directory_name especificado, deve existir no repo. Padrao "/" (raiz) sempre valido. |
| **Permissao insuficiente (403)** | SPN/User nao tem write access ao repo. Verifique permissoes no GitHub/ADO. |
| **Item type nao suportado** | Nem todos Fabric item types suportam Git (ex: Dataflows Gen2 ainda nao). Verifique lista de tipos suportados na doc oficial. |
| **Workspace capacity invalida** | Git Integration requer workspace em capacidade F-SKU ou P-SKU (nao suportado em Trial ou Free). |

---

## Notas de Versao (2026-04)

- **Novos item types suportados:** Fabric agora suporta Git para Eventstreams, KQL Databases e Lakehouses (estrutura de pastas/metadata).
- **Git status granular:** Endpoint `/git/status` agora retorna `conflictedItems` separadamente de `workspaceHead`, facilitando deteccao de conflitos antes do commit.
- **Suporte a multiple directories:** `directory_name` agora aceita subpastas (ex: `/team-a/notebooks`) para organizar multiplos workspaces no mesmo repo.
- **Cross-workspace sync:** Preview de sincronizacao entre workspaces via mesmo branch/directory (feature flag habilitada por workspace admin).
- **Fabric Deployment Pipelines + Git:** A partir de 2025H2, pipelines de deployment geram commits automaticos em ADO/GitHub ao promover entre stages (dev → test → prod).
