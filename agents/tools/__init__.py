"""Registry de tools MCP para o loop agentico OpenAI."""

from __future__ import annotations

import json
import logging

from agents.tools.databricks import DATABRICKS_TOOLS, dispatch_databricks
from agents.tools.fabric import FABRIC_TOOLS, dispatch_fabric

logger = logging.getLogger(__name__)

_MCP_REGISTRY: dict[str, tuple[list[dict], callable]] = {
    "databricks": (DATABRICKS_TOOLS, dispatch_databricks),
    "fabric": (FABRIC_TOOLS, dispatch_fabric),
}


def load_tools_for_mcps(mcps: list[str]) -> list[dict]:
    tools: list[dict] = []
    for mcp in mcps:
        if mcp in _MCP_REGISTRY:
            tools.extend(_MCP_REGISTRY[mcp][0])
        else:
            logger.warning("MCP '%s' não registrado em agents/tools", mcp)
    return tools


def dispatch_tool(name: str, arguments: str | dict) -> str:
    args = json.loads(arguments) if isinstance(arguments, str) else arguments
    for _mcp, (tool_defs, dispatch_fn) in _MCP_REGISTRY.items():
        tool_names = {t["function"]["name"] for t in tool_defs}
        if name in tool_names:
            return dispatch_fn(name, args)
    return f"Tool '{name}' não encontrada em nenhum MCP registrado."
