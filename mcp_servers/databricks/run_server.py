"""
Wrapper para o databricks-mcp-server que redireciona o log para logs/.

O pacote `databricks-mcp` hardcoda "databricks_mcp.log" como caminho relativo
em main.py:setup_logging. Sem variável de ambiente para sobrescrever, o arquivo
sempre cai no CWD (raiz do projeto). Este wrapper chama configure_logging com
caminho absoluto antes de subir o servidor, interceptando o setup original.
"""

import asyncio
import logging
from pathlib import Path

# Resolve caminho absoluto do projeto, independente de onde o processo foi iniciado
_project_root = Path(__file__).parent.parent.parent
_logs_dir = _project_root / "logs"
_logs_dir.mkdir(exist_ok=True)
_log_file = str(_logs_dir / "databricks_mcp.log")

from databricks_mcp.core.config import settings as _dbc_settings  # noqa: E402
from databricks_mcp.core.logging_utils import configure_logging  # noqa: E402

configure_logging(level=_dbc_settings.LOG_LEVEL.upper(), log_file=_log_file)

from databricks_mcp.server.databricks_mcp_server import DatabricksMCPServer  # noqa: E402


async def _run() -> None:
    logger = logging.getLogger(__name__)
    logger.info("Starting Databricks MCP server (log → %s)", _log_file)
    server = DatabricksMCPServer()
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(_run())
