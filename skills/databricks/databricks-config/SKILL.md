---
name: databricks-config
description: "Manage Databricks workspace connections: check current workspace, switch profiles, list available workspaces, or authenticate to a new workspace. Use when the user mentions \"switch workspace\", \"which workspace\", \"current profile\", \"databrickscfg\", \"connect to workspace\", \"databricks auth\", \"configure profile\", \"PAT token\", \"service principal\", \"OAuth\", or \"Databricks Connect setup\"."
updated_at: 2026-04-16
source: kb/databricks + skills/databricks-python-sdk
---

# Databricks Config — Workspace & Authentication

Gerenciamento de conexão com workspaces Databricks: troca de perfil, autenticação,
configuração do `~/.databrickscfg` e integração com Databricks Connect.

---

## Operações de Workspace via MCP (sessão atual)

Use o MCP tool `manage_workspace` para todas as operações de workspace em sessão.
**Não edite `~/.databrickscfg` diretamente, não use Bash e não use a Databricks CLI para isso.**

### Passo 1 — Carregar o tool

```
ToolSearch: select:mcp__databricks__manage_workspace
```

### Passo 2 — Mapear intent → action

| Intent do usuário | action | parâmetros adicionais |
|-------------------|--------|-----------------------|
| "qual workspace?" / "status" / "workspace atual" | `status` | — |
| "listar workspaces" / "quais perfis tenho" | `list` | — |
| "trocar para X" / "switch to X" | primeiro `list`, depois `switch` | `profile="<name>"` ou `host="<url>"` |
| "autenticar" / "conectar" / "login" | `login` | `host="<url>"` |

### Passo 3 — Chamar o tool

```python
mcp__databricks__manage_workspace(action="status")
mcp__databricks__manage_workspace(action="list")
mcp__databricks__manage_workspace(action="switch", profile="producao")
mcp__databricks__manage_workspace(action="login", host="https://adb-xxx.azuredatabricks.net")
```

### Passo 4 — Apresentar resultado

- `status` / `switch` / `login`: exibir host, profile ativo, username.
- `list`: tabela formatada com o perfil ativo marcado (`*`).

> **Importante:** O switch é **scoped à sessão MCP** — reseta ao reiniciar o servidor MCP.
> Para mudança permanente, use `databricks auth login -p <profile>` e edite `~/.databrickscfg`.

---

## Configuração Permanente — `~/.databrickscfg`

### Estrutura do arquivo

```ini
[DEFAULT]
host  = https://adb-1234567890.azuredatabricks.net
token = dapi...

[producao]
host                  = https://adb-0987654321.azuredatabricks.net
token                 = dapi...
cluster_id            = 0123-456789-abcdef      # cluster interativo padrão
serverless_compute_id = auto                     # usa serverless quando disponível

[homologacao]
host  = https://adb-1111111111.azuredatabricks.net
token = dapi...

[azure-sp]
host                         = https://adb-2222222222.azuredatabricks.net
azure_tenant_id              = <tenant-id>
azure_client_id              = <client-id>
azure_client_secret          = <secret>
azure_workspace_resource_id  = /subscriptions/.../resourceGroups/.../providers/Microsoft.Databricks/workspaces/...
```

### Campos importantes por tipo de auth

| Campo | Tipo de auth | Descrição |
|-------|--------------|-----------|
| `host` | todos | URL do workspace (obrigatório) |
| `token` | PAT | Personal Access Token (`dapi...`) |
| `azure_tenant_id` | Azure SP | ID do tenant Azure AD |
| `azure_client_id` | Azure SP | Client ID do Service Principal |
| `azure_client_secret` | Azure SP | Secret do SP |
| `azure_workspace_resource_id` | Azure SP | ARM resource ID do workspace |
| `cluster_id` | Connect/CLI | Cluster padrão para Databricks Connect |
| `serverless_compute_id` | Connect/CLI | `auto` para usar serverless automaticamente |

### Criar/atualizar perfil permanentemente via CLI

```bash
# PAT interativo (abre browser ou pede token)
databricks auth login --host https://adb-xxx.azuredatabricks.net --profile producao

# Configuração manual com token
databricks configure --token --profile producao
# Interativo: pede host e token

# Verificar qual perfil está ativo
databricks auth profiles

# Testar autenticação de um perfil
databricks auth describe --profile producao
```

---

## Autenticação por Variáveis de Ambiente

Alternativa ao `~/.databrickscfg`. Tem precedência sobre arquivo de config.

```bash
# PAT authentication
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...

# Azure Service Principal
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export ARM_TENANT_ID=<tenant-id>
export ARM_CLIENT_ID=<client-id>
export ARM_CLIENT_SECRET=<secret>
```

No Python (SDK):

```python
from databricks.sdk import WorkspaceClient

# Auto-detecta variáveis de ambiente ou DEFAULT profile
w = WorkspaceClient()

# Perfil explícito
w = WorkspaceClient(profile="producao")

# Credenciais inline (evitar em produção — use vars de ambiente)
w = WorkspaceClient(
    host="https://adb-xxx.azuredatabricks.net",
    token="dapi..."
)

# Azure Service Principal
w = WorkspaceClient(
    host="https://adb-xxx.azuredatabricks.net",
    azure_workspace_resource_id="/subscriptions/.../Microsoft.Databricks/workspaces/...",
    azure_tenant_id="<tenant-id>",
    azure_client_id="<client-id>",
    azure_client_secret="<secret>"
)
```

> **Nunca** inclua tokens ou secrets diretamente no código. Use variáveis de ambiente
> ou Databricks Secrets (via `dbutils.secrets.get`).

---

## Databricks Connect — Setup e Seleção de Perfil

Databricks Connect permite rodar PySpark localmente contra um workspace remoto.
Requer **Python 3.12** e `databricks-connect >= 16.4.0`.

```bash
# Instalação
pip install databricks-connect==16.4.0

# Verificar configuração
databricks configure --token --profile databricks
```

```python
from databricks.connect import DatabricksSession

# Usa perfil DEFAULT de ~/.databrickscfg
spark = DatabricksSession.builder.getOrCreate()

# Perfil específico
spark = DatabricksSession.builder.profile("producao").getOrCreate()

# Credenciais inline
spark = DatabricksSession.builder \
    .remote(
        host="https://adb-xxx.azuredatabricks.net",
        token="dapi...",
        cluster_id="0123-456789-abcdef"
    ).getOrCreate()

df = spark.sql("SELECT * FROM main.analytics.users")
df.show()
```

**Regras críticas para Databricks Connect:**
- **NUNCA** use `.master("local[*]")` — quebra a conexão remota.
- O `cluster_id` pode ser definido no perfil `~/.databrickscfg` (campo `cluster_id`).
- Use `serverless_compute_id = auto` no perfil para Serverless sem cluster fixo.
- Requer Python 3.12 — versões anteriores não são suportadas com `>=16.4`.

---

## Ordem de Precedência de Autenticação

O SDK e a CLI seguem esta ordem (do mais ao menos prioritário):

1. Parâmetros explícitos no código (inline)
2. Variáveis de ambiente (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `ARM_*`)
3. Perfil explícito via `profile=` ou `--profile`
4. Perfil `DEFAULT` em `~/.databrickscfg`
5. Azure Managed Identity / Instance Profile (quando em VM Azure/EC2)

---

## Diagnóstico de Problemas Comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Profile 'X' not found` | Perfil não existe no `~/.databrickscfg` | Rodar `databricks auth login --profile X` |
| `401 Unauthorized` | Token expirado ou inválido | Gerar novo PAT no workspace → User Settings → Developer |
| `Connection refused` | Host incorreto ou firewall | Verificar `DATABRICKS_HOST` (incluir `https://`) |
| Databricks Connect falha silenciosamente | Python != 3.12 ou versão errada do pacote | `python3.12 -m pip install databricks-connect==16.4.0` |
| MCP switch não persiste | Session-scoped, reseta no restart | Usar `databricks auth login` para persistência |

---

## Checklist de Configuração

- [ ] `~/.databrickscfg` com pelo menos o perfil `DEFAULT`
- [ ] `databricks auth describe --profile <nome>` retorna `username` correto
- [ ] Para Databricks Connect: Python 3.12 instalado e `databricks-connect` instalado
- [ ] Token PAT com data de expiração configurada (evitar tokens sem expiração)
- [ ] Secrets sensíveis no Databricks Secrets, não em arquivos de texto

---

## Skills Relacionadas

- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** — WorkspaceClient APIs completas
- **[databricks-execution-compute](../databricks-execution-compute/SKILL.md)** — execução de código e compute
- **[databricks-bundles](../databricks-bundles/SKILL.md)** — DABs: targets, variáveis de ambiente, deploy
