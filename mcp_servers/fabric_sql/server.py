"""
Fabric SQL Analytics Endpoint — MCP Server Customizado.

Resolve o problema da REST API do Fabric que só enxerga o schema `dbo`.
Conecta diretamente ao SQL Analytics Endpoint via TDS (porta 1433)
usando pyodbc + Azure AD Service Principal Token.

MULTI-LAKEHOUSE: Suporta múltiplos lakehouses via FABRIC_SQL_LAKEHOUSES (JSON registry).
O agente passa o parâmetro `lakehouse` opcionalmente em qualquer tool.

Configuração no .env:

  # Registry de todos os lakehouses disponíveis (JSON)
  # Chave = nome do lakehouse | Valor = SQL endpoint do workspace
  FABRIC_SQL_LAKEHOUSES={
    "TARN_LH_DEV":  "tarn-dev.datawarehouse.fabric.microsoft.com",
    "TARN_LH_PROD": "tarn-prod.datawarehouse.fabric.microsoft.com",
    "ANALYTICS_LH": "analytics-ws.datawarehouse.fabric.microsoft.com"
  }

  # Lakehouse padrão (usado quando o agente não especifica qual)
  FABRIC_SQL_DEFAULT_LAKEHOUSE=TARN_LH_DEV

  # Credenciais Azure (compartilhadas entre todos os lakehouses)
  AZURE_TENANT_ID=...
  AZURE_CLIENT_ID=...
  AZURE_CLIENT_SECRET=...

Como encontrar o SQL Endpoint:
  Portal Fabric → Lakehouse → SQL Analytics Endpoint → campo "Server"
  Formato: <workspace-name>.datawarehouse.fabric.microsoft.com

Pré-requisitos:
  macOS:  brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
          HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
  Linux:  https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
  Python: pip install pyodbc  (incluído no pyproject.toml)
"""

from __future__ import annotations

import json
import logging
import os
import struct
import traceback
from typing import Any

logger = logging.getLogger("fabric_sql_mcp")

try:
    import pyodbc

    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

try:
    from azure.identity import ClientSecretCredential

    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False

from mcp.server.fastmcp import FastMCP  # noqa: E402

# ─── Constantes ──────────────────────────────────────────────────────────────

SQL_COPT_SS_ACCESS_TOKEN = 1256
ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
_BLOCKED_SQL_PREFIXES = frozenset(
    ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "EXEC", "EXECUTE"]
)

# ─── FastMCP Server ───────────────────────────────────────────────────────────

mcp = FastMCP("fabric-sql")


# ─── Registry de Lakehouses ──────────────────────────────────────────────────


def _get_registry() -> dict[str, str]:
    """
    Carrega o registry de lakehouses do FABRIC_SQL_LAKEHOUSES (JSON).
    Formato: {"NOME_LH": "workspace.datawarehouse.fabric.microsoft.com", ...}
    """
    raw = os.environ.get("FABRIC_SQL_LAKEHOUSES", "").strip()
    if not raw:
        return {}
    try:
        registry = json.loads(raw)
        if not isinstance(registry, dict):
            raise ValueError("FABRIC_SQL_LAKEHOUSES deve ser um objeto JSON.")
        return registry
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear FABRIC_SQL_LAKEHOUSES: {e}")
        return {}


def _resolve_connection_params(lakehouse: str | None) -> tuple[str, str]:
    """
    Resolve (endpoint, database) para um lakehouse.

    Prioridade:
      1. lakehouse especificado → busca no registry (FABRIC_SQL_LAKEHOUSES)
      2. lakehouse especificado mas não no registry → erro com sugestão
      3. lakehouse=None → usa o default (FABRIC_SQL_DEFAULT_LAKEHOUSE no registry)

    Returns:
        (sql_endpoint, database_name)

    Raises:
        RuntimeError com mensagem clara se o lakehouse não for encontrado.
    """
    registry = _get_registry()

    if lakehouse:
        # Busca explícita no registry
        endpoint = registry.get(lakehouse)
        if not endpoint:
            available = list(registry.keys()) or ["(registry vazio)"]
            raise RuntimeError(
                f"Lakehouse '{lakehouse}' não encontrado no registry.\n"
                f"Lakehouses disponíveis: {available}\n\n"
                f"Para adicionar, edite o .env:\n"
                f'  FABRIC_SQL_LAKEHOUSES={{"...", "{lakehouse}": "seu-workspace.datawarehouse.fabric.microsoft.com"}}'
            )
        return endpoint, lakehouse

    # Sem lakehouse explícito → usa o default
    default_name = os.environ.get("FABRIC_SQL_DEFAULT_LAKEHOUSE", "").strip()

    if default_name and registry:
        endpoint = registry.get(default_name)
        if endpoint:
            return endpoint, default_name
        # Default configurado mas não no registry
        raise RuntimeError(
            f"FABRIC_SQL_DEFAULT_LAKEHOUSE='{default_name}' não encontrado no registry.\n"
            f"Lakehouses no registry: {list(registry.keys())}"
        )

    # Fallback: variáveis legadas (backward compat)
    endpoint_legacy = os.environ.get("FABRIC_SQL_ENDPOINT", "").strip()
    database_legacy = os.environ.get("FABRIC_LAKEHOUSE_NAME", "").strip()
    if endpoint_legacy and database_legacy:
        return endpoint_legacy, database_legacy

    # Nada configurado
    available_lakehouses = list(registry.keys()) if registry else []
    raise RuntimeError(
        "Nenhum lakehouse configurado.\n\n"
        "Opção 1 — Registry (recomendado para múltiplos lakehouses):\n"
        "  No .env, adicione:\n"
        '  FABRIC_SQL_LAKEHOUSES={"MEU_LH": "workspace.datawarehouse.fabric.microsoft.com"}\n'
        "  FABRIC_SQL_DEFAULT_LAKEHOUSE=MEU_LH\n\n"
        "Opção 2 — Variáveis simples (para um único lakehouse):\n"
        "  FABRIC_SQL_ENDPOINT=workspace.datawarehouse.fabric.microsoft.com\n"
        "  FABRIC_LAKEHOUSE_NAME=MEU_LH\n\n"
        "Como encontrar o SQL Endpoint:\n"
        "  Portal Fabric → Lakehouse → SQL Analytics Endpoint → campo 'Server'"
        + (
            f"\n\nLakehouses no registry atual: {available_lakehouses}"
            if available_lakehouses
            else ""
        )
    )


# ─── Helpers de conexão ───────────────────────────────────────────────────────


def _validate_dependencies() -> str | None:
    if not AZURE_IDENTITY_AVAILABLE:
        return "azure-identity não instalado. Execute: pip install azure-identity"
    if not PYODBC_AVAILABLE:
        return (
            "pyodbc não instalado. Execute: pip install pyodbc\n"
            "E instale o ODBC Driver 18:\n"
            "  macOS: brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release\n"
            "         HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18"
        )
    drivers = pyodbc.drivers()
    if ODBC_DRIVER not in drivers:
        return (
            f"ODBC Driver '{ODBC_DRIVER}' não encontrado.\n"
            f"Drivers instalados: {drivers}\n"
            "Instale com: HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18"
        )
    return None


def _get_access_token() -> bytes:
    """Bearer Token AAD para o SQL Analytics Endpoint (scope database.windows.net)."""
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    return struct.pack("<I", len(token_bytes)) + token_bytes


def _get_connection(lakehouse: str | None = None):
    """
    Abre conexão com o SQL Analytics Endpoint do lakehouse especificado.
    Se lakehouse=None, usa o default configurado no .env.
    """
    dep_error = _validate_dependencies()
    if dep_error:
        raise RuntimeError(dep_error)

    endpoint, database = _resolve_connection_params(lakehouse)

    conn_str = (
        f"Driver={{{ODBC_DRIVER}}};"
        f"Server={endpoint},1433;"
        f"Database={database};"
        "Encrypt=Yes;"
        "TrustServerCertificate=No;"
        "Connection Timeout=30;"
    )
    token_struct = _get_access_token()
    conn = pyodbc.connect(conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})
    conn.timeout = 60
    return conn


def _serialize_row(row: Any) -> list:
    result = []
    for val in row:
        if val is None:
            result.append(None)
        elif hasattr(val, "isoformat"):
            result.append(val.isoformat())
        elif isinstance(val, (bytes, bytearray)):
            result.append(val.hex())
        elif isinstance(val, float) and val != val:  # NaN
            result.append(None)
        else:
            result.append(val)
    return result


def _error_response(e: Exception) -> str:
    return json.dumps(
        {"error": str(e), "type": type(e).__name__, "traceback": traceback.format_exc()},
        ensure_ascii=False,
    )


# ─── MCP Tools ───────────────────────────────────────────────────────────────


@mcp.tool()
def fabric_sql_list_lakehouses() -> str:
    """
    Lista todos os lakehouses disponíveis no registry (FABRIC_SQL_LAKEHOUSES).
    Use este tool para saber quais lakehouses podem ser usados no parâmetro 'lakehouse'.

    Returns:
        JSON com lista de lakehouses configurados e o default atual.
        Exemplo: {"lakehouses": ["TARN_LH_DEV", "TARN_LH_PROD"], "default": "TARN_LH_DEV"}
    """
    registry = _get_registry()
    default = os.environ.get("FABRIC_SQL_DEFAULT_LAKEHOUSE", "")

    # Backward compat: se tiver variáveis legadas mas sem registry
    legacy_name = os.environ.get("FABRIC_LAKEHOUSE_NAME", "")
    legacy_endpoint = os.environ.get("FABRIC_SQL_ENDPOINT", "")
    if not registry and legacy_name and legacy_endpoint:
        return json.dumps(
            {
                "lakehouses": [legacy_name],
                "default": legacy_name,
                "mode": "legacy (FABRIC_LAKEHOUSE_NAME + FABRIC_SQL_ENDPOINT)",
                "hint": "Para múltiplos lakehouses, use FABRIC_SQL_LAKEHOUSES no .env",
            },
            ensure_ascii=False,
            indent=2,
        )

    return json.dumps(
        {
            "lakehouses": list(registry.keys()),
            "endpoints": registry,
            "default": default or (list(registry.keys())[0] if registry else None),
            "count": len(registry),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def fabric_sql_diagnostics(lakehouse: str | None = None) -> str:
    """
    Diagnóstico completo da conexão ao Fabric SQL Analytics Endpoint.
    Execute este tool quando houver erros de conexão.

    Args:
        lakehouse: Nome do lakehouse a diagnosticar. Se None, usa o default.
                   Use fabric_sql_list_lakehouses() para ver os disponíveis.
    """
    report: dict[str, Any] = {"status": "ok", "checks": [], "lakehouse_requested": lakehouse}

    def check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"check": name, "status": "✅" if ok else "❌", "detail": detail})
        if not ok:
            report["status"] = "error"

    check(
        "azure-identity",
        AZURE_IDENTITY_AVAILABLE,
        "Disponível" if AZURE_IDENTITY_AVAILABLE else "Execute: pip install azure-identity",
    )
    check(
        "pyodbc",
        PYODBC_AVAILABLE,
        "Disponível" if PYODBC_AVAILABLE else "Execute: pip install pyodbc",
    )

    if PYODBC_AVAILABLE:
        drivers = pyodbc.drivers()
        check(
            "ODBC Driver 18",
            ODBC_DRIVER in drivers,
            "Instalado" if ODBC_DRIVER in drivers else f"Não encontrado. Disponíveis: {drivers}",
        )

    # Registry
    registry = _get_registry()
    check(
        "Registry (FABRIC_SQL_LAKEHOUSES)",
        bool(registry),
        f"{len(registry)} lakehouse(s): {list(registry.keys())}"
        if registry
        else "Não configurado. Use FABRIC_SQL_LAKEHOUSES no .env",
    )

    # Resolve params
    resolved_endpoint = resolved_db = None
    try:
        resolved_endpoint, resolved_db = _resolve_connection_params(lakehouse)
        check("Lakehouse resolvido", True, f"{resolved_db} → {resolved_endpoint}")
    except RuntimeError as e:
        check("Lakehouse resolvido", False, str(e))

    # Conectividade
    if resolved_endpoint:
        env_vars = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]
        for var in env_vars:
            val = os.environ.get(var, "")
            display = f"{val[:8]}***" if val and "SECRET" in var else (val or "NÃO CONFIGURADO")
            check(f"ENV:{var}", bool(val), display)

        if all(os.environ.get(v) for v in env_vars) and report["status"] == "ok":
            try:
                conn = _get_connection(lakehouse)
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                conn.close()
                check("Conectividade SQL", True, f"{version[:80]}...")
            except Exception as e:
                check("Conectividade SQL", False, str(e))

    return json.dumps(report, ensure_ascii=False, indent=2)


@mcp.tool()
def fabric_sql_list_schemas(lakehouse: str | None = None) -> str:
    """
    Lista todos os schemas disponíveis no Lakehouse (bronze, silver, gold, dbo...).

    IMPORTANTE: Use esta ferramenta (não mcp__fabric_community__list_tables) para
    schemas customizados. A REST API só enxerga o schema dbo.

    Args:
        lakehouse: Nome do lakehouse. Se None, usa o default.
                   Use fabric_sql_list_lakehouses() para ver os disponíveis.
                   Exemplos: "TARN_LH_DEV", "TARN_LH_PROD"
    """
    try:
        conn = _get_connection(lakehouse)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
            "WHERE SCHEMA_NAME NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
            "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
            "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
            "ORDER BY SCHEMA_NAME"
        )
        schemas = [row[0] for row in cursor.fetchall()]
        conn.close()
        _, db = _resolve_connection_params(lakehouse)
        return json.dumps(
            {"lakehouse": db, "schemas": schemas, "count": len(schemas)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def fabric_sql_list_tables(schema: str | None = None, lakehouse: str | None = None) -> str:
    """
    Lista todas as tabelas no Lakehouse com schema, nome e tipo.

    IMPORTANTE: Use esta ferramenta (não mcp__fabric_community__list_tables) para
    schemas customizados (bronze, silver, gold). A REST API só lista o schema dbo.

    Args:
        schema: Filtra por schema específico. Ex: "bronze", "silver", "gold".
                Se None, retorna tabelas de todos os schemas.
        lakehouse: Nome do lakehouse. Se None, usa o default.
                   Use fabric_sql_list_lakehouses() para ver os disponíveis.
    """
    try:
        conn = _get_connection(lakehouse)
        cursor = conn.cursor()
        if schema:
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                "FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                schema,
            )
        else:
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
                "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
                "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
        tables = [{"schema": r[0], "table": r[1], "type": r[2]} for r in cursor.fetchall()]
        conn.close()
        _, db = _resolve_connection_params(lakehouse)
        return json.dumps(
            {"lakehouse": db, "tables": tables, "count": len(tables)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def fabric_sql_describe_table(schema: str, table: str, lakehouse: str | None = None) -> str:
    """
    Retorna a definição completa de uma tabela: colunas, tipos e nullability.

    Args:
        schema: Nome do schema. Ex: "bronze", "silver", "gold", "dbo".
        table: Nome da tabela. Ex: "tb_clientes", "fato_vendas".
        lakehouse: Nome do lakehouse. Se None, usa o default.
    """
    try:
        conn = _get_connection(lakehouse)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, "
            "CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, COLUMN_DEFAULT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
            schema,
            table,
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return json.dumps(
                {
                    "error": f"Tabela '{schema}.{table}' não encontrada.",
                    "hint": "Use fabric_sql_list_tables() para confirmar o nome.",
                },
                ensure_ascii=False,
            )
        _, db = _resolve_connection_params(lakehouse)
        return json.dumps(
            {
                "lakehouse": db,
                "schema": schema,
                "table": table,
                "full_name": f"{schema}.{table}",
                "columns": [
                    {
                        "position": r[0],
                        "column": r[1],
                        "type": r[2],
                        "nullable": r[3] == "YES",
                        "max_length": r[4],
                        "precision": r[5],
                        "scale": r[6],
                        "default": r[7],
                    }
                    for r in rows
                ],
                "column_count": len(rows),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def fabric_sql_execute(query: str, max_rows: int = 100, lakehouse: str | None = None) -> str:
    """
    Executa uma query T-SQL no Fabric SQL Analytics Endpoint.
    Permite: SELECT, CTEs (WITH), INFORMATION_SCHEMA queries.
    Bloqueia: INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE.

    Args:
        query: Query T-SQL. Ex: "SELECT TOP 10 * FROM gold.fato_vendas"
        max_rows: Máximo de linhas (padrão: 100, limite: 1000).
        lakehouse: Nome do lakehouse. Se None, usa o default.
                   Use fabric_sql_list_lakehouses() para ver os disponíveis.
    """
    normalized = query.strip().upper().lstrip("(").split()
    first_word = normalized[0] if normalized else ""
    if first_word in _BLOCKED_SQL_PREFIXES:
        return json.dumps(
            {
                "error": f"Operação '{first_word}' não permitida.",
                "allowed": "SELECT, CTEs (WITH ...), INFORMATION_SCHEMA queries",
            },
            ensure_ascii=False,
        )

    max_rows = min(max(1, max_rows), 1000)
    try:
        conn = _get_connection(lakehouse)
        cursor = conn.cursor()
        cursor.execute(query)

        if cursor.description:
            columns = [col[0] for col in cursor.description]
            raw_rows = cursor.fetchmany(max_rows)
            serialized = [_serialize_row(r) for r in raw_rows]
            has_more = cursor.fetchone() is not None
            conn.close()
            _, db = _resolve_connection_params(lakehouse)
            return json.dumps(
                {
                    "lakehouse": db,
                    "columns": columns,
                    "rows": serialized,
                    "row_count": len(serialized),
                    "truncated": has_more,
                    "max_rows_limit": max_rows,
                },
                ensure_ascii=False,
            )
        else:
            affected = cursor.rowcount
            conn.close()
            return json.dumps({"message": "OK", "rows_affected": affected}, ensure_ascii=False)

    except Exception as e:
        return _error_response(e)


@mcp.tool()
def fabric_sql_sample_table(
    schema: str, table: str, rows: int = 10, lakehouse: str | None = None
) -> str:
    """
    Retorna uma amostra de dados de uma tabela do Lakehouse.

    Args:
        schema: Nome do schema. Ex: "bronze", "silver", "gold".
        table: Nome da tabela.
        rows: Linhas a amostrar (padrão: 10, máximo: 100).
        lakehouse: Nome do lakehouse. Se None, usa o default.
    """
    rows = min(max(1, rows), 100)
    return fabric_sql_execute(
        f"SELECT TOP {rows} * FROM [{schema}].[{table}]",  # nosec B608
        max_rows=rows,
        lakehouse=lakehouse,
    )


@mcp.tool()
def fabric_sql_count_tables_by_schema(lakehouse: str | None = None) -> str:
    """
    Retorna contagem de tabelas por schema — visão geral rápida do Lakehouse.

    Args:
        lakehouse: Nome do lakehouse. Se None, usa o default.
    """
    return fabric_sql_execute(
        "SELECT TABLE_SCHEMA, COUNT(*) AS table_count "
        "FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
        "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
        "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
        "GROUP BY TABLE_SCHEMA ORDER BY TABLE_SCHEMA",
        max_rows=50,
        lakehouse=lakehouse,
    )


# ─── Entry Point ─────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    mcp.run()


if __name__ == "__main__":
    main()
