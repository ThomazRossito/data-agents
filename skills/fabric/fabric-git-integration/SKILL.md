---
name: fabric-git-integration
description: Integração Git (GitHub/ADO) com Fabric via REST API para CI/CD, versionamento de workspace e sincronização commit/pull.
updated_at: 2026-04-23
source: web_search
---

# SKILL: fabric-git-integration

> **Fonte:** Microsoft Fabric REST API (api.fabric.microsoft.com/v1)
> **Atualizado:** 2026-04-23
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
- Gerenciamento de credenciais (SPN via ConfiguredConnection, Automatic)

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

> ⚠️ **Novo campo em 2025-2026:** `custom_domain_name` adicionado ao payload `gitProviderDetails`
> para suporte a GitHub Enterprise Cloud com dominio customizado (ex: `my-enterprise.ghe.com`).
> GitHub Enterprise Server com dominio customizado **nao** e suportado mesmo que publicamente acessivel.

Conecta workspace ao repositorio GitHub com credenciais especificadas.

**Parametros:**

| Parametro          | Tipo | Obrigatorio | Descricao                                       |
|--------------------|------|-------------|--------------------------------------------------|
| `workspace`        | str  | Sim         | ID ou nome do workspace                         |
| `connection`       | str  | Sim         | ID ou nome da conexao Git                       |
| `owner_name`       | str  | Sim         | Owner do repo (user ou org)                     |
| `repository_name`  | str  | Sim         | Nome do repositorio                             |
| `branch_name`      | str  | Nao         | Branch a conectar (padrao: main)                |
| `directory_name`   | str  | Nao         | Diretorio do repo (padrao: /)                   |
| `credential_type`  | str  | Nao         | `spn` ou `automatic` (padrao: `spn`)            |
| `custom_domain_name` | str | Nao        | Dominio customizado para GitHub Enterprise Cloud |

**Fluxo interno:**
1. Resolver workspace e connection para IDs
2. Construir payload `gitProviderDetails` (GitHub) com `ownerName` e opcionalmente `customDomainName`
3. Construir `myGitCredentials` com `source: ConfiguredConnection` e `connectionId`
4. `POST /v1/workspaces/{workspaceId}/git/connect`
5. Retorna bool indicando sucesso

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

# GitHub Enterprise Cloud com dominio customizado:
github_connect(
    workspace="fabric-dev",
    connection="ghe-conn",
    owner_name="DataTeam",
    repository_name="fabric-repository",
    branch_name="main",
    custom_domain_name="my-enterprise.ghe.com"
)
```

**Payload REST de referencia (GitHub):**

```json
{
  "gitProviderDetails": {
    "gitProviderType": "GitHub",
    "ownerName": "DataTeam",
    "repositoryName": "fabric-repository",
    "branchName": "develop",
    "directoryName": "/notebooks",
    "customDomainName": "my-enterprise.ghe.com"
  },
  "myGitCredentials": {
    "source": "ConfiguredConnection",
    "connectionId": "<uuid-da-conexao>"
  }
}
```

---

### 2. `ado_connect` -- Conectar ao Azure DevOps

> ⚠️ **Breaking change / GA em dez/2025:** SPN para ADO agora e **Generally Available**.
> O fluxo mudou: antes de chamar `ado_connect`, e necessario criar a conexao ADO via
> `POST /v1/connections` com `credentialType: ServicePrincipal` (ou `WorkspaceIdentity`).
> Autenticacao por UserPrincipal **nao e suportada** via REST (requer OAuth2 interativo).
> Cross-tenant (Fabric e ADO em tenants distintos) tambem e suportado desde essa versao.

Conecta workspace a repositorio Azure DevOps.

**Parametros:**

| Parametro           | Tipo | Obrigatorio | Descricao                               |
|---------------------|------|-------------|------------------------------------------|
| `workspace`         | str  | Sim         | ID ou nome do workspace                 |
| `connection_id`     | str  | Sim         | ID da conexao ADO (ConfiguredConnection) |
| `organization_name` | str  | Sim         | Organizacao ADO                         |
| `project_name`      | str  | Sim         | Projeto ADO                             |
| `repository_name`   | str  | Sim         | Repositorio do projeto                  |
| `branch_name`       | str  | Nao         | Branch (padrao: develop)                |
| `directory_name`    | str  | Nao         | Diretorio (padrao: src)                 |

**Fluxo interno:**
1. **Pre-requisito:** Criar conexao ADO com SPN via `POST /v1/connections`
   - `connectivityType: ShareableCloud`
   - `connectionDetails.type: AzureDevOpsSourceControl`
   - `credentialDetails.credentials.credentialType: ServicePrincipal`
2. Resolver workspace para ID
3. Construir payload `gitProviderDetails` (AzureDevOps)
4. `POST /v1/workspaces/{workspaceId}/git/connect` com `source: ConfiguredConnection`

**Exemplo:**

```python
from git_integration import ado_connect

# Passo 1: Criar conexao ADO com SPN (uma vez por ambiente)
# POST /v1/connections -- ver payload abaixo
connection_id = create_ado_spn_connection(
    display_name="ado-spn-prod",
    ado_url="https://dev.azure.com/MyOrg/MyProject/_git/MyRepo",
    tenant_id="<tenant-id>",
    client_id="<sp-client-id>",
    client_secret="<sp-secret>"
)

# Passo 2: Conectar workspace usando a conexao criada
ado_connect(
    workspace="fabric-prod",
    connection_id=connection_id,
    organization_name="MyOrg",
    project_name="AnalyticsProject",
    repository_name="fabric-content",
    branch_name="main"
)
```

**Payload REST de referencia -- criacao de conexao ADO com SPN:**

```json
POST /v1/connections
{
  "displayName": "ado-spn-prod",
  "connectivityType": "ShareableCloud",
  "connectionDetails": {
    "type": "AzureDevOpsSourceControl",
    "creationMethod": "AzureDevOpsSourceControl.Contents",
    "parameters": [
      { "dataType": "Text", "name": "url",
        "value": "https://dev.azure.com/<org>/<project>/_git/<repo>" }
    ]
  },
  "credentialDetails": {
    "credentials": {
      "credentialType": "ServicePrincipal",
      "tenantId": "<sp-tenant-id>",
      "servicePrincipalClientId": "<sp-client-id>",
      "servicePrincipalSecret": "<sp-secret>"
    }
  }
}
```

**Payload REST de referencia -- connect:**

```json
POST /v1/workspaces/{workspaceId}/git/connect
{
  "gitProviderDetails": {
    "gitProviderType": "AzureDevOps",
    "organizationName": "MyOrg",
    "projectName": "AnalyticsProject",
    "repositoryName": "fabric-content",
    "branchName": "main",
    "directoryName": "src"
  },
  "myGitCredentials": {
    "source": "ConfiguredConnection",
    "connectionId": "<uuid-da-conexao>"
  }
}
```

> **Nota cross-tenant:** Se Fabric e ADO estao em tenants distintos, registre o app como
> multitenant e crie o service principal no tenant do ADO antes de usar a conexao.

---

### 3. `git_status` -- Verificar status

Obtem status atual do Git (commits pendentes, branch, hash remoto, itens em conflito).

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/git/status`
3. Retorna dict com `remoteCommitHash`, `workspaceHead`, `branch`, `conflictedItems`, etc

> **Nota:** O endpoint `/git/status` retorna `conflictedItems` como lista separada,
> permitindo detectar conflitos antes de iniciar commit ou pull.

**Exemplo:**

```python
from git_integration import git_status

status = git_status(workspace="fabric-dev")
print(f"Remote: {status['remoteCommitHash']}")
print(f"Local:  {status['workspaceHead']}")
print(f"Sincronizado: {status['remoteCommitHash'] == status['workspaceHead']}")

# Verificar conflitos antes de commit/pull
if status.get("conflictedItems"):
    print(f"Itens em conflito: {status['conflictedItems']}")
```

---

### 4. `commit_to_git` -- Fazer commit

Faz commit de conteudo workspace para Git (All ou Selective).

> ⚠️ **Limite operacional:** O tamanho total combinado dos arquivos em um unico commit e limitado
> a **50 MB**. Se necessario, divida em commits menores usando o modo Selective.
> Workspaces com mais de **1.000 itens** podem falhar na sincronizacao -- divida em workspaces menores.

**Parametros:**

| Parametro           | Tipo | Obrigatorio | Descricao                                          |
|---------------------|------|-------------|-----------------------------------------------------|
| `workspace`         | str  | Sim         | ID ou nome do workspace                            |
| `mode`              | str  | Nao         | `All` (todos items) ou `Selective` (selecionados)  |
| `comment`           | str  | Nao         | Mensagem do commit                                 |
| `selective_payload` | dict | Nao         | Payload com items selecionados (para `Selective`)  |

**Fluxo interno:**
1. Resolver workspace para ID
2. Construir payload com `mode` e `comment`
3. Se `mode==Selective`, incluir `selective_payload` (estrutura: `{"items": [...]}`)
4. `POST /v1/workspaces/{workspaceId}/git/commitToGit` com LRO support
5. Polling ate conclusao (retorna `Location` header + `x-ms-operation-id`)

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
        {"itemId": "model-uuid",    "itemType": "SemanticModel"}
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

| Parametro                    | Tipo | Obrigatorio | Descricao                              |
|------------------------------|------|-------------|----------------------------------------|
| `workspace`                  | str  | Sim         | ID ou nome do workspace               |
| `conflict_resolution_policy` | str  | Nao         | `PreferWorkspace` ou `PreferRemote`   |
| `allow_override_items`       | bool | Nao         | Permitir sobrescrever items (default: True) |

**Fluxo interno:**
1. Resolver workspace para ID
2. `GET /v1/workspaces/{workspaceId}/git/status` -- obter `remoteCommitHash` e `workspaceHead`
3. Se ja sincronizado, retornar `True`
4. Construir payload com `workspaceHead`, `remoteCommitHash`, `conflictResolution` e `options`
5. `POST /v1/workspaces/{workspaceId}/git/updateFromGit`
6. Polling via `Location` header ate workspace sincronizar (ate 10 tentativas)

**Payload REST de referencia:**

```json
POST /v1/workspaces/{workspaceId}/git/updateFromGit
{
  "workspaceHead": "<workspaceHead-hash>",
  "remoteCommitHash": "<remoteCommitHash>",
  "conflictResolution": {
    "conflictResolutionType": "Workspace",
    "conflictResolutionPolicy": "PreferWorkspace"
  },
  "options": {
    "allowOverrideItems": true
  }
}
```

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

> **Nota:** Somente o workspace admin pode desconectar o workspace do Git,
> tanto via UI quanto via API.

**Parametros:**

| Parametro   | Tipo | Obrigatorio | Descricao               |
|-------------|------|-------------|-------------------------|
| `workspace` | str  | Sim         | ID ou nome do workspace |

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

- [git-operations.md](git-operations.md) -- Payloads REST, connection strings, estrategias de branch, credenciais (SPN/Automatic)

---

## Novas Capacidades (Preview) -- FabCon 2026 / Marco 2026

As features abaixo estao em **Preview** a partir de marco/2026. Nao ha endpoints REST
exclusivos para elas -- sao expostas via UI e, onde aplicavel, via parametros ja existentes.

### Selective Branching (Preview)

Permite fazer branch-out incluindo apenas um subconjunto de items do workspace, em vez de
copiar tudo. Util para workspaces grandes onde clonar todos os items e lento e desnecessario.

- Na UI: `Source control > Branches > Branch out to another workspace > Select items individually`
- Os items relacionados necessarios sao incluidos automaticamente para manter consistencia

### Branched Workspaces (Preview)

Experiencia explicitamente desenhada para desenvolvimento isolado em feature branches.
Cada developer trabalha em seu proprio workspace conectado ao seu proprio branch, sem
impactar o workspace compartilhado da equipe.

### Compare Code Changes / Diff (Preview)

Exibe diffs em nivel de item e de arquivo **antes** de commit ou pull. Remove o risco de
sincronizar alteracoes sem revisao previa. Disponivel nos fluxos de commit e de update-from-git.

### Commit para branch standalone (jan/2026)

Permite criar um novo branch a partir do ultimo ponto de sincronizacao e fazer commit das
mudancas atuais em uma unica acao, sem necessidade de conectar previamente o workspace ao
novo branch.

---

## SDK Python (Preview -- jan/2026)

O SDK `microsoft-fabric-api` esta disponivel no PyPI como alternativa a chamadas REST manuais.
Encapsula autenticacao e operacoes comuns do Fabric REST API.

```bash
pip install microsoft-fabric-api
```

> Use o SDK para ambientes de prototipagem e automacao interna. Para producao, mantenha
> controle explicito sobre os payloads REST documentados nesta skill.

---

## Item Types Suportados no Git

A lista de item types suportados continua crescendo. Item types **nao suportados** sao ignorados
(nao sincronizados, nao deletados) quando o workspace e conectado. Principais suportados:

| Categoria             | Item Types                                                   |
|-----------------------|--------------------------------------------------------------|
| Power BI              | Report, Semantic Model, Paginated Report                     |
| Data Engineering      | Notebook, Lakehouse, Spark Job Definition, Spark Environment |
| Data Warehouse        | Warehouse, Data Pipeline                                     |
| Real-Time Intelligence| **Eventhouse**, **KQL Database**, **KQL Queryset**, **Real-Time Dashboard** |
| Extensibilidade       | User Data Functions                                          |

> **RTI GA:** Eventhouses e KQL Databases incluem integracao em nivel de dados (schema,
> tabelas, funcoes, materialized views via KQL script) -- nao apenas metadata.
>
> **Ainda nao suportados (verifique docs oficiais):** Dataflows Gen2, alguns tipos de
> mirrored databases. Consulte sempre a lista oficial antes de assumir suporte.

---

## Common Issues

| Issue | Solution |
|-------|----------|
| **Connection nao encontrada (404)** | Confirme que conexao Git existe. Para SPN/ADO, crie primeiro via `POST /v1/connections`. |
| **Repository nao encontrado (404)** | Verifique `owner_name`, `repository_name`, `branch_name`. Confirme token/SPN tem acesso. |
| **Conflito de merge (422)** | Items divergiram. Use `conflict_resolution_policy=PreferRemote` ou `PreferWorkspace`. Inspecione `conflictedItems` via `/git/status` antes. |
| **Credencial invalida (401)** | Token expirado ou permissoes insuficientes. Renew via `update_my_git_credentials()` ou atualize a conexao em Manage Connections. |
| **LRO timeout no update** | Workspace grande pode demorar >120s. Polling retenta ate 10x (~200s). |
| **Branch nao encontrada** | Confirme `branch_name` existe no repo remoto. |
| **Directory invalido** | Se `directory_name` especificado, deve existir no repo. Padrao `/` (raiz) sempre valido. Subdiretorios aceitos (ex: `/team-a/notebooks`). |
| **Permissao insuficiente (403)** | SPN/User nao tem write access ao repo. Verifique permissoes no GitHub/ADO. Para disconnect, exige workspace admin. |
| **Item type nao suportado** | Items nao suportados sao ignorados silenciosamente. Confirme a lista oficial de tipos suportados. |
| **Workspace capacity invalida** | Git Integration requer workspace em capacidade F-SKU ou P-SKU. Power BI Premium Per User suporta apenas Power BI items. Trial e Free nao suportados. |
| **Commit > 50 MB** | Divida em commits menores usando modo Selective. |
| **Workspace > 1.000 itens** | Sincronizacao pode falhar. Divida em workspaces menores ou use diretorios distintos no mesmo branch. |
| **ADO + IP Conditional Access** | Azure DevOps nao e suportado quando "Enable IP Conditional Access policy validation" esta habilitado no tenant. |
| **Cross-geo** | Se workspace e repo estao em regioes geograficas distintas, o tenant admin deve habilitar cross-geo exports. |
| **GitHub Enterprise Server** | GitHub Enterprise Server com dominio customizado **nao** e suportado, mesmo se publicamente acessivel. Somente GitHub Enterprise Cloud com `customDomainName`. |
| **UserPrincipal via REST (ADO)** | ADO via UserPrincipal nao e suportado programaticamente (requer OAuth2 interativo). Use SPN via `ConfiguredConnection`. |

---

## Notas de Versao

### 2026-03 (FabCon 2026)
- **Selective Branching (Preview):** Branch-out com subset de items; inclui automaticamente dependencias.
- **Branched Workspaces (Preview):** Workspaces isolados por feature branch com experiencia redesenhada.
- **Compare Code Changes / Diff (Preview):** Diff em nivel de item e arquivo antes de commit ou pull.
- **Notebook auto-binding no Git:** Reduz reconfiguracao quando notebooks sao movidos entre workspaces.
- **Bulk Export/Import API (Preview):** Nova alternativa CI/CD via `POST /v1/workspaces/{id}/items/bulkExport` e `bulkImport` para deploy em lote sem Git (complementar, nao substitui).

### 2026-01
- **Commit para branch standalone:** Criar branch e commitar mudancas atuais em uma unica acao.
- **Python SDK `microsoft-fabric-api`** disponivel no PyPI (preview).

### 2025-12
- **SPN para ADO (GA):** Service principal e cross-tenant para Azure DevOps agora Generally Available. Fluxo: criar conexao via `POST /v1/connections` com `credentialType: ServicePrincipal`, depois usar `connectionId` no connect.
- **Cross-tenant ADO suportado:** Cenarios onde Fabric e ADO estao em tenants distintos agora sao cobertos com registro de app multitenant.

### 2025 (geral)
- **Real-Time Intelligence GA no Git:** Eventhouses, KQL Databases, KQL Querysets e Real-Time Dashboards com integracao de dados (schema KQL) e metadata.
- **User Data Functions no Git:** Suporte via arquivo `function-app.py` + `definitions.json`.
- **`customDomainName` no GitHub payload:** Para GitHub Enterprise Cloud com dominio customizado.
- **Workspace structure preservada:** Subpastas do workspace sao espelhadas no repositorio Git.
