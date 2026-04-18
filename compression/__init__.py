"""
compression — Pacote de compressão de output de ferramentas.

Módulos:
  - `compression.constants`   — limites, tool sets, pricing e `_limits()`
  - `compression.strategies`  — estratégias de compressão por tipo de saída
  - `compression.metrics`     — persistência de métricas em `logs/compression.jsonl`
  - `compression.hook`        — PostToolUse principal (`compress_tool_output`)

Re-exports convenientes para importações externas:
  - `compress_tool_output`           — hook principal (registrado no Supervisor)
  - `COMPRESSION_LOG_PATH`           — caminho do JSONL de métricas
  - `MAX_SQL_ROWS`, `MAX_LIST_ITEMS`,
    `MAX_FILE_LINES`, `MAX_BASH_LINES`,
    `MAX_OUTPUT_CHARS`               — aliases usados em testes
"""

from compression.constants import (  # noqa: F401
    AVG_INPUT_PRICE_PER_TOKEN,
    BASH_TOOLS,
    CHARS_PER_TOKEN,
    COMPRESSION_LOG_PATH,
    FILE_TOOLS,
    LIST_TOOLS,
    MAX_BASH_LINES,
    MAX_FILE_LINES,
    MAX_LIST_ITEMS,
    MAX_OUTPUT_CHARS,
    MAX_SQL_ROWS,
    SQL_TOOLS,
    _limits,
)
from compression.hook import (  # noqa: F401
    _build_response,
    _extract_output,
    compress_tool_output,
)
from compression.metrics import _log_compression_metrics  # noqa: F401
from compression.strategies import (  # noqa: F401
    _compress_by_chars,
    _compress_by_lines,
    _compress_list_result,
    _compress_sql_result,
)

__all__ = [
    "AVG_INPUT_PRICE_PER_TOKEN",
    "BASH_TOOLS",
    "CHARS_PER_TOKEN",
    "COMPRESSION_LOG_PATH",
    "FILE_TOOLS",
    "LIST_TOOLS",
    "MAX_BASH_LINES",
    "MAX_FILE_LINES",
    "MAX_LIST_ITEMS",
    "MAX_OUTPUT_CHARS",
    "MAX_SQL_ROWS",
    "SQL_TOOLS",
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
