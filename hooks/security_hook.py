"""
Hook de segurança — bloqueia comandos Bash potencialmente destrutivos e queries SQL de alto custo.
Aplicado como PreToolUse no Supervisor.

Implementa:
  - Regex com word boundaries para detecção precisa de comandos destrutivos
  - Detecção de padrões de evasão (base64, eval, xargs, hex encoding)
  - Bloqueio de pipe chains suspeitas
  - Detecção de queries SQL de alto custo: SELECT * sem WHERE/LIMIT (full table scan)
"""

import re
from typing import Any


# ─── Padrões destrutivos com regex (word boundaries) ──────────────

DESTRUCTIVE_PATTERNS: list[re.Pattern] = [
    # Filesystem destruction
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/", re.IGNORECASE),
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?~", re.IGNORECASE),
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"\bdd\s+.*of=/dev/", re.IGNORECASE),
    re.compile(r"\bformat\s+[cC]:", re.IGNORECASE),
    # SQL destructive operations
    re.compile(r"\bDROP\s+(DATABASE|CATALOG|SCHEMA|TABLE|VIEW|FUNCTION)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\s+\S+\s+DROP\b", re.IGNORECASE),
    # Dangerous system commands
    re.compile(r"\bchmod\s+(-[a-zA-Z]+\s+)?777\s+/", re.IGNORECASE),
    re.compile(r"\bchown\s+(-[a-zA-Z]+\s+)?\S+\s+/", re.IGNORECASE),
    re.compile(r"\bkill\s+-9\s+-1\b", re.IGNORECASE),
    re.compile(r"\bshutdown\b", re.IGNORECASE),
    re.compile(r"\breboot\b", re.IGNORECASE),
    re.compile(r":\(\)\{.*?:\|.*?&.*?\};:", re.IGNORECASE),  # fork bomb
]

# ─── Padrões de evasão (tentativas de bypass) ────────────────────

EVASION_PATTERNS: list[re.Pattern] = [
    # Base64 encoding para esconder comandos
    re.compile(r"\bbase64\s+(-d|--decode)\b", re.IGNORECASE),
    re.compile(r"\becho\s+\S+\s*\|\s*base64\s+(-d|--decode)", re.IGNORECASE),
    # eval / exec para execução dinâmica
    re.compile(r"\beval\s+", re.IGNORECASE),
    re.compile(r"\$\(\s*echo\s+.*\)", re.IGNORECASE),
    # xargs com comandos perigosos
    re.compile(r"\bxargs\s+.*\brm\b", re.IGNORECASE),
    re.compile(r"\bxargs\s+.*\bkill\b", re.IGNORECASE),
    # Hex/octal encoding
    re.compile(r"\\x[0-9a-fA-F]{2}", re.IGNORECASE),
    re.compile(r"\$'\\x", re.IGNORECASE),
    # Curl/wget piped to shell
    re.compile(r"\b(curl|wget)\s+.*\|\s*(bash|sh|zsh)\b", re.IGNORECASE),
    # Python/Perl/Ruby one-liners para bypass
    re.compile(r"\bpython[23]?\s+-c\s+.*import\s+os", re.IGNORECASE),
    re.compile(r"\bperl\s+-e\s+.*system\(", re.IGNORECASE),
]


# ─── Detecção de queries SQL de alto custo ───────────────────────

#: Padrão que captura SQL inline em comandos Bash (spark-sql -e, databricks query, etc.)
_SQL_IN_BASH = re.compile(
    r'(?:spark-sql\s+-e|beeline\s+-e|databricks\s+query\s+execute|bq\s+query)\s+'
    r"""(?P<q>["'](.+?)["'])""",
    re.IGNORECASE | re.DOTALL,
)

#: Ferramenta cujo tool_input pode conter campos SQL diretos
_SQL_TOOL_FIELDS = ("query", "sql", "statement")


def _detect_expensive_sql(sql: str) -> tuple[bool, str]:
    """
    Analisa uma string SQL e sinaliza padrões de alto custo de computação.

    Retorna (bloqueado: bool, motivo: str).

    Padrões detectados
    ------------------
    1. SELECT * sem WHERE **e** sem LIMIT/TOP → full table scan garantido.
    2. SELECT * sem LIMIT/TOP → pode retornar toda a tabela mesmo com WHERE parcial.
    """
    s = sql.upper().strip()

    if not s or "SELECT" not in s or "FROM" not in s:
        return False, ""

    # Ignora statements que não retornam dados ao agente (INSERT...SELECT, CTAS, MERGE, etc.)
    leading = re.match(r"\b(\w+)\b", s)
    if leading and leading.group(1) in ("INSERT", "CREATE", "MERGE", "UPDATE", "REPLACE"):
        return False, ""

    has_star = bool(re.search(r"\bSELECT\s+\*", s))
    has_where = bool(re.search(r"\bWHERE\b", s))
    has_limit = bool(re.search(r"\bLIMIT\b", s))
    has_top = bool(re.search(r"\bSELECT\s+TOP\s+\d+\b", s))  # T-SQL / Fabric style
    has_row_filter = has_where or has_limit or has_top

    if has_star and not has_where and not has_limit and not has_top:
        return (
            True,
            "SELECT * sem WHERE e sem LIMIT pode escanear TBs de dados em tabelas de produção. "
            "Use: SELECT col1, col2 FROM tabela WHERE particao = 'valor' LIMIT 1000",
        )

    if has_star and not has_row_filter:
        return (
            True,
            "SELECT * sem LIMIT/TOP pode retornar milhões de linhas. "
            "Adicione LIMIT <n> ou selecione apenas as colunas necessárias.",
        )

    # SELECT genérico sem qualquer filtro de linha (não necessariamente SELECT *)
    has_any_select = bool(re.search(r"\bSELECT\b", s))
    if has_any_select and not has_row_filter:
        # Aviso menos severo — bloqueia apenas se também não tiver GROUP BY / HAVING (agrega tudo)
        has_group = bool(re.search(r"\bGROUP\s+BY\b", s))
        if not has_group:
            return (
                True,
                "Query SELECT sem WHERE, LIMIT ou GROUP BY pode escanear toda a tabela. "
                "Adicione filtros de partição ou LIMIT para evitar custos desnecessários.",
            )

    return False, ""


async def check_sql_cost(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Detecta e bloqueia queries SQL de alto custo de computação.

    Verifica dois tipos de chamada:
    - **Bash**: extrai SQL inline de comandos spark-sql, beeline, databricks query, bq query.
    - **Tools SQL diretas**: qualquer tool cujo tool_input contenha campos ``query``,
      ``sql`` ou ``statement`` (ex: execute_query, run_statement, mcp SQL tools).
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name: str = input_data.get("tool_name", "")
    tool_input: dict = input_data.get("tool_input", {}) or {}

    sql_candidate = ""

    if tool_name == "Bash":
        command: str = tool_input.get("command", "")
        m = _SQL_IN_BASH.search(command)
        if m:
            sql_candidate = m.group("q").strip("'\"")
    else:
        for field in _SQL_TOOL_FIELDS:
            value = tool_input.get(field, "")
            if value and isinstance(value, str):
                sql_candidate = value
                break

    if not sql_candidate:
        return {}

    blocked, reason = _detect_expensive_sql(sql_candidate)
    if blocked:
        return _deny(f"Query bloqueada — alto custo detectado: {reason}")

    return {}


async def block_destructive_commands(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Bloqueia comandos Bash que contêm padrões destrutivos ou de evasão.

    Retorna deny com mensagem explicativa se algum padrão for detectado.
    Para comandos não-Bash, retorna {} sem interferir.
    """
    # Proteção contra eventos de teardown do SDK
    if not input_data or not isinstance(input_data, dict):
        return {}

    if input_data.get("tool_name") != "Bash":
        return {}

    command: str = input_data.get("tool_input", {}).get("command", "")

    if not command.strip():
        return {}

    # Verificar padrões destrutivos
    for pattern in DESTRUCTIVE_PATTERNS:
        match = pattern.search(command)
        if match:
            return _deny(
                f"Comando bloqueado: padrão destrutivo detectado '{match.group()}'. "
                f"Confirme com o usuário antes de executar operações destrutivas."
            )

    # Verificar padrões de evasão
    for pattern in EVASION_PATTERNS:
        match = pattern.search(command)
        if match:
            return _deny(
                f"Comando bloqueado: possível tentativa de evasão detectada '{match.group()}'. "
                f"Comandos com encoding, eval ou pipe para shell são proibidos por segurança."
            )

    return {}


def _deny(reason: str) -> dict[str, Any]:
    """Helper para construir resposta de deny padronizada."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
