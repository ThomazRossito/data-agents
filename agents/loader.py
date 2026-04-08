"""
Agent Loader — Carregamento Dinâmico de Agentes via Markdown/YAML

Lê todos os arquivos .md em agents/registry/ e instancia AgentDefinition
dinamicamente a partir do frontmatter YAML + corpo Markdown.

Formato esperado de cada arquivo de agente:
---
name: agent-name
description: "Descrição do agente."
model: claude-sonnet-4-6
tools: [Read, Grep, Glob, Write]
mcp_servers: [databricks, fabric]
kb_domains: [sql-patterns, data-modeling]
tier: T1
---
# Agent Name
Conteúdo do system prompt em Markdown...

Campos obrigatórios: name, description, model, tools
Campos opcionais: mcp_servers, kb_domains, tier
"""

import logging
import re
from pathlib import Path
from typing import Any

from claude_agent_sdk import AgentDefinition

from mcp_servers.databricks.server_config import (
    DATABRICKS_MCP_TOOLS,
    DATABRICKS_MCP_READONLY_TOOLS,
)
from mcp_servers.fabric.server_config import (
    FABRIC_MCP_TOOLS,
    FABRIC_COMMUNITY_MCP_TOOLS,
)
from mcp_servers.fabric_rti.server_config import (
    FABRIC_RTI_MCP_TOOLS,
    FABRIC_RTI_READONLY_TOOLS,
)

logger = logging.getLogger("data_agents.loader")

# Diretório padrão de definições de agentes
AGENTS_REGISTRY_DIR = Path(__file__).parent / "registry"

# Mapeamento de aliases de tool sets para listas concretas de tools MCP
MCP_TOOL_SETS: dict[str, list[str]] = {
    "databricks_all": DATABRICKS_MCP_TOOLS,
    "databricks_readonly": DATABRICKS_MCP_READONLY_TOOLS,
    "fabric_all": FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS,
    "fabric_readonly": [
        t
        for t in FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS
        if any(kw in t for kw in ["list_", "get_", "download_", "sample_"])
    ],
    "fabric_rti_all": FABRIC_RTI_MCP_TOOLS,
    "fabric_rti_readonly": FABRIC_RTI_READONLY_TOOLS,
}


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Extrai o frontmatter YAML e o corpo Markdown de um arquivo .md.

    Returns:
        Tupla (metadata_dict, body_markdown)
    """
    # Detecta bloco frontmatter delimitado por ---
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
    match = pattern.match(content)

    if not match:
        raise ValueError("Arquivo de agente sem frontmatter YAML válido (delimitado por ---)")

    yaml_block = match.group(1)
    body = match.group(2).strip()

    # Parse manual do YAML simples (evita dependência externa)
    metadata: dict[str, Any] = {}
    for line in yaml_block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            key, _, raw_value = line.partition(":")
            key = key.strip()
            raw_value = raw_value.strip()

            # Lista inline: [item1, item2]
            if raw_value.startswith("[") and raw_value.endswith("]"):
                items = raw_value[1:-1].split(",")
                metadata[key] = [i.strip().strip('"').strip("'") for i in items if i.strip()]
            # String com aspas
            elif raw_value.startswith('"') and raw_value.endswith('"'):
                metadata[key] = raw_value[1:-1]
            elif raw_value.startswith("'") and raw_value.endswith("'"):
                metadata[key] = raw_value[1:-1]
            # Booleano
            elif raw_value.lower() == "true":
                metadata[key] = True
            elif raw_value.lower() == "false":
                metadata[key] = False
            # Número
            elif raw_value.replace(".", "", 1).isdigit():
                metadata[key] = float(raw_value) if "." in raw_value else int(raw_value)
            else:
                metadata[key] = raw_value

    return metadata, body


def _resolve_tools(tool_list: list[str]) -> list[str]:
    """
    Resolve aliases de tool sets para listas concretas de tools MCP.

    Aliases como 'databricks_readonly' são expandidos para a lista completa
    de tools MCP correspondente. Tools literais (ex: 'Read', 'Bash') são
    mantidas como estão.
    """
    resolved: list[str] = []
    for tool in tool_list:
        if tool in MCP_TOOL_SETS:
            resolved.extend(MCP_TOOL_SETS[tool])
        else:
            resolved.append(tool)
    return resolved


def load_agent(path: Path) -> tuple[str, AgentDefinition]:
    """
    Carrega um único arquivo .md e retorna (name, AgentDefinition).

    Args:
        path: Caminho absoluto para o arquivo .md do agente.

    Returns:
        Tupla (agent_name, AgentDefinition)

    Raises:
        ValueError: Se campos obrigatórios estiverem ausentes.
    """
    content = path.read_text(encoding="utf-8")
    metadata, body = _parse_frontmatter(content)

    # Validação de campos obrigatórios
    required = ["name", "description", "model", "tools"]
    missing = [f for f in required if f not in metadata]
    if missing:
        raise ValueError(f"Agente '{path.name}' está faltando campos obrigatórios: {missing}")

    name: str = metadata["name"]
    description: str = metadata["description"]
    model: str = metadata["model"]
    tools_raw: list[str] = metadata["tools"]
    mcp_servers: list[str | dict[str, Any]] = metadata.get("mcp_servers", [])

    # Resolve aliases de tool sets para tools MCP concretas
    tools = _resolve_tools(tools_raw)

    agent = AgentDefinition(
        description=description,
        prompt=body,
        tools=tools,
        model=model,
        mcpServers=mcp_servers if mcp_servers else None,
    )

    logger.info(
        f"Agente carregado: '{name}' | model={model} | "
        f"tools={len(tools)} | mcp_servers={mcp_servers}"
    )
    return name, agent


def load_all_agents(
    registry_dir: Path | None = None,
    available_mcp_servers: set[str] | None = None,
) -> dict[str, AgentDefinition]:
    """
    Carrega todos os agentes do diretório de registry.

    Lê todos os arquivos .md em agents/registry/ (exceto _template.md)
    e instancia AgentDefinition para cada um.

    Se `available_mcp_servers` for fornecido, filtra os mcp_servers de cada
    agente para conter apenas servidores que realmente existem no registry.
    Isso evita que agentes referenciem servidores sem credenciais configuradas,
    o que causa falha silenciosa de conexão MCP no SDK.

    Args:
        registry_dir: Diretório de registry. Padrão: agents/registry/
        available_mcp_servers: Conjunto de nomes de MCP servers disponíveis
            no registry. Se None, não filtra (mantém todos os declarados).

    Returns:
        Dicionário {agent_name: AgentDefinition}
    """
    directory = registry_dir or AGENTS_REGISTRY_DIR

    if not directory.exists():
        logger.warning(f"Diretório de registry não encontrado: {directory}")
        return {}

    agents: dict[str, AgentDefinition] = {}
    agent_files = sorted(directory.glob("*.md"))

    # Ignora arquivos de template
    agent_files = [f for f in agent_files if not f.name.startswith("_")]

    if not agent_files:
        logger.warning(f"Nenhum arquivo .md encontrado em: {directory}")
        return {}

    for path in agent_files:
        try:
            name, agent = load_agent(path)

            # Filtra mcp_servers indisponíveis para evitar erros silenciosos no SDK
            if available_mcp_servers is not None and agent.mcpServers:
                original = list(agent.mcpServers)
                filtered: list[str | dict[str, Any]] = []
                removed: list[str] = []
                for s in original:
                    if isinstance(s, str):
                        if s in available_mcp_servers:
                            filtered.append(s)
                        else:
                            removed.append(s)
                    else:
                        filtered.append(s)  # Ignora verificação para configs inline (dicts)

                agent.mcpServers = filtered if filtered else None
                if removed:
                    logger.info(f"Agente '{name}': mcp_servers indisponíveis removidos: {removed}")

            agents[name] = agent
        except Exception as e:
            logger.error(f"Erro ao carregar agente '{path.name}': {e}")
            # Continua carregando os demais agentes mesmo com erro em um

    logger.info(f"Registry carregado: {len(agents)} agentes — {list(agents.keys())}")
    return agents
