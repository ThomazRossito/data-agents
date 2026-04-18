"""
Shim de compatibilidade — a implementação foi movida para `compression/`.

Mantido apenas para preservar imports existentes:
  - `from hooks.output_compressor_hook import compress_tool_output`
  - `from hooks.output_compressor_hook import MAX_SQL_ROWS, MAX_LIST_ITEMS, ...`
  - `from hooks.output_compressor_hook import _compress_sql_result, ...`

Novos módulos:
  - `compression.constants`   — limites, tool sets, pricing, `_limits()`
  - `compression.strategies`  — estratégias de compressão por tipo
  - `compression.metrics`     — logging JSONL de métricas
  - `compression.hook`        — PostToolUse principal
"""

from compression import (  # noqa: F401 — re-exports
    AVG_INPUT_PRICE_PER_TOKEN,
    CHARS_PER_TOKEN,
    COMPRESSION_LOG_PATH,
    MAX_BASH_LINES,
    MAX_FILE_LINES,
    MAX_LIST_ITEMS,
    MAX_OUTPUT_CHARS,
    MAX_SQL_ROWS,
    _build_response,
    _compress_by_chars,
    _compress_by_lines,
    _compress_list_result,
    _compress_sql_result,
    _extract_output,
    _limits,
    _log_compression_metrics,
    compress_tool_output,
)

__all__ = [
    "AVG_INPUT_PRICE_PER_TOKEN",
    "CHARS_PER_TOKEN",
    "COMPRESSION_LOG_PATH",
    "MAX_BASH_LINES",
    "MAX_FILE_LINES",
    "MAX_LIST_ITEMS",
    "MAX_OUTPUT_CHARS",
    "MAX_SQL_ROWS",
    "_build_response",
    "_compress_by_chars",
    "_compress_by_lines",
    "_compress_list_result",
    "_compress_sql_result",
    "_extract_output",
    "_limits",
    "_log_compression_metrics",
    "compress_tool_output",
]
