"""
compression.constants — Limites, tool sets e métricas de custo do compressor.

Fonte de verdade para:
  - Caminho do log (`COMPRESSION_LOG_PATH`)
  - Estimativas de token / preço (`CHARS_PER_TOKEN`, `AVG_INPUT_PRICE_PER_TOKEN`)
  - Classificação de tools por tipo de saída (SQL, List, File, Bash)
  - Limites atuais lidos de `settings` via `_limits()` (permite override em runtime)
  - Aliases `MAX_*` para compatibilidade com testes e imports externos
"""

import os

from config.settings import settings
from utils.tokenizer import CHARS_PER_TOKEN  # noqa: F401 — re-export para metrics.py

# Caminho do log de compressão — `<repo_root>/logs/compression.jsonl`
COMPRESSION_LOG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "compression.jsonl"
)

# Pricing de referência (input tokens, pois é o que o compressor economiza).
# claude-opus-4-6: $15/1M input tokens, claude-sonnet-4-6: $3/1M input tokens.
# Usamos a média ponderada assumindo mix de agentes.
AVG_INPUT_PRICE_PER_TOKEN: float = 9.0 / 1_000_000  # ~$9/1M tokens (média opus+sonnet)


def _limits() -> tuple[int, int, int, int, int]:
    """Retorna limites de compressão lidos de settings (permite override via .env)."""
    return (
        settings.compressor_max_sql_rows,
        settings.compressor_max_list_items,
        settings.compressor_max_file_lines,
        settings.compressor_max_bash_lines,
        settings.compressor_max_output_chars,
    )


# Aliases de módulo para compatibilidade com testes e importações externas.
MAX_SQL_ROWS: int = settings.compressor_max_sql_rows
MAX_LIST_ITEMS: int = settings.compressor_max_list_items
MAX_FILE_LINES: int = settings.compressor_max_file_lines
MAX_BASH_LINES: int = settings.compressor_max_bash_lines
MAX_OUTPUT_CHARS: int = settings.compressor_max_output_chars


# ─── Classificação de tools por tipo de saída ─────────────────────

SQL_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__databricks__execute_sql",
        "mcp__fabric_rti__kusto_query",
        "mcp__fabric_rti__kusto_command",
    }
)

LIST_TOOLS: frozenset[str] = frozenset(
    {
        # Databricks
        "mcp__databricks__list_catalogs",
        "mcp__databricks__list_schemas",
        "mcp__databricks__list_tables",
        "mcp__databricks__list_jobs",
        "mcp__databricks__list_pipelines",
        "mcp__databricks__list_clusters",
        "mcp__databricks__list_job_runs",
        "mcp__databricks__list_workspace",
        "mcp__databricks__list_files",
        "mcp__databricks__list_volume_files",
        "mcp__databricks__get_query_history",
        # Fabric
        "mcp__fabric__list_workspaces",
        "mcp__fabric__list_items",
        "mcp__fabric__list_lakehouses",
        "mcp__fabric__onelake_list_files",
        # Fabric RTI
        "mcp__fabric_rti__kusto_list_databases",
        "mcp__fabric_rti__kusto_list_tables",
        "mcp__fabric_rti__eventstream_list",
        # Fabric Community
        "mcp__fabric_community__list_tables",
        "mcp__fabric_community__list_shortcuts",
        "mcp__fabric_community__list_job_instances",
        "mcp__fabric_community__list_schedules",
    }
)

FILE_TOOLS: frozenset[str] = frozenset({"Read", "Grep", "Glob"})
BASH_TOOLS: frozenset[str] = frozenset({"Bash"})
