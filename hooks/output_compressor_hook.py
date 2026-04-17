"""
Hook de compressão de output — reduz o volume de tokens consumidos pelas respostas
das ferramentas antes de enviá-las ao modelo.

Inspirado no RTK (Rust Token Killer): filtra e comprime a saída de tools
de forma transparente, sem alterar o comportamento funcional do sistema.
Aplicado como PostToolUse no Supervisor (propaga aos sub-agents via SDK).

Princípio: menos tokens para processar = menor custo + menor latência.

Estratégias por categoria de tool:
  - SQL / KQL results    → trunca para MAX_SQL_ROWS linhas + cabeçalho informativo
  - List operations      → limita a MAX_LIST_ITEMS itens + contagem total
  - File reads (Read)    → trunca para MAX_FILE_LINES linhas
  - Bash output          → trunca para MAX_BASH_LINES linhas
  - Fallback geral       → trunca se > MAX_OUTPUT_CHARS caracteres

O hook nunca bloqueia a execução: em caso de exceção, retorna {} e
passa o output original intacto ao modelo (fail-safe).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from config.settings import settings

logger = logging.getLogger("data_agents.output_compressor")

COMPRESSION_LOG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "compression.jsonl"
)

# Estimativa de conversão chars → tokens (Claude tokenizer ≈ 4 chars/token)
CHARS_PER_TOKEN: float = 4.0

# Pricing de referência (input tokens, pois é o que o compressor economiza)
# claude-opus-4-6: $15/1M input tokens, claude-sonnet-4-6: $3/1M input tokens
# Usamos a média ponderada assumindo mix de agentes
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


# Aliases de módulo para compatibilidade com testes e importações externas
MAX_SQL_ROWS: int = settings.compressor_max_sql_rows
MAX_LIST_ITEMS: int = settings.compressor_max_list_items
MAX_FILE_LINES: int = settings.compressor_max_file_lines
MAX_BASH_LINES: int = settings.compressor_max_bash_lines
MAX_OUTPUT_CHARS: int = settings.compressor_max_output_chars


# ─── Classificação de tools por tipo de saída ─────────────────────

_SQL_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__databricks__execute_sql",
        "mcp__fabric_rti__kusto_query",
        "mcp__fabric_rti__kusto_command",
    }
)

_LIST_TOOLS: frozenset[str] = frozenset(
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

_FILE_TOOLS: frozenset[str] = frozenset({"Read", "Grep", "Glob"})
_BASH_TOOLS: frozenset[str] = frozenset({"Bash"})


# ─── Funções auxiliares de extração e resposta ────────────────────


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


# ─── Estratégias de compressão por tipo ──────────────────────────


def _compress_sql_result(output: str, tool_name: str) -> str | None:
    """
    Comprime resultado de queries SQL (Spark SQL, T-SQL) ou KQL.

    Estratégia:
      1. Tenta interpretar como JSON (lista de rows ou dict com rows).
      2. Fallback: trunca texto tabular/markdown por número de linhas.

    Retorna None se o output já está dentro do limite (sem modificação).
    """
    # ── Caminho JSON ──────────────────────────────────────────────
    try:
        data = json.loads(output)

        # Formato: lista direta de rows → [{"col": "val"}, ...]
        max_sql = _limits()[0]

        if isinstance(data, list):
            total = len(data)
            if total <= max_sql:
                return None

            header = (
                f"[OUTPUT COMPRIMIDO] {total} linhas retornadas — "
                f"exibindo as primeiras {max_sql}. "
                f"Refine com WHERE + LIMIT para resultados completos.\n\n"
            )
            return header + json.dumps(data[:max_sql], ensure_ascii=False, indent=2)

        # Formato: dict com lista interna → {"rows": [...], "schema": {...}}
        if isinstance(data, dict):
            rows: list | None = None
            rows_key: str = ""
            for k, v in data.items():
                if isinstance(v, list):
                    rows = v
                    rows_key = k
                    break

            if rows is not None:
                total = len(rows)
                if total <= max_sql:
                    return None

                data_copy = dict(data)
                data_copy[rows_key] = rows[:max_sql]
                header = (
                    f"[OUTPUT COMPRIMIDO] {total} linhas retornadas — "
                    f"exibindo as primeiras {max_sql}. "
                    f"Refine com WHERE + LIMIT para resultados completos.\n\n"
                )
                return header + json.dumps(data_copy, ensure_ascii=False, indent=2)

    except (json.JSONDecodeError, ValueError):
        pass

    # ── Fallback: trunca por linhas de texto (markdown table, CSV, etc.) ──
    max_sql = _limits()[0]
    lines = output.splitlines()
    if len(lines) <= max_sql:
        return None

    truncated = lines[:max_sql]
    omitted = len(lines) - max_sql
    truncated.append(
        f"[OUTPUT COMPRIMIDO — {omitted} linhas omitidas] "
        f"Refine a query com WHERE/LIMIT para ver todos os dados."
    )
    return "\n".join(truncated)


def _compress_list_result(output: str, tool_name: str) -> str | None:
    """
    Comprime resultado de operações de listagem (tabelas, schemas, jobs, etc.).

    Estratégia:
      1. Tenta interpretar como JSON (lista ou dict com lista interna).
      2. Fallback: trunca texto linha a linha.

    Retorna None se o output já está dentro do limite (sem modificação).
    """
    tool_label = tool_name.replace("mcp__", "").replace("__", " → ").replace("_", " ").title()

    # ── Caminho JSON ──────────────────────────────────────────────
    try:
        data = json.loads(output)
        items: list | None = None
        items_key: str = ""

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    items = v
                    items_key = k
                    break

        max_list = _limits()[1]

        if items is not None:
            total = len(items)
            if total <= max_list:
                return None

            header = (
                f"[OUTPUT COMPRIMIDO — {tool_label}] "
                f"Total: {total} itens. Exibindo os primeiros {max_list}.\n\n"
            )

            if isinstance(data, list):
                return header + json.dumps(items[:max_list], ensure_ascii=False, indent=2)

            # Reconstrói dict com lista truncada
            data_copy = dict(data)
            data_copy[items_key] = items[:max_list]
            return header + json.dumps(data_copy, ensure_ascii=False, indent=2)

    except (json.JSONDecodeError, ValueError):
        pass

    # ── Fallback: trunca por linhas ───────────────────────────────
    max_list = _limits()[1]
    lines = output.splitlines()
    if len(lines) <= max_list:
        return None

    truncated = lines[:max_list]
    omitted = len(lines) - max_list
    truncated.append(f"[OUTPUT COMPRIMIDO — {tool_label}] ... {omitted} itens omitidos.")
    return "\n".join(truncated)


def _compress_by_lines(output: str, max_lines: int, label: str) -> str | None:
    """
    Compressão genérica por número de linhas — usada para Bash e Read.

    Retorna None se o output já está dentro do limite (sem modificação).
    """
    lines = output.splitlines()
    if len(lines) <= max_lines:
        return None

    truncated = lines[:max_lines]
    omitted = len(lines) - max_lines
    truncated.append(f"[OUTPUT COMPRIMIDO — {label}] ... {omitted} linhas omitidas.")
    return "\n".join(truncated)


def _compress_by_chars(output: str) -> str | None:
    """
    Fallback de segurança: trunca por caracteres se exceder MAX_OUTPUT_CHARS.

    Aplicado a tools não categorizadas com output muito grande.
    Retorna None se dentro do limite.
    """
    max_chars = _limits()[4]
    if len(output) <= max_chars:
        return None

    truncated = output[:max_chars]
    omitted = len(output) - max_chars
    return (
        truncated + f"\n\n[OUTPUT COMPRIMIDO] ... {omitted} caracteres omitidos "
        f"(total original: {len(output)} chars)."
    )


def _log_compression_metrics(
    tool_name: str,
    original_chars: int,
    compressed_chars: int,
    tool_use_id: str | None,
) -> None:
    """Persiste métricas de compressão em logs/compression.jsonl."""
    try:
        saved_chars = original_chars - compressed_chars
        reduction_pct = (
            round((1 - compressed_chars / original_chars) * 100, 1) if original_chars > 0 else 0.0
        )
        saved_tokens_est = round(saved_chars / CHARS_PER_TOKEN)
        saved_cost_est = round(saved_tokens_est * AVG_INPUT_PRICE_PER_TOKEN, 6)

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "original_chars": original_chars,
            "compressed_chars": compressed_chars,
            "saved_chars": saved_chars,
            "reduction_pct": reduction_pct,
            "saved_tokens_est": saved_tokens_est,
            "saved_cost_est_usd": saved_cost_est,
            "tool_use_id": tool_use_id or "",
        }

        os.makedirs(os.path.dirname(COMPRESSION_LOG_PATH), exist_ok=True)
        with open(COMPRESSION_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Nunca bloqueia a execução


# ─── Hook principal ───────────────────────────────────────────────


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
        if tool_name in _SQL_TOOLS:
            compressed = _compress_sql_result(output, tool_name)

        elif tool_name in _LIST_TOOLS:
            compressed = _compress_list_result(output, tool_name)

        elif tool_name in _FILE_TOOLS:
            compressed = _compress_by_lines(output, _limits()[2], "Read/Grep")

        elif tool_name in _BASH_TOOLS:
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
