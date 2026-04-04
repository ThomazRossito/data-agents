"""
Hook de segurança — bloqueia comandos Bash potencialmente destrutivos.
Aplicado como PreToolUse no Supervisor.
"""

from typing import Any


# Padrões de comandos que nunca devem ser executados automaticamente
BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "DROP DATABASE",
    "DROP CATALOG",
    "DROP SCHEMA",
    "DROP TABLE",
    "TRUNCATE TABLE",
    "DELETE FROM",
    "FORMAT C:",
    "> /dev/sda",
]


async def block_destructive_commands(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Bloqueia comandos Bash que contêm padrões destrutivos conhecidos.
    Retorna deny com mensagem explicativa se algum padrão for detectado.
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command: str = input_data.get("tool_input", {}).get("command", "")

    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in command.lower():
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Comando bloqueado por política de segurança: "
                        f"contém padrão proibido '{pattern}'. "
                        f"Confirme com o usuário antes de executar operações destrutivas."
                    ),
                }
            }

    return {}
