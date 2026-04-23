---
name: databricks-config
description: "Manage Databricks workspace connections: check current workspace, switch profiles, list available workspaces, or authenticate to a new workspace. Use when the user mentions \"switch workspace\", \"which workspace\", \"current profile\", \"databrickscfg\", \"connect to workspace\", \"databricks auth\", \"configure profile\", \"PAT token\", \"service principal\", \"OAuth\", or \"Databricks Connect setup\"."
updated_at: 2026-04-23
source: web_search
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

[azure-sp-oauth]
# OAuth M2M — preferido sobre azure_client_secret para SPs
host          = https://adb-2222222222.azuredatabricks.net
client_id     = <service-principal-client-id>
client_secret = <service-principal-oauth-secret>
```

### Campos importantes por tipo de auth

| Campo | Tipo de auth | Descrição |
|-------|--------------|-----------|
| `host` | todos | URL do workspace (obrigatório) |
| `token` | PAT | Personal Access Token (`dapi...`) |
| `client_id` | OAuth M2M (SP) | Client ID do Service Principal |
| `client_secret` | OAuth M2M (SP) | OAuth secret do SP (não confundir com `azure_client_secret`) |
| `azure_tenant_id` | Azure SP (legado) | ID do tenant Azure AD |
| `azure_client_id` | Azure SP (legado) | Client ID do Service Principal |
| `azure_client_secret` | Azure SP (legado) | Secret do SP via ARM |
| `azure_workspace_resource_id` | Azure SP (legado) | ARM resource ID do workspace |
| `cluster_id` | Connect/CLI | Cluster padrão para Databricks Connect |
| `serverless_compute_id` | Connect/CLI | `auto` para usar serverless automaticamente |

> **Nota:** Para autenticação de Service Principals, prefira OAuth M2M (`client_id` + `client_secret`)
> sobre o fluxo ARM (`azure_client_secret`). A Databricks recomenda OAuth sobre PAT para contas de usuário
> pela maior segurança dos tokens de curta duração.

### Criar/atualizar perfil permanentemente via CLI

```bash
# OAuth U2M interativo — RECOMENDADO (abre browser, tokens de curta duração)
databricks auth login --host https://adb-xxx.azuredatabricks.net --profile producao

# Configuração manual com PAT (legado, ainda suportado)
databricks configure --token --profile producao
# Interativo: pede host e token

# Listar todos os perfis e verificar validade
databricks auth profiles

# Inspecionar variáveis de ambiente de um perfil (inclui token desofuscado)
databricks auth env --profile producao

# Testar autenticação de um perfil (detalha método e origem das credenciais)
databricks auth describe --profile producao
```

---

## Autenticação por Variáveis de Ambiente

Alternativa ao `~/.databrickscfg`. Tem precedência sobre arquivo de config.

```bash
# PAT authentication
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export DATABRICKS_TOKEN=dapi...

# Azure Service Principal (ARM — legado)
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export ARM_TENANT_ID=<tenant-id>
export ARM_CLIENT_ID=<client-id>
export ARM_CLIENT_SECRET=<secret>

# OAuth M2M Service Principal — preferido
export DATABRICKS_HOST=https://adb-xxx.azuredatabricks.net
export DATABRICKS_CLIENT_ID=<client-id>
export DATABRICKS_CLIENT_SECRET=<oauth-secret>

# Forçar perfil específico sem alterar código
export DATABRICKS_CONFIG_PROFILE=producao

# Caminho alternativo para o .databrickscfg
export DATABRICKS_CONFIG_FILE=/path/to/custom/.databrickscfg
```

No Python (SDK):

```python
from databricks.sdk import WorkspaceClient

# Auto-detecta variáveis de ambiente ou DEFAULT profile
w = WorkspaceClient()

# Perfil explícito
w = WorkspaceClient(profile="producao")

# Forçar método de auth específico (evita ambiguidade quando múltiplos métodos disponíveis)
w = WorkspaceClient(
    host="https://adb-xxx.azuredatabricks.net",
    auth_type="azure-cli"   # ou "pat", "azure-client-secret", "databricks-cli"
)

# Credenciais inline (evitar em produção — use vars de ambiente)
w = WorkspaceClient(
    host="https://adb-xxx.azuredatabricks.net",
    token="dapi..."
)

# Azure Service Principal (ARM — legado)
w = WorkspaceClient(
    host="https://adb-xxx.azuredatabricks.net",
    azure_workspace_resource_id="/subscriptions/.../Microsoft.Databricks/workspaces/...",
    azure_tenant_id="<tenant-id>",
    azure_client_id="<client-id>",
    azure_client_secret="<secret>"
)

# Custom headers em todas as requisições (adicionado em versão recente do SDK)
w = WorkspaceClient(
    profile="producao",
    custom_headers={"X-My-Header": "value"}
)
```

> ⚠️ **Depreciação (SDK Python, 2025-2026):** `WorkspaceClient.serving_endpoints.get_open_ai_client()`
> e `get_langchain_chat_open_ai_client()` foram depreciados em favor de pacotes dedicados.
> Remova chamadas a esses métodos se existirem no código.

> **Nunca** inclua tokens ou secrets diretamente no código. Use variáveis de ambiente
> ou Databricks Secrets (via `dbutils.secrets.get`).

---

## Databricks Connect — Setup e Seleção de Perfil

> ⚠️ **Breaking change em 18.x:** O requisito mínimo de `pyarrow` foi elevado de
> `>=11.0.0` para `>=18.0.0`. Ambientes que fixam `pyarrow<18` quebrarão ao usar
> `databricks-connect==18.*`.

> ⚠️ **Restrição de pandas (desde 17.3, jan/2026):** versões suportadas limitadas a
> `1.0.5 <= pandas < 3`. `pandas>=3` não é suportado para evitar quebras em `pyspark.pandas`.

Databricks Connect permite rodar PySpark localmente contra um workspace remoto.
Requer **Python 3.12** e `databricks-connect` compatível com o DBR do cluster/serverless alvo.

Os números de versão do Databricks Connect correspondem aos números de versão do Databricks Runtime. A versão do Databricks Runtime do compute deve ser maior ou igual à versão do pacote Databricks Connect. A Databricks recomenda usar o pacote Databricks Connect mais recente que corresponda à sua versão do Databricks Runtime.

A versão mais recente disponível é `18.1.2` (março/2026), suportando DBR 18.1.

```bash
# Instalação — use notação X.Y.* para pegar o patch mais recente da minor
pip install "databricks-connect==18.1.*"   # ou 17.3.* para DBR 17.3 LTS, etc.

# Se PySpark estiver instalado, remova antes (conflito de pacotes)
pip uninstall pyspark databricks-connect
pip install "databricks-connect==18.1.*"

# Verificar configuração de auth (reutiliza ~/.databrickscfg)
databricks auth describe --profile producao
```

```python
from databricks.connect import DatabricksSession

# Usa perfil DEFAULT de ~/.databrickscfg
spark = DatabricksSession.builder.getOrCreate()

# Perfil específico
spark = DatabricksSession.builder.profile("producao").getOrCreate()

# Sempre cria uma nova sessão Spark (não reutiliza existente)
# Adicionado em DBConnect 16.x — desabilitado por padrão em notebooks
spark = DatabricksSession.builder.profile("producao").create()

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
- Use `serverless_compute_id = auto` no perfil para Serverless sem cluster fixo. Suporte do Databricks Connect para serverless compute está agora Generally Available (GA), a partir da versão 17.3 LTS.
- Requer Python 3.12 — versões anteriores não são suportadas com `>=16.4`.
- Para UDFs: a versão Python local deve coincidir com a do DBR do cluster.
- Ao usar `18.x`, certifique-se de ter `pyarrow>=18.0.0` no ambiente.

---

## Ordem de Precedência de Autenticação

O SDK e a CLI seguem esta ordem (do mais ao menos prioritário):

1. Parâmetros explícitos no código (inline) — **não recomendado em produção**
2. Variáveis de ambiente (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`, `DATABRICKS_CLIENT_ID`, `ARM_*`)
3. `DATABRICKS_CONFIG_PROFILE` (var de ambiente apontando para perfil nomeado)
4. Perfil explícito via `profile=` ou `--profile`
5. Perfil `DEFAULT` em `~/.databrickscfg`
6. Azure Managed Identity / Instance Profile (quando em VM Azure/EC2)

> **Nota CLI:** Para comandos executados dentro de um diretório de bundle, as configurações
> do arquivo de bundle têm precedência sobre variáveis de ambiente e `~/.databrickscfg`.

---

## Diagnóstico de Problemas Comuns

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| `Profile 'X' not found` | Perfil não existe no `~/.databrickscfg` | Rodar `databricks auth login --profile X` |
| `401 Unauthorized` | Token expirado ou inválido | Gerar novo PAT no workspace → User Settings → Developer; ou usar OAuth U2M |
| `Connection refused` | Host incorreto ou firewall | Verificar `DATABRICKS_HOST` (incluir `https://`) |
| Databricks Connect falha silenciosamente | Python != 3.12 ou versão errada do pacote | `python3.12 -m pip install "databricks-connect==X.Y.*"` |
| `ImportError: pyarrow` ao usar DBConnect 18.x | pyarrow desatualizado | `pip install "pyarrow>=18.0.0"` |
| `pyspark.pandas` quebra com pandas 3.x | pandas>=3 não suportado | `pip install "pandas<3"` |
| Scope mismatch silencioso (OAuth) | SDK usava token em cache com escopos errados | SDK agora levanta erro — reautentique com `databricks auth login` |
| MCP switch não persiste | Session-scoped, reseta no restart | Usar `databricks auth login` para persistência |

---

## Checklist de Configuração

- [ ] `~/.databrickscfg` com pelo menos o perfil `DEFAULT`
- [ ] `databricks auth describe --profile <nome>` retorna `username` correto
- [ ] Para Databricks Connect: Python 3.12 instalado, `databricks-connect==X.Y.*` instalado (X.Y = versão DBR alvo)
- [ ] Se DBConnect `>=18.x`: `pyarrow>=18.0.0` no ambiente
- [ ] `pandas<3` no ambiente se usar `pyspark.pandas`
- [ ] Token PAT com data de expiração configurada (evitar tokens sem expiração); preferir OAuth U2M quando possível
- [ ] Secrets sensíveis no Databricks Secrets, não em arquivos de texto

---

## Skills Relacionadas

- **[databricks-python-sdk](../databricks-python-sdk/SKILL.md)** — WorkspaceClient APIs completas
- **[databricks-execution-compute](../databricks-execution-compute/SKILL.md)** — execução de código e compute
- **[databricks-bundles](../databricks-bundles/SKILL.md)** — DABs: targets, variáveis de ambiente, deploy
