"""
Hook de segurança — bloqueia comandos Bash potencialmente destrutivos.
Aplicado como PreToolUse no Supervisor.

Implementa:
  - Regex com word boundaries para detecção precisa de comandos destrutivos
  - Detecção de padrões de evasão (base64, eval, xargs, hex encoding)
  - Bloqueio de pipe chains suspeitas
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
    re.compile(r":(){ :\|:& };:", re.IGNORECASE),  # fork bomb
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
