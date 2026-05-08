---
description: Scaffold de um novo MCP server seguindo os 5 passos do CLAUDE.md na ordem correta, com validação automática de cada passo.
---

# /add-mcp — Scaffold de Novo MCP Server

Você está adicionando um novo MCP server. Há **5 pontos de registro obrigatórios**
espalhados pelo projeto — se qualquer um deles ficar faltando, o MCP carrega mas suas
tools não aparecem para os agentes, e o bug é **silencioso**. Siga os passos na ordem.

## Argumento

**Nome do MCP em snake_case** (ex: `snowflake`, `dbt_cloud`, `looker`).

Pergunte também (AskUserQuestion em uma única chamada):
- **Stdio ou HTTP?** (stdio é o padrão — 99% dos MCPs)
- **Runtime** (`uvx` para pacotes Python, `npx` para Node, ou caminho direto para customizados)
- **Pacote/comando** (ex: `mcp-server-snowflake` ou `@modelcontextprotocol/server-xyz`)
- **Requer credenciais?** (S/N — MCPs sem credenciais ficam ativos por padrão via `ALWAYS_ACTIVE_MCPS`)
- **Credenciais necessárias** se S (nomes das env vars: ex: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_PASSWORD`)

## Os 5 Passos (execute em ordem, valide ao fim de cada um)

### Passo 1 — Criar `mcp_servers/<nome>/`

Copie o template como base:
```bash
cp -r mcp_servers/_template mcp_servers/<nome>
```

Resultado esperado:
- `mcp_servers/<nome>/__init__.py` (vazio)
- `mcp_servers/<nome>/server_config.py` (a ser preenchido no Passo 2)

Para MCPs customizados (código próprio), adicionar também `server.py` com a lógica do servidor.

### Passo 2 — Preencher `server_config.py`

Estrutura obrigatória (import de `settings` **sempre local** — evita circular import):

```python
def get_<nome>_mcp_config() -> dict:
    from config.settings import settings  # ← import LOCAL obrigatório
    return {
        "<nome>": {
            "type": "stdio",              # ou "sse" / "http"
            "command": "uvx",             # ou "npx", ou caminho do executável
            "args": ["pacote-mcp"],
            "env": {
                # Se requer credenciais:
                "CRED_VAR": settings.<campo_pydantic>,
            },
            # Para MCPs sem credenciais, env pode ser {} ou omitido
        }
    }

MCP_TOOLS: list[str] = [
    "mcp__<nome>__tool_a",
    "mcp__<nome>__tool_b",
    # ...
]

MCP_READONLY_TOOLS: list[str] = [
    # Subconjunto opcional: somente tools de leitura (list_, get_, describe_, etc.)
    # Usado pelos agentes que recebem alias "<nome>_readonly"
]
```

> **Nota:** a lista `MCP_TOOLS` é a fonte de verdade dos nomes de tools que o
> `audit_hook.py` usa para classificar operações. Se o MCP não documentar os nomes,
> rode-o uma vez em dev e extraia da primeira tool call.

### Passo 3 — Registrar em `config/mcp_servers.py`

```python
from mcp_servers.<nome>.server_config import get_<nome>_mcp_config, MCP_TOOLS  # noqa: E402

ALL_MCP_CONFIGS: dict = {
    ...,
    "<nome>": get_<nome>_mcp_config,
}
```

**Se o MCP não requer credenciais** (auth via Azure CLI, sem env vars, etc.):
```python
ALWAYS_ACTIVE_MCPS: list[str] = ["context7", "memory_mcp", "fabric_ontology", "<nome>"]
```

Se requer credenciais, não adicionar ao `ALWAYS_ACTIVE_MCPS` — ele só ativa quando as
credenciais estiverem presentes no `.env`.

### Passo 4 — Credenciais em `config/settings.py` (apenas se requer credenciais)

Adicionar campos na classe `Settings`:
```python
# --- <Nome> MCP ---
# Como obter: <URL ou instruções>
<nome>_api_key: str = ""
# (ou os campos específicos necessários)
```

Adicionar à função `validate_platform_credentials()`:
```python
if self.<nome>_api_key:
    configured.append("<nome>")
else:
    missing.append("<nome>_api_key")
```

Adicionar ao `startup_diagnostics()` para aparecer no `/health`.

Se **não requer credenciais**, pular este passo — mas adicionar ao `.env.example`
com comentário explicando o método de autenticação.

### Passo 5 — Aliases em `agents/loader.py` → `MCP_TOOL_SETS`

```python
from mcp_servers.<nome>.server_config import (   # noqa: E402
    MCP_TOOLS as <NOME>_MCP_TOOLS,
    MCP_READONLY_TOOLS as <NOME>_MCP_READONLY_TOOLS,
)

MCP_TOOL_SETS: dict[str, list[str]] = {
    ...,
    "<nome>_all": <NOME>_MCP_TOOLS,
    "<nome>_readonly": <NOME>_MCP_READONLY_TOOLS,  # omitir se MCP_READONLY_TOOLS estiver vazio
}
```

## Passo 6 — Testes e documentação (obrigatório)

### Testes
- `tests/test_settings.py`: se credential-free, adicionar à constante `CREDENTIAL_FREE_MCPS`:
  ```python
  CREDENTIAL_FREE_MCPS = {..., "<nome>"}
  ```
- Criar `tests/test_<nome>_server.py` seguindo o padrão de `tests/test_fabric_ontology_server.py`:
  - `get_<nome>_mcp_config()` retorna estrutura válida
  - `MCP_TOOLS` não está vazio
  - `MCP_READONLY_TOOLS` é subconjunto de `MCP_TOOLS` (se definido)
  - Aliases em `MCP_TOOL_SETS` existem
  - (Se credential-free) presente em `ALWAYS_ACTIVE_MCPS`

### Documentação (`CLAUDE.md`)
Atualizar 3 seções:
1. **Estrutura de Diretórios** → novo item em `mcp_servers/`
2. **Tool Aliases Disponíveis** → linhas `<nome>_all` e `<nome>_readonly`
3. **MCPs por Agente** → coluna do agente que vai usar

## Validação final

Rode em paralelo:

```bash
# 1. Import sem erro
python -c "from config.mcp_servers import ALL_MCP_CONFIGS; print('keys:', sorted(ALL_MCP_CONFIGS.keys()))"

# 2. Aliases carregam
python -c "from agents.loader import MCP_TOOL_SETS; print([k for k in MCP_TOOL_SETS if k.startswith('<nome>')])"

# 3. Settings ok
python -c "from config.settings import settings; print('ok')"

# 4. Testes verdes
make test
```

## Checklist final

- [ ] `mcp_servers/<nome>/server_config.py` define `get_<nome>_mcp_config()`, `MCP_TOOLS` e (opcionalmente) `MCP_READONLY_TOOLS`
- [ ] Registrado em `config/mcp_servers.py::ALL_MCP_CONFIGS`
- [ ] (se credential-free) Adicionado em `ALWAYS_ACTIVE_MCPS`
- [ ] (se requer credenciais) Campos em `Settings` + `validate_platform_credentials()` + `startup_diagnostics()`
- [ ] `.env.example` atualizado com as variáveis ou comentário de autenticação
- [ ] Aliases em `MCP_TOOL_SETS` (`<nome>_all`, e `<nome>_readonly` se definido)
- [ ] (se credential-free) Adicionado em `CREDENTIAL_FREE_MCPS` em `tests/test_settings.py`
- [ ] `tests/test_<nome>_server.py` criado
- [ ] `CLAUDE.md` atualizado (3 seções)
- [ ] 4 validações acima passaram

Se algum passo falhar, **pare e reporte**. MCP mal registrado é bug silencioso —
agentes pensam que têm as tools mas as chamadas somem no vazio.
