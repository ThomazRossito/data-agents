"""Hook de segurança — bloqueia padrões destrutivos antes da execução."""

import re

# Input: bloqueia TUDO — destrutivos + queries não qualificadas
_INPUT_BLOCKED_PATTERNS = [
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA|CATALOG)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+push\s+--force\b",
    r"\.env\b",
    r"\.ssh/",
    r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)",         # DELETE sem WHERE
    r"\bSELECT\s+\*\s+FROM\b(?!.*\b(WHERE|LIMIT)\b)",  # SELECT * sem WHERE/LIMIT
]

# Output: só destrutivos reais — agentes podem gerar docs com SELECT * em exemplos
_OUTPUT_BLOCKED_PATTERNS = [
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA|CATALOG)\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\brm\s+-rf\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+push\s+--force\b",
    r"\.env\b",
    r"\.ssh/",
]

_INPUT_COMPILED = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INPUT_BLOCKED_PATTERNS
]
_OUTPUT_COMPILED = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _OUTPUT_BLOCKED_PATTERNS
]


def check_input(content: str) -> tuple[bool, str]:
    """Política para entradas do usuário — bloqueia destrutivos + queries não qualificadas."""
    for pattern in _INPUT_COMPILED:
        if pattern.search(content):
            return False, f"Padrão bloqueado detectado: `{pattern.pattern}`"
    return True, ""


def check_output(content: str) -> tuple[bool, str]:
    """Política para saídas de agentes — bloqueia só destrutivos reais."""
    for pattern in _OUTPUT_COMPILED:
        if pattern.search(content):
            return False, f"Padrão bloqueado detectado: `{pattern.pattern}`"
    return True, ""


# Alias para compatibilidade — input check
def check(content: str) -> tuple[bool, str]:
    return check_input(content)
