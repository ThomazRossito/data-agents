"""
Migration Source — MCP Server Customizado.

Conecta a bancos relacionais de origem (SQL Server e PostgreSQL) para extração
completa de metadados: schemas, tabelas, DDL, views, procedures, functions e stats.

Usado pelo agente migration-expert para as fases de ASSESS e ANALYZE.
Todos os acessos são somente leitura — nenhuma operação de escrita é permitida.

MULTI-SOURCE: Suporta múltiplos bancos via MIGRATION_SOURCES (JSON registry).
O agente passa o parâmetro `source` opcionalmente em qualquer tool.

Configuração no .env:

  MIGRATION_SOURCES={
    "ERP_PROD":  {"type": "sqlserver",  "host": "10.0.0.1", "port": 1433, "database": "ERP",       "user": "sa",       "password": "..."},
    "ANALYTICS": {"type": "postgresql", "host": "10.0.0.3", "port": 5432, "database": "analytics",  "user": "postgres", "password": "..."}
  }
  MIGRATION_DEFAULT_SOURCE=ERP_PROD

Pré-requisitos:
  SQL Server:  ODBC Driver 18 para SQL Server
    macOS: HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18
    Linux: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server

  PostgreSQL:  psycopg2-binary (incluído no pyproject.toml)
"""

from __future__ import annotations

import json
import logging
import os
import traceback
from typing import Any

logger = logging.getLogger("migration_source_mcp")

try:
    import pyodbc

    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

from mcp.server.fastmcp import FastMCP  # noqa: E402

# ─── Constantes ───────────────────────────────────────────────────────────────

ODBC_DRIVERS_SQLSERVER = ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"]

mcp = FastMCP("migration-source")


# ─── Registry e Resolução ────────────────────────────────────────────────────


def _get_registry() -> dict[str, dict]:
    """
    Carrega o registry de fontes de migração do MIGRATION_SOURCES (JSON).
    Formato: {"NOME": {"type": "sqlserver|postgresql", "host": ..., "port": ..., "database": ..., "user": ..., "password": ...}}
    """
    raw = os.environ.get("MIGRATION_SOURCES", "").strip()
    if not raw:
        return {}
    try:
        registry = json.loads(raw)
        if not isinstance(registry, dict):
            logger.error(
                "MIGRATION_SOURCES deve ser um objeto JSON (dict), não lista ou primitivo."
            )
            return {}
        return registry
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear MIGRATION_SOURCES: {e}")
        return {}


def _resolve_source_config(source: str | None) -> tuple[str, dict]:
    """
    Resolve (source_name, config_dict) para uma fonte de migração.

    Prioridade:
      1. source especificado → busca no registry
      2. source não encontrado no registry → erro com sugestão
      3. source=None → usa o default (MIGRATION_DEFAULT_SOURCE)

    Returns:
        (source_name, config_dict)

    Raises:
        RuntimeError com mensagem clara se a fonte não for encontrada.
    """
    registry = _get_registry()

    if source:
        config = registry.get(source)
        if not config:
            available = list(registry.keys()) or ["(registry vazio)"]
            raise RuntimeError(
                f"Fonte '{source}' não encontrada no registry.\n"
                f"Fontes disponíveis: {available}\n\n"
                f"Para adicionar, edite o .env:\n"
                f'  MIGRATION_SOURCES={{..., "{source}": {{"type": "sqlserver", "host": "...", "port": 1433, "database": "...", "user": "...", "password": "..."}}}}'
            )
        return source, config

    default_name = os.environ.get("MIGRATION_DEFAULT_SOURCE", "").strip()

    if default_name and registry:
        config = registry.get(default_name)
        if config:
            return default_name, config
        raise RuntimeError(
            f"MIGRATION_DEFAULT_SOURCE='{default_name}' não encontrado no registry.\n"
            f"Fontes no registry: {list(registry.keys())}"
        )

    if not registry:
        raise RuntimeError(
            "Nenhuma fonte de migração configurada.\n\n"
            "No .env, adicione:\n"
            '  MIGRATION_SOURCES={"MINHA_FONTE": {"type": "sqlserver", "host": "...", "port": 1433, "database": "...", "user": "...", "password": "..."}}\n'
            "  MIGRATION_DEFAULT_SOURCE=MINHA_FONTE"
        )

    first_name = list(registry.keys())[0]
    return first_name, registry[first_name]


# ─── Conexão ─────────────────────────────────────────────────────────────────


def _get_sqlserver_connection(config: dict):
    """Abre conexão com SQL Server via pyodbc."""
    if not PYODBC_AVAILABLE:
        raise RuntimeError("pyodbc não instalado. Execute: pip install pyodbc")

    driver = None
    for d in ODBC_DRIVERS_SQLSERVER:
        if d in pyodbc.drivers():
            driver = d
            break
    if not driver:
        raise RuntimeError(
            f"Nenhum ODBC Driver para SQL Server encontrado.\n"
            f"Drivers instalados: {pyodbc.drivers()}\n"
            "Instale com: HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18"
        )

    host = config["host"]
    port = config.get("port", 1433)
    database = config["database"]
    user = config["user"]
    password = config["password"]

    conn_str = (
        f"Driver={{{driver}}};"
        f"Server={host},{port};"
        f"Database={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=Yes;"
        "TrustServerCertificate=Yes;"
        "Connection Timeout=30;"
    )
    conn = pyodbc.connect(conn_str)
    conn.timeout = 60
    return conn


def _get_postgresql_connection(config: dict):
    """Abre conexão com PostgreSQL via psycopg2."""
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 não instalado. Execute: pip install psycopg2-binary")

    return psycopg2.connect(
        host=config["host"],
        port=config.get("port", 5432),
        dbname=config["database"],
        user=config["user"],
        password=config["password"],
        connect_timeout=30,
    )


def _get_connection(source: str | None = None):
    """
    Abre conexão com a fonte de migração especificada.
    Retorna (conn, source_name, db_type).
    """
    source_name, config = _resolve_source_config(source)
    db_type = config.get("type", "").lower()

    if db_type == "sqlserver":
        conn = _get_sqlserver_connection(config)
    elif db_type == "postgresql":
        conn = _get_postgresql_connection(config)
    else:
        raise RuntimeError(
            f"Tipo de banco '{db_type}' não suportado.\nTipos suportados: 'sqlserver', 'postgresql'"
        )

    return conn, source_name, db_type


def _fetchall(conn, db_type: str, query: str, params: tuple = ()) -> list[tuple]:
    """Executa query e retorna todas as linhas. Abstrai diferenças de placeholder."""
    cursor = conn.cursor()
    if db_type == "sqlserver" and "?" not in query and "%s" in query:
        query = query.replace("%s", "?")
    elif db_type == "postgresql" and "?" in query and "%s" not in query:
        query = query.replace("?", "%s")
    cursor.execute(query, params)
    return cursor.fetchall()


def _serialize_row(row: Any) -> list:
    result = []
    for val in row:
        if val is None:
            result.append(None)
        elif hasattr(val, "isoformat"):
            result.append(val.isoformat())
        elif isinstance(val, (bytes, bytearray)):
            result.append(val.hex())
        elif isinstance(val, float) and val != val:
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
def migration_source_list_sources() -> str:
    """
    Lista todas as fontes de migração disponíveis no registry (MIGRATION_SOURCES).
    Use este tool para saber quais fontes podem ser usadas no parâmetro 'source'.

    Returns:
        JSON com lista de fontes configuradas, tipos e a fonte default.
    """
    registry = _get_registry()
    default = os.environ.get("MIGRATION_DEFAULT_SOURCE", "")

    sources = []
    for name, config in registry.items():
        sources.append(
            {
                "name": name,
                "type": config.get("type", "unknown"),
                "host": config.get("host", ""),
                "database": config.get("database", ""),
                "is_default": name == default,
            }
        )

    return json.dumps(
        {
            "sources": sources,
            "default": default or (list(registry.keys())[0] if registry else None),
            "count": len(sources),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.tool()
def migration_source_diagnostics(source: str | None = None) -> str:
    """
    Diagnóstico completo da conexão a uma fonte de migração.
    Execute este tool quando houver erros de conexão.

    Args:
        source: Nome da fonte a diagnosticar. Se None, usa o default.
                Use migration_source_list_sources() para ver as disponíveis.
    """
    report: dict[str, Any] = {"status": "ok", "checks": [], "source_requested": source}

    def check(name: str, ok: bool, detail: str) -> None:
        report["checks"].append({"check": name, "status": "✅" if ok else "❌", "detail": detail})
        if not ok:
            report["status"] = "error"

    registry = _get_registry()
    check(
        "Registry (MIGRATION_SOURCES)",
        bool(registry),
        f"{len(registry)} fonte(s): {list(registry.keys())}"
        if registry
        else "Não configurado. Use MIGRATION_SOURCES no .env",
    )

    resolved_name = resolved_config = resolved_type = None
    try:
        resolved_name, resolved_config = _resolve_source_config(source)
        resolved_type = resolved_config.get("type", "unknown")
        check(
            "Fonte resolvida",
            True,
            f"{resolved_name} ({resolved_type}) → {resolved_config.get('host')}:{resolved_config.get('port')}/{resolved_config.get('database')}",
        )
    except RuntimeError as e:
        check("Fonte resolvida", False, str(e))

    if resolved_type == "sqlserver":
        check(
            "pyodbc", PYODBC_AVAILABLE, "Disponível" if PYODBC_AVAILABLE else "pip install pyodbc"
        )
        if PYODBC_AVAILABLE:
            drivers = pyodbc.drivers()
            found = next((d for d in ODBC_DRIVERS_SQLSERVER if d in drivers), None)
            check(
                "ODBC Driver SQL Server",
                bool(found),
                found if found else f"Não encontrado. Disponíveis: {drivers}",
            )
    elif resolved_type == "postgresql":
        check(
            "psycopg2",
            PSYCOPG2_AVAILABLE,
            "Disponível" if PSYCOPG2_AVAILABLE else "pip install psycopg2-binary",
        )

    if resolved_config and report["status"] == "ok":
        try:
            conn, _, db_type = _get_connection(source)
            if db_type == "sqlserver":
                rows = _fetchall(conn, db_type, "SELECT @@VERSION")
                version = rows[0][0][:80]
            else:
                rows = _fetchall(conn, db_type, "SELECT version()")
                version = rows[0][0][:80]
            conn.close()
            check("Conectividade", True, version)
        except Exception as e:
            check("Conectividade", False, str(e))

    return json.dumps(report, ensure_ascii=False, indent=2)


@mcp.tool()
def migration_source_list_schemas(source: str | None = None) -> str:
    """
    Lista todos os schemas disponíveis na fonte de migração.

    Args:
        source: Nome da fonte. Se None, usa o default.
                Use migration_source_list_sources() para ver as disponíveis.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            rows = _fetchall(
                conn,
                db_type,
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
                "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
                "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
                "ORDER BY SCHEMA_NAME",
            )
        else:
            rows = _fetchall(
                conn,
                db_type,
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
                "AND schema_name NOT LIKE 'pg_temp_%' AND schema_name NOT LIKE 'pg_toast_temp_%' "
                "ORDER BY schema_name",
            )

        schemas = [row[0] for row in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "schemas": schemas, "count": len(schemas)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_list_tables(schema: str | None = None, source: str | None = None) -> str:
    """
    Lista todas as tabelas na fonte de migração.

    Args:
        schema: Filtra por schema específico. Se None, retorna de todos os schemas.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                    "FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = ? "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE "
                    "FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
                    "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
                    "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                )
        else:
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT table_schema, table_name, table_type "
                    "FROM information_schema.tables WHERE table_schema = %s "
                    "ORDER BY table_schema, table_name",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT table_schema, table_name, table_type "
                    "FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema','pg_toast') "
                    "AND table_schema NOT LIKE 'pg_temp_%' "
                    "ORDER BY table_schema, table_name",
                )

        tables = [{"schema": r[0], "table": r[1], "type": r[2]} for r in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "tables": tables, "count": len(tables)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_describe_table(schema: str, table: str, source: str | None = None) -> str:
    """
    Retorna definição completa de uma tabela: colunas, tipos, nullability, PKs, FKs e indexes.

    Args:
        schema: Nome do schema.
        table: Nome da tabela.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        # Colunas
        if db_type == "sqlserver":
            col_rows = _fetchall(
                conn,
                db_type,
                "SELECT ORDINAL_POSITION, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, "
                "CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE, COLUMN_DEFAULT "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ? ORDER BY ORDINAL_POSITION",
                (schema, table),
            )
        else:
            col_rows = _fetchall(
                conn,
                db_type,
                "SELECT ordinal_position, column_name, data_type, is_nullable, "
                "character_maximum_length, numeric_precision, numeric_scale, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (schema, table),
            )

        if not col_rows:
            conn.close()
            return json.dumps(
                {
                    "error": f"Tabela '{schema}.{table}' não encontrada.",
                    "hint": "Use migration_source_list_tables() para confirmar o nome.",
                },
                ensure_ascii=False,
            )

        columns = [
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
            for r in col_rows
        ]

        # Primary Keys
        if db_type == "sqlserver":
            pk_rows = _fetchall(
                conn,
                db_type,
                "SELECT kcu.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
                "ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
                "AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA AND tc.TABLE_NAME = kcu.TABLE_NAME "
                "WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
                "AND tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ? "
                "ORDER BY kcu.ORDINAL_POSITION",
                (schema, table),
            )
        else:
            pk_rows = _fetchall(
                conn,
                db_type,
                "SELECT kcu.column_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "ON tc.constraint_name = kcu.constraint_name "
                "AND tc.table_schema = kcu.table_schema AND tc.table_name = kcu.table_name "
                "WHERE tc.constraint_type = 'PRIMARY KEY' "
                "AND tc.table_schema = %s AND tc.table_name = %s "
                "ORDER BY kcu.ordinal_position",
                (schema, table),
            )
        primary_keys = [r[0] for r in pk_rows]

        # Foreign Keys
        if db_type == "sqlserver":
            fk_rows = _fetchall(
                conn,
                db_type,
                "SELECT kcu.COLUMN_NAME, ccu.TABLE_SCHEMA, ccu.TABLE_NAME, ccu.COLUMN_NAME "
                "FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc "
                "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
                "JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu ON rc.UNIQUE_CONSTRAINT_NAME = ccu.CONSTRAINT_NAME "
                "WHERE kcu.TABLE_SCHEMA = ? AND kcu.TABLE_NAME = ?",
                (schema, table),
            )
        else:
            fk_rows = _fetchall(
                conn,
                db_type,
                "SELECT kcu.column_name, ccu.table_schema, ccu.table_name, ccu.column_name "
                "FROM information_schema.referential_constraints rc "
                "JOIN information_schema.key_column_usage kcu ON rc.constraint_name = kcu.constraint_name "
                "JOIN information_schema.constraint_column_usage ccu ON rc.unique_constraint_name = ccu.constraint_name "
                "WHERE kcu.table_schema = %s AND kcu.table_name = %s",
                (schema, table),
            )
        foreign_keys = [
            {
                "column": r[0],
                "references_schema": r[1],
                "references_table": r[2],
                "references_column": r[3],
            }
            for r in fk_rows
        ]

        # Indexes
        if db_type == "sqlserver":
            idx_rows = _fetchall(
                conn,
                db_type,
                "SELECT i.name, i.type_desc, i.is_unique, STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns "
                "FROM sys.indexes i "
                "JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
                "JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id "
                "WHERE i.object_id = OBJECT_ID(?) AND i.is_primary_key = 0 "
                "GROUP BY i.name, i.type_desc, i.is_unique",
                (f"{schema}.{table}",),
            )
        else:
            idx_rows = _fetchall(
                conn,
                db_type,
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE schemaname = %s AND tablename = %s "
                "AND indexname NOT LIKE '%_pkey'",
                (schema, table),
            )
        indexes = [_serialize_row(r) for r in idx_rows]

        conn.close()
        return json.dumps(
            {
                "source": source_name,
                "schema": schema,
                "table": table,
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "column_count": len(columns),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_get_table_ddl(schema: str, table: str, source: str | None = None) -> str:
    """
    Gera o DDL CREATE TABLE completo de uma tabela, incluindo PKs e FKs.
    Útil para a fase de TRANSPILE — converte para Spark SQL ou T-SQL Fabric.

    Args:
        schema: Nome do schema.
        table: Nome da tabela.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        raw = migration_source_describe_table(schema, table, source)
        meta = json.loads(raw)

        if "error" in meta:
            return raw

        db_type = _get_connection(source)[2]
        lines = [f"CREATE TABLE {schema}.{table} ("]
        col_defs = []

        for col in meta["columns"]:
            col_type = col["type"].upper()
            if col["max_length"] and col["max_length"] > 0:
                col_type += f"({col['max_length']})"
            elif col["precision"] and col["scale"] is not None:
                col_type += f"({col['precision']},{col['scale']})"
            nullable = "" if col["nullable"] else " NOT NULL"
            default = f" DEFAULT {col['default']}" if col["default"] else ""
            col_defs.append(f"    {col['column']} {col_type}{nullable}{default}")

        if meta["primary_keys"]:
            pk_cols = ", ".join(meta["primary_keys"])
            col_defs.append(f"    PRIMARY KEY ({pk_cols})")

        for fk in meta["foreign_keys"]:
            col_defs.append(
                f"    FOREIGN KEY ({fk['column']}) "
                f"REFERENCES {fk['references_schema']}.{fk['references_table']} ({fk['references_column']})"
            )

        lines.append(",\n".join(col_defs))
        lines.append(");")

        return json.dumps(
            {
                "source": meta["source"],
                "schema": schema,
                "table": table,
                "db_type": db_type,
                "ddl": "\n".join(lines),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_count_tables_by_schema(source: str | None = None) -> str:
    """
    Retorna contagem de tabelas e views por schema — visão geral rápida da fonte.

    Args:
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            rows = _fetchall(
                conn,
                db_type,
                "SELECT TABLE_SCHEMA, TABLE_TYPE, COUNT(*) AS count "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA','guest','db_owner',"
                "'db_securityadmin','db_accessadmin','db_backupoperator','db_ddladmin',"
                "'db_datawriter','db_datareader','db_denydatawriter','db_denydatareader') "
                "GROUP BY TABLE_SCHEMA, TABLE_TYPE ORDER BY TABLE_SCHEMA, TABLE_TYPE",
            )
        else:
            rows = _fetchall(
                conn,
                db_type,
                "SELECT table_schema, table_type, COUNT(*) AS count "
                "FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog','information_schema','pg_toast') "
                "AND table_schema NOT LIKE 'pg_temp_%' "
                "GROUP BY table_schema, table_type ORDER BY table_schema, table_type",
            )

        result = [{"schema": r[0], "type": r[1], "count": r[2]} for r in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "breakdown": result},
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_list_views(schema: str | None = None, source: str | None = None) -> str:
    """
    Lista todas as views na fonte de migração.

    Args:
        schema: Filtra por schema. Se None, retorna de todos os schemas.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS "
                    "WHERE TABLE_SCHEMA = ? ORDER BY TABLE_SCHEMA, TABLE_NAME",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS "
                    "WHERE TABLE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA') "
                    "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                )
        else:
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT table_schema, table_name FROM information_schema.views "
                    "WHERE table_schema = %s ORDER BY table_schema, table_name",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT table_schema, table_name FROM information_schema.views "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
                    "ORDER BY table_schema, table_name",
                )

        views = [{"schema": r[0], "view": r[1]} for r in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "views": views, "count": len(views)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_get_view_definition(schema: str, view: str, source: str | None = None) -> str:
    """
    Retorna o código-fonte SQL de uma view.

    Args:
        schema: Nome do schema.
        view: Nome da view.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            rows = _fetchall(
                conn,
                db_type,
                "SELECT VIEW_DEFINITION FROM INFORMATION_SCHEMA.VIEWS "
                "WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?",
                (schema, view),
            )
        else:
            rows = _fetchall(
                conn,
                db_type,
                "SELECT view_definition FROM information_schema.views "
                "WHERE table_schema = %s AND table_name = %s",
                (schema, view),
            )

        conn.close()
        if not rows:
            return json.dumps(
                {"error": f"View '{schema}.{view}' não encontrada."},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "source": source_name,
                "schema": schema,
                "view": view,
                "definition": rows[0][0],
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_list_procedures(schema: str | None = None, source: str | None = None) -> str:
    """
    Lista todas as stored procedures na fonte de migração.

    Args:
        schema: Filtra por schema. Se None, retorna de todos os schemas.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT ROUTINE_SCHEMA, ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'PROCEDURE' AND ROUTINE_SCHEMA = ? "
                    "ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT ROUTINE_SCHEMA, ROUTINE_NAME FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'PROCEDURE' "
                    "AND ROUTINE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA') "
                    "ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME",
                )
        else:
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT routine_schema, routine_name FROM information_schema.routines "
                    "WHERE routine_type = 'PROCEDURE' AND routine_schema = %s "
                    "ORDER BY routine_schema, routine_name",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT routine_schema, routine_name FROM information_schema.routines "
                    "WHERE routine_type = 'PROCEDURE' "
                    "AND routine_schema NOT IN ('pg_catalog','information_schema') "
                    "ORDER BY routine_schema, routine_name",
                )

        procedures = [{"schema": r[0], "procedure": r[1]} for r in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "procedures": procedures, "count": len(procedures)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_get_procedure_definition(
    schema: str, procedure: str, source: str | None = None
) -> str:
    """
    Retorna o código-fonte de uma stored procedure.

    Args:
        schema: Nome do schema.
        procedure: Nome da procedure.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            rows = _fetchall(
                conn,
                db_type,
                "SELECT OBJECT_DEFINITION(OBJECT_ID(?)) AS definition",
                (f"{schema}.{procedure}",),
            )
        else:
            rows = _fetchall(
                conn,
                db_type,
                "SELECT pg_get_functiondef(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = %s AND p.proname = %s AND p.prokind = 'p'",
                (schema, procedure),
            )

        conn.close()
        definition = rows[0][0] if rows else None
        if not definition:
            return json.dumps(
                {"error": f"Procedure '{schema}.{procedure}' não encontrada."},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "source": source_name,
                "schema": schema,
                "procedure": procedure,
                "definition": definition,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_list_functions(schema: str | None = None, source: str | None = None) -> str:
    """
    Lista todas as functions na fonte de migração.

    Args:
        schema: Filtra por schema. Se None, retorna de todos os schemas.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT ROUTINE_SCHEMA, ROUTINE_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'FUNCTION' AND ROUTINE_SCHEMA = ? "
                    "ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT ROUTINE_SCHEMA, ROUTINE_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'FUNCTION' "
                    "AND ROUTINE_SCHEMA NOT IN ('sys','INFORMATION_SCHEMA') "
                    "ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME",
                )
        else:
            if schema:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT routine_schema, routine_name, data_type FROM information_schema.routines "
                    "WHERE routine_type = 'FUNCTION' AND routine_schema = %s "
                    "ORDER BY routine_schema, routine_name",
                    (schema,),
                )
            else:
                rows = _fetchall(
                    conn,
                    db_type,
                    "SELECT routine_schema, routine_name, data_type FROM information_schema.routines "
                    "WHERE routine_type = 'FUNCTION' "
                    "AND routine_schema NOT IN ('pg_catalog','information_schema') "
                    "ORDER BY routine_schema, routine_name",
                )

        functions = [{"schema": r[0], "function": r[1], "return_type": r[2]} for r in rows]
        conn.close()
        return json.dumps(
            {"source": source_name, "functions": functions, "count": len(functions)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_get_function_definition(
    schema: str, function: str, source: str | None = None
) -> str:
    """
    Retorna o código-fonte de uma function.

    Args:
        schema: Nome do schema.
        function: Nome da function.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            rows = _fetchall(
                conn,
                db_type,
                "SELECT OBJECT_DEFINITION(OBJECT_ID(?)) AS definition",
                (f"{schema}.{function}",),
            )
        else:
            rows = _fetchall(
                conn,
                db_type,
                "SELECT pg_get_functiondef(p.oid) "
                "FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
                "WHERE n.nspname = %s AND p.proname = %s AND p.prokind = 'f'",
                (schema, function),
            )

        conn.close()
        definition = rows[0][0] if rows else None
        if not definition:
            return json.dumps(
                {"error": f"Function '{schema}.{function}' não encontrada."},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "source": source_name,
                "schema": schema,
                "function": function,
                "definition": definition,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_get_schema_summary(
    schema: str | None = None, source: str | None = None
) -> str:
    """
    Resumo completo de um schema para assessment de migração:
    contagens de tabelas, views, procedures, functions e estimativa de linhas.

    Args:
        schema: Schema a sumarizar. Se None, sumariza todos.
        source: Nome da fonte. Se None, usa o default.
    """
    try:
        conn, source_name, db_type = _get_connection(source)

        summary: dict[str, Any] = {"source": source_name, "schema_filter": schema}

        schema_filter_sql = "AND TABLE_SCHEMA = ?" if schema and db_type == "sqlserver" else ""
        schema_filter_pg = "AND table_schema = %s" if schema and db_type == "postgresql" else ""
        params = (schema,) if schema else ()

        # Contagens básicas
        if db_type == "sqlserver":
            counts = {}
            for obj_type, type_filter in [
                ("tables", "BASE TABLE"),
                ("views", "VIEW"),
            ]:
                q = (
                    f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "  # nosec B608
                    f"WHERE TABLE_TYPE = '{type_filter}' {schema_filter_sql}"
                )
                rows = _fetchall(conn, db_type, q, params)
                counts[obj_type] = rows[0][0]

            for obj_type, routine_type in [
                ("procedures", "PROCEDURE"),
                ("functions", "FUNCTION"),
            ]:
                q = (
                    f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.ROUTINES "  # nosec B608
                    f"WHERE ROUTINE_TYPE = '{routine_type}' {schema_filter_sql.replace('TABLE_SCHEMA', 'ROUTINE_SCHEMA')}"
                )
                rows = _fetchall(conn, db_type, q, params)
                counts[obj_type] = rows[0][0]
        else:
            counts = {}
            for obj_type, type_filter in [
                ("tables", "BASE TABLE"),
                ("views", "VIEW"),
            ]:
                q = (
                    f"SELECT COUNT(*) FROM information_schema.tables "  # nosec B608
                    f"WHERE table_type = '{type_filter}' {schema_filter_pg}"
                )
                rows = _fetchall(conn, db_type, q, params)
                counts[obj_type] = rows[0][0]

            for obj_type, routine_type in [
                ("procedures", "PROCEDURE"),
                ("functions", "FUNCTION"),
            ]:
                q = (
                    f"SELECT COUNT(*) FROM information_schema.routines "  # nosec B608
                    f"WHERE routine_type = '{routine_type}' {schema_filter_pg.replace('table_schema', 'routine_schema')}"
                )
                rows = _fetchall(conn, db_type, q, params)
                counts[obj_type] = rows[0][0]

        summary["object_counts"] = counts
        summary["total_objects"] = sum(counts.values())

        conn.close()
        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return _error_response(e)


@mcp.tool()
def migration_source_sample_table(
    schema: str, table: str, rows: int = 10, source: str | None = None
) -> str:
    """
    Retorna uma amostra de dados de uma tabela da fonte de migração.
    Útil para entender distribuição de dados e detectar PII na fase de ASSESS.

    Args:
        schema: Nome do schema.
        table: Nome da tabela.
        rows: Linhas a amostrar (padrão: 10, máximo: 100).
        source: Nome da fonte. Se None, usa o default.
    """
    rows = min(max(1, rows), 100)
    try:
        conn, source_name, db_type = _get_connection(source)

        if db_type == "sqlserver":
            query = f"SELECT TOP {rows} * FROM [{schema}].[{table}]"  # nosec B608
            result_rows = _fetchall(conn, db_type, query)
            cursor = conn.cursor()
            cursor.execute(f"SELECT TOP 1 * FROM [{schema}].[{table}]")  # nosec B608
            columns = [col[0] for col in cursor.description] if cursor.description else []
        else:
            query = f'SELECT * FROM "{schema}"."{table}" LIMIT {rows}'  # nosec B608
            cursor = conn.cursor()
            cursor.execute(query)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            result_rows = cursor.fetchall()

        serialized = [_serialize_row(r) for r in result_rows]
        conn.close()

        return json.dumps(
            {
                "source": source_name,
                "schema": schema,
                "table": table,
                "columns": columns,
                "rows": serialized,
                "row_count": len(serialized),
            },
            ensure_ascii=False,
        )
    except Exception as e:
        return _error_response(e)


# ─── Entry Point ─────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    mcp.run()


if __name__ == "__main__":
    main()
