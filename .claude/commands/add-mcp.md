---
description: Scaffold de um novo MCP server seguindo os 5 passos do CLAUDE.md na ordem correta, com validação automática de cada passo.
---

# /add-mcp — Scaffold de Novo MCP Server

Você está adicionando um novo MCP server. Há **5 pontos de registro** espalhados pelo
projeto — se qualquer um deles ficar faltando, o MCP carrega mas seus tools não aparecem
para os agentes, e o bug é silencioso. Siga os passos na ordem.

## Argumento

**Nome do MCP em snake_case** (ex: `snowflake`, `dbt_cloud`, `looker`).

Pergunte também (AskUserQuestion em uma única chamada):
- **Stdio ou HTTP?** (stdio é o padrão — 99% dos MCPs)
- **Runtime** (`uvx` para pacotes Python, `npx` para Node)
- **Pacote/comando** (ex: `mcp-server-snowflake` ou `@modelcontextprotocol/server-xyz`)
- **Requer credenciais?** (S/N — MCPs sem credenciais ficam ativos por padrão)
- **Credenciais necessárias** se S (nomes: ex: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`)

## Os 5 Passos (execute em ordem, valide ao fim de cada um)

### Passo 1 — Criar `mcp_servers/<nome>/`

```bash
mkdir mcp_servers/<nome>
```

Crie:
- `mcp_servers/<nome>/__init__.py` (vazio)
- `mcp_servers/<nome>/server_config.py` (a partir de `mcp_servers/_template/server_config.py`)

### Passo 2 — Preencher `server_config.py`

Estrutura obrigatória:

```python
def get_<nome>_mcp_config() -> dict:
    from config.settings import settings  # ← import LOCAL obrigatório (evita ciclo)
    return {
        "<nome>": {
            "type": "stdio",
            "command": "uvx",              # ou "npx"
            "args": ["pacote-mcp"],
            "env": {
                # Se requer credenciais:
                "CRED_VAR": settings.<campo_pydantic>,
            },
        }
    }

MCP_TOOLS = ["mcp__<nome>__tool_a", "mcp__<nome>__tool_b", ...]
MCP_READONLY_TOOLS = [...]  # subconjunto opcional para agentes read-only
```

> **Nota:** a lista `MCP_TOOLS` vale ouro — é a única fonte de verdade dos nomes de tools
> que o `audit_hook.py` usa para classificar operações. Se o MCP não documentar os nomes,
> rode-o uma vez em dev e extraia da primeira tool call.

### Passo 3 — Registrar em `config/mcp_servers.py`

```python
from mcp_servers.<nome>.server_config import get_<nome>_mcp_config, MCP_TOOLS

ALL_MCP_CONFIGS = {
    ...,
    "<nome>": get_<nome>_mcp_config,
}
```

**Se o MCP não requer credenciais**, também adicionar ao `ALWAYS_ACTIVE_MCPS` em
`build_mcp_registry()` — senão ele nunca ativa.

### Passo 4 — Credenciais em `config/settings.py`

Se o usuário disse que requer credenciais:

```python
class Settings(BaseSettings):
    ...
    <nome>_api_key: str = ""
    # (ou os campos específicos passados pelo usuário)
```

E adicionar à função `validate_platform_credentials()` + `startup_diagnostics()` para
que o `/health` informe o status do MCP.

### Passo 5 — Aliases em `agents/loader.py::MCP_TOOL_SETS`

```python
MCP_TOOL_SETS = {
    ...,
    "<nome>_all": MCP_TOOLS,
    "<nome>_readonly": MCP_READONLY_TOOLS,  # só se existir
}
```

### Passo 6 (bônus, sempre necessário) — Testes e docs

- `tests/test_settings.py`: se credential-free, adicionar à constante `CREDENTIAL_FREE_MCPS`.
- `CLAUDE.md`: atualizar 3 seções:
  - Lista "Estrutura de Diretórios" → novo item em `mcp_servers/`
  - Tabela "Tool Aliases Disponíveis" → 1-2 linhas novas
  - "MCPs por Agente" → se algum agente vai usar

## Validação final

Rode em paralelo:

```bash
# 1. Import do config não pode quebrar
python -c "from config.mcp_servers import ALL_MCP_CONFIGS; print('keys:', sorted(ALL_MCP_CONFIGS.keys()))"

# 2. Aliases carregam
python -c "from agents.loader import MCP_TOOL_SETS; print([k for k in MCP_TOOL_SETS if k.startswith('<nome>')])"

# 3. Settings sem erro (se adicionou campos)
python -c "from config.settings import settings; print('ok')"

# 4. Testes verdes
make test
```

## Checklist final

- [ ] `mcp_servers/<nome>/server_config.py` define `get_<nome>_mcp_config()` e `MCP_TOOLS`
- [ ] Registrado em `config/mcp_servers.py::ALL_MCP_CONFIGS`
- [ ] (se credential-free) Em `ALWAYS_ACTIVE_MCPS`
- [ ] (se requer credenciais) Campos em `Settings` + validação + diagnostics
- [ ] Aliases em `MCP_TOOL_SETS` (`<nome>_all`, opcionalmente `<nome>_readonly`)
- [ ] (se credential-free) Em `CREDENTIAL_FREE_MCPS` em `tests/test_settings.py`
- [ ] `CLAUDE.md` atualizado (3 seções)
- [ ] Validações passaram (4 comandos acima)

Se algum passo falhar, **pare e reporte**. MCP mal registrado é bug silencioso —
agentes pensam que têm as tools mas chamadas somem no vazio.
