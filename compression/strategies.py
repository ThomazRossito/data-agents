"""
compression.strategies — Estratégias de compressão por tipo de saída.

Cada função retorna:
  - `str` com o output comprimido (e cabeçalho informativo), ou
  - `None` se o output já está dentro do limite — hook passa inalterado.

Estratégias:
  - `_compress_sql_result`   — resultados de SQL / KQL (JSON ou texto tabular)
  - `_compress_list_result`  — listagens (catálogos, schemas, tabelas, jobs, ...)
  - `_compress_by_lines`     — compressão genérica por linhas (Bash, Read, Grep)
  - `_compress_by_chars`     — fallback de segurança por caracteres
"""

import json

from compression.constants import _limits


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


def _compress_by_chars(output: str, max_chars: int | None = None) -> str | None:
    """
    Fallback de segurança: trunca por caracteres se exceder o limite.

    Aplicado a tools não categorizadas com output muito grande.
    Aceita `max_chars` customizado (ex: para migration-expert com limite maior).
    Retorna None se dentro do limite.
    """
    limit = max_chars if max_chars is not None else _limits()[4]
    if len(output) <= limit:
        return None

    truncated = output[:limit]
    omitted = len(output) - limit
    return (
        truncated + f"\n\n[OUTPUT COMPRIMIDO] ... {omitted} caracteres omitidos "
        f"(total original: {len(output)} chars)."
    )
