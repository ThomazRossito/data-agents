"""
compression.hook — PostToolUse do compressor de output.

Intercepta `tool_response` (ou equivalente) no PostToolUse, aplica a estratégia
adequada ao tipo de tool e retorna `hookSpecificOutput` substituindo o output
original. Fail-safe: qualquer exceção interna resulta em pass-through ({}).

Protocolo de hooks Claude Code CLI:
  - Retorna `{}` para pass-through (output original é enviado ao modelo)
  - Retorna `{"hookSpecificOutput": {"hookEventName": "PostToolUse",
    "toolResponse": <compressed>}}` para substituir o output.
"""

import logging
from typing import Any

from compression.constants import (
    BASH_TOOLS,
    FILE_TOOLS,
    LIST_TOOLS,
    MIGRATION_SOURCE_TOOL_PREFIX,
    SQL_TOOLS,
    _limits,
    _migration_limits,
)
from compression.metrics import _log_compression_metrics
from compression.strategies import (
    _compress_by_chars,
    _compress_by_lines,
    _compress_list_result,
    _compress_sql_result,
)

logger = logging.getLogger("data_agents.output_compressor")


def _extract_output(input_data: dict[str, Any]) -> str | None:
    """
    Extrai o output da tool do dict de input_data do hook PostToolUse.

    Tenta as chaves possíveis em ordem de prioridade, pois podem variar
    conforme a versão do Claude Agent SDK e do Claude Code CLI.
    """
    for key in ("tool_response", "tool_output", "output"):
        value = input_data.get(key)
        if value is not None:
            return str(value)
    return None


def _build_response(compressed: str) -> dict[str, Any]:
    """
    Constrói o dict de resposta do hook para substituir o output original da tool.

    Segue o protocolo de hooks do Claude Code CLI:
    hookSpecificOutput.toolResponse substitui o conteúdo de tool_response
    antes de ser enviado ao modelo.
    """
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "toolResponse": compressed,
        }
    }


async def compress_tool_output(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Intercepta o output de ferramentas e comprime conforme o tipo de tool.

    Aplicado como PostToolUse no Supervisor. Reduz o volume de tokens consumidos
    pelas respostas das ferramentas antes de enviá-las ao modelo, seguindo a
    filosofia do RTK (Rust Token Killer): menos tokens = menor custo + menor latência.

    Retorna {} (sem modificação) se:
      - input_data é inválido ou None
      - output não excede os limites configurados para o tipo de tool
      - ocorre qualquer exceção interna (fail-safe garantido)

    Retorna hookSpecificOutput com toolResponse comprimido se:
      - output excede os limites configurados para o tipo de tool

    Args:
        input_data: Dict com tool_name, tool_input e tool_response (output da tool).
        tool_use_id: ID único da chamada de tool (usado para correlação de logs).
        context: Contexto do SDK (não utilizado diretamente).

    Returns:
        {} para pass-through ou dict com hookSpecificOutput para substituir o output.
    """
    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name: str = input_data.get("tool_name", "")
    if not tool_name:
        return {}

    output = _extract_output(input_data)
    if not output or not output.strip():
        return {}

    compressed: str | None = None

    try:
        # Tools do migration-expert: limites maiores — DDLs e schemas são legitimamente grandes.
        if tool_name.startswith(MIGRATION_SOURCE_TOOL_PREFIX):
            migration_file_lines, migration_max_chars = _migration_limits()
            compressed = _compress_by_lines(output, migration_file_lines, "migration_source")
            if compressed is None:
                compressed = _compress_by_chars(output, migration_max_chars)

        elif tool_name in SQL_TOOLS:
            compressed = _compress_sql_result(output, tool_name)

        elif tool_name in LIST_TOOLS:
            compressed = _compress_list_result(output, tool_name)

        elif tool_name in FILE_TOOLS:
            compressed = _compress_by_lines(output, _limits()[2], "Read/Grep")

        elif tool_name in BASH_TOOLS:
            compressed = _compress_by_lines(output, _limits()[3], "Bash")

        # Fallback de segurança para qualquer tool não categorizada
        if compressed is None:
            compressed = _compress_by_chars(output)

        if compressed is not None:
            original_chars = len(output)
            compressed_chars = len(compressed)
            reduction_pct = (
                round((1 - compressed_chars / original_chars) * 100, 1)
                if original_chars > 0
                else 0.0
            )
            logger.info(
                "[OUTPUT COMPRIMIDO] tool=%s | original=%d chars → comprimido=%d chars | "
                "redução=%.1f%% | tool_use_id=%s",
                tool_name,
                original_chars,
                compressed_chars,
                reduction_pct,
                tool_use_id,
            )
            _log_compression_metrics(tool_name, original_chars, compressed_chars, tool_use_id)
            return _build_response(compressed)

    except Exception as e:
        # O hook nunca deve bloquear a execução — em caso de exceção, passa o output original.
        logger.warning(
            "Falha na compressão de output para '%s' (tool_use_id=%s): %s",
            tool_name,
            tool_use_id,
            e,
        )

    return {}
