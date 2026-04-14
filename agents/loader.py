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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from claude_agent_sdk import AgentDefinition

from mcp_servers.context7.server_config import CONTEXT7_MCP_TOOLS
from mcp_servers.databricks.server_config import (
    DATABRICKS_MCP_TOOLS,
    DATABRICKS_MCP_READONLY_TOOLS,
    DATABRICKS_AIBI_TOOLS,
    DATABRICKS_SERVING_TOOLS,
    DATABRICKS_COMPUTE_TOOLS,
)
from mcp_servers.databricks_genie.server_config import (
    DATABRICKS_GENIE_MCP_TOOLS,
    DATABRICKS_GENIE_MCP_READONLY_TOOLS,
)
from mcp_servers.fabric.server_config import (
    FABRIC_MCP_TOOLS,
    FABRIC_COMMUNITY_MCP_TOOLS,
)
from mcp_servers.fabric_rti.server_config import (
    FABRIC_RTI_MCP_TOOLS,
    FABRIC_RTI_READONLY_TOOLS,
)
from mcp_servers.fabric_sql.server_config import FABRIC_SQL_MCP_TOOLS
from mcp_servers.firecrawl.server_config import FIRECRAWL_MCP_TOOLS
from mcp_servers.github.server_config import (
    GITHUB_MCP_TOOLS,
    GITHUB_MCP_READONLY_TOOLS,
)
from mcp_servers.memory_mcp.server_config import (
    MEMORY_MCP_TOOLS,
    MEMORY_MCP_READONLY_TOOLS,
)
from mcp_servers.postgres.server_config import POSTGRES_MCP_TOOLS
from mcp_servers.tavily.server_config import TAVILY_MCP_TOOLS

from memory.store import MemoryStore
from memory.retrieval import retrieve_relevant_memories, format_memories_for_injection
from memory.decay import apply_decay

logger = logging.getLogger("data_agents.loader")

# Diretório padrão de definições de agentes
AGENTS_REGISTRY_DIR = Path(__file__).parent / "registry"

# Diretório base das Knowledge Bases
KB_BASE_DIR = Path(__file__).parent.parent / "kb"

# Arquivo de prefixo de cache compartilhado (Ch. 9 — Fork Agents & Prompt Cache)
CACHE_PREFIX_PATH = Path(__file__).parent / "cache_prefix.md"

# Separador entre prefixo compartilhado e corpo específico do agente
_CACHE_PREFIX_SEPARATOR = "\n\n---\n\n"

# Mapeamento de aliases de tool sets para listas concretas de tools MCP
MCP_TOOL_SETS: dict[str, list[str]] = {
    "databricks_all": DATABRICKS_MCP_TOOLS,
    "databricks_readonly": DATABRICKS_MCP_READONLY_TOOLS,
    # Novos aliases granulares para as tools do ai-dev-kit
    "databricks_aibi": DATABRICKS_AIBI_TOOLS,  # Genie, Dashboards, KA, MAS
    "databricks_serving": DATABRICKS_SERVING_TOOLS,  # Model Serving endpoints
    "databricks_compute": DATABRICKS_COMPUTE_TOOLS,  # Clusters, execute_code, wait_for_run
    "databricks_genie_all": DATABRICKS_GENIE_MCP_TOOLS,
    "databricks_genie_readonly": DATABRICKS_GENIE_MCP_READONLY_TOOLS,
    "fabric_all": FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS,
    "fabric_readonly": [
        t
        for t in FABRIC_MCP_TOOLS + FABRIC_COMMUNITY_MCP_TOOLS
        if any(kw in t for kw in ["list_", "get_", "download_", "sample_"])
    ],
    "fabric_rti_all": FABRIC_RTI_MCP_TOOLS,
    "fabric_rti_readonly": FABRIC_RTI_READONLY_TOOLS,
    "fabric_sql_all": FABRIC_SQL_MCP_TOOLS,
    "fabric_sql_readonly": [
        t
        for t in FABRIC_SQL_MCP_TOOLS
        if any(kw in t for kw in ["list_", "describe_", "sample_", "count_", "diagnostics"])
    ],
    # ── MCPs externos ─────────────────────────────────────────────────────────
    # context7: documentação atualizada de bibliotecas (resolve-library-id + get-library-docs)
    "context7_all": CONTEXT7_MCP_TOOLS,
    # tavily: busca web + extração de conteúdo de URLs
    "tavily_all": TAVILY_MCP_TOOLS,
    # github: acesso completo (repos, issues, PRs, commits, branches)
    "github_all": GITHUB_MCP_TOOLS,
    "github_readonly": GITHUB_MCP_READONLY_TOOLS,
    # firecrawl: web scraping e crawling estruturado
    "firecrawl_all": FIRECRAWL_MCP_TOOLS,
    # postgres: queries somente leitura em PostgreSQL
    "postgres_all": POSTGRES_MCP_TOOLS,
    # memory_mcp: knowledge graph persistente de entidades e relações
    "memory_mcp_all": MEMORY_MCP_TOOLS,
    "memory_mcp_readonly": MEMORY_MCP_READONLY_TOOLS,
}


@dataclass
class AgentMeta:
    """
    Metadata-only snapshot de um agente (Ch. 12 — Two-Phase Loading).

    Fase rápida: lê apenas o frontmatter YAML, sem carregar o corpo do prompt.
    Útil para descoberta, roteamento e verificações de capacidade sem pagar
    o custo completo de I/O do carregamento do prompt.

    Para carregamento completo, use load_agent(path=meta.path, ...).
    """

    name: str
    description: str
    model: str
    tier: str
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    kb_domains: list[str] = field(default_factory=list)
    max_turns: int | None = None
    effort: str | None = None
    path: Path = field(default_factory=Path)


def preload_registry(
    registry_dir: Path | None = None,
) -> dict[str, AgentMeta]:
    """
    Fase rápida: escaneia o registry lendo apenas o frontmatter de cada agente (Ch. 12).

    Retorna um dicionário de nome → AgentMeta sem carregar os corpos dos prompts.
    Útil para listagem de agentes, roteamento e verificações antes de iniciar a sessão.

    Args:
        registry_dir: Diretório do registry. Default: agents/registry/.

    Returns:
        Dict de nome_do_agente → AgentMeta.
    """
    registry_dir = registry_dir or AGENTS_REGISTRY_DIR
    agents_meta: dict[str, AgentMeta] = {}

    for path in sorted(registry_dir.glob("*.md")):
        if path.name.startswith("_"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
            metadata, _ = _parse_frontmatter(content)

            name = metadata.get("name", "")
            if not name:
                logger.warning(f"Agente sem 'name' em {path.name} — ignorado no preload")
                continue

            max_turns_raw = metadata.get("max_turns")
            effort_raw = metadata.get("effort")

            agents_meta[name] = AgentMeta(
                name=name,
                description=metadata.get("description", ""),
                model=metadata.get("model", ""),
                tier=metadata.get("tier", ""),
                tools=metadata.get("tools", []),
                mcp_servers=metadata.get("mcp_servers", []),
                kb_domains=metadata.get("kb_domains", []),
                max_turns=int(max_turns_raw) if max_turns_raw is not None else None,
                effort=str(effort_raw) if effort_raw is not None else None,
                path=path,
            )
        except Exception as e:
            logger.warning(f"Erro no preload de {path.name}: {e}")

    logger.info(f"Registry preloaded: {len(agents_meta)} agentes (frontmatter apenas)")
    return agents_meta


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


def _load_kb_indexes(
    kb_domains: list[str],
    kb_base_dir: Path | None = None,
) -> str:
    """
    Carrega o conteúdo dos index.md das KBs relevantes para um agente.

    Lê kb/{domain}/index.md para cada domínio em kb_domains.
    Domínios cujo index.md não exista são silenciosamente ignorados.

    Args:
        kb_domains: Lista de domínios de KB (ex: ["sql-patterns", "databricks"])
        kb_base_dir: Diretório base das KBs. Padrão: kb/ na raiz do projeto.

    Returns:
        String com o conteúdo concatenado dos index.md, formatada para
        injeção no prompt do agente. Retorna string vazia se nenhum index
        for encontrado.
    """
    base = kb_base_dir or KB_BASE_DIR
    sections: list[str] = []

    for domain in kb_domains:
        index_path = base / domain / "index.md"
        if index_path.exists():
            try:
                content = index_path.read_text(encoding="utf-8").strip()
                sections.append(content)
                logger.debug(f"KB index carregado: {domain}/index.md ({len(content)} chars)")
            except Exception as e:
                logger.warning(f"Erro ao ler KB index '{domain}/index.md': {e}")
        else:
            logger.debug(f"KB index não encontrado (ignorado): {domain}/index.md")

    if not sections:
        return ""

    header = (
        "\n\n---\n\n"
        "## [Contexto Injetado] Knowledge Base — Índices Relevantes\n\n"
        "Os índices abaixo foram pré-carregados dos seus domínios de KB (`kb_domains`).\n"
        "Use-os como referência para saber quais arquivos aprofundar via `Read` quando necessário.\n\n"
    )

    return header + "\n\n---\n\n".join(sections)


def _load_cache_prefix(prefix_path: Path | None = None) -> str:
    """
    Carrega o prefixo de cache compartilhado (Ch. 9 — Fork Agents & Prompt Cache).

    O prefixo é um bloco de texto idêntico byte-a-byte que é injetado no
    INÍCIO do system prompt de TODOS os agentes. Isso ativa o prompt caching
    da API do Claude: o prefixo é processado e cacheado uma única vez,
    reduzindo ~40-60% nos custos de tokens de input nas chamadas subsequentes.

    Regra crítica: o conteúdo deste arquivo NUNCA deve conter conteúdo dinâmico
    (timestamps, IDs de sessão, estados variáveis). Qualquer byte diferente
    invalida o cache para aquele agente.

    Args:
        prefix_path: Caminho para o arquivo cache_prefix.md.
            Padrão: agents/cache_prefix.md

    Returns:
        Conteúdo do prefixo como string, ou string vazia se arquivo não existir.
    """
    path = prefix_path or CACHE_PREFIX_PATH
    if not path.exists():
        logger.warning(f"Cache prefix não encontrado: {path} — agentes sem prefixo compartilhado")
        return ""

    try:
        content = path.read_text(encoding="utf-8").strip()
        logger.debug(f"Cache prefix carregado: {len(content)} chars ({path.name})")
        return content
    except Exception as e:
        logger.warning(f"Erro ao ler cache prefix '{path}': {e} — continuando sem prefixo")
        return ""


def load_agent(
    path: Path,
    tier_model_map: dict[str, str] | None = None,
    tier_turns_map: dict[str, int] | None = None,
    tier_effort_map: dict[str, str] | None = None,
    inject_kb_index: bool = False,
    kb_base_dir: Path | None = None,
    inject_cache_prefix: bool = True,
    cache_prefix_path: Path | None = None,
) -> tuple[str, AgentDefinition]:
    """
    Carrega um único arquivo .md e retorna (name, AgentDefinition).

    Args:
        path: Caminho absoluto para o arquivo .md do agente.
        tier_model_map: Mapeamento tier -> modelo para model routing.
            Se None ou vazio, usa o model do frontmatter.
        tier_turns_map: Mapeamento tier -> maxTurns por sub-agente.
            Limita o número de chamadas de tool por chamada ao agente.
            Override por frontmatter: campo `max_turns` no YAML.
            Se None, usa frontmatter ou sem limite.
        tier_effort_map: Mapeamento tier -> effort ("high"/"medium"/"low").
            Controla o nível de raciocínio do modelo por tier.
            Override por frontmatter: campo `effort` no YAML.
            Se None, usa frontmatter ou sem especificação de effort.
        inject_kb_index: Se True, injeta index.md das KBs no prompt.
        kb_base_dir: Diretório base das KBs. Padrão: kb/ na raiz do projeto.
        inject_cache_prefix: Se True (padrão), prepend o prefixo de cache
            compartilhado (agents/cache_prefix.md) ao system prompt.
        cache_prefix_path: Caminho alternativo para o arquivo de prefixo.

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

    # Model routing por tier: se tier_model_map fornecido, usa modelo do mapa
    tier: str = metadata.get("tier", "")
    if tier_model_map and tier in tier_model_map:
        routed_model = tier_model_map[tier]
        logger.info(
            f"Model routing: agente '{name}' tier={tier} → "
            f"model overridden de '{model}' para '{routed_model}'"
        )
        model = routed_model

    # Token budget por tier (Ch. 5 — Agent Loop):
    # Prioridade: frontmatter > tier_turns_map > None (sem limite)
    max_turns_raw = metadata.get("max_turns")
    agent_max_turns: int | None = None
    if max_turns_raw is not None:
        # Override explícito no frontmatter do agente
        agent_max_turns = int(max_turns_raw)
        logger.debug(f"Agente '{name}': maxTurns={agent_max_turns} (frontmatter override)")
    elif tier_turns_map and tier in tier_turns_map:
        agent_max_turns = tier_turns_map[tier]
        logger.debug(f"Agente '{name}': maxTurns={agent_max_turns} (tier={tier} map)")

    # Effort por tier (Ch. 5 — Agent Loop):
    # Prioridade: frontmatter > tier_effort_map > None (sem especificação)
    # Cast para Literal satisfaz mypy — valores válidos: 'low', 'medium', 'high', 'max'
    effort_raw = metadata.get("effort")
    agent_effort: Literal["low", "medium", "high", "max"] | None = None
    if effort_raw is not None:
        agent_effort = cast(Literal["low", "medium", "high", "max"], str(effort_raw))
        logger.debug(f"Agente '{name}': effort={agent_effort} (frontmatter override)")
    elif tier_effort_map and tier in tier_effort_map:
        agent_effort = cast(Literal["low", "medium", "high", "max"], tier_effort_map[tier])
        logger.debug(f"Agente '{name}': effort={agent_effort} (tier={tier} map)")

    # Cache prefix injection (Ch. 9 — Fork Agents & Prompt Cache):
    # Prepend um bloco idêntico byte-a-byte ao topo de todos os agentes.
    # O Claude API detecta o prefixo comum e o cacheia, evitando reprocessamento.
    prefix = ""
    if inject_cache_prefix:
        prefix = _load_cache_prefix(cache_prefix_path)

    # KB injection: carrega e injeta index.md das KBs relevantes no prompt
    kb_domains: list[str] = metadata.get("kb_domains", [])
    kb_content = ""
    if inject_kb_index and kb_domains:
        kb_content = _load_kb_indexes(kb_domains, kb_base_dir=kb_base_dir)
        if kb_content:
            logger.info(f"KB injection: agente '{name}' ← {len(kb_domains)} domínios: {kb_domains}")

    # Resolve aliases de tool sets para tools MCP concretas
    tools = _resolve_tools(tools_raw)

    # Monta o prompt final: [prefixo compartilhado] + [corpo específico] + [KB]
    # O separador --- garante que o prefixo é visualmente distinto do corpo,
    # mas NÃO altera o prefixo em si (só o que vem depois).
    if prefix:
        full_prompt = prefix + _CACHE_PREFIX_SEPARATOR + body + kb_content
    else:
        full_prompt = body + kb_content

    agent = AgentDefinition(
        description=description,
        prompt=full_prompt,
        tools=tools,
        model=model,
        mcpServers=mcp_servers if mcp_servers else None,
        maxTurns=agent_max_turns,
        effort=agent_effort,
    )

    logger.info(
        f"Agente carregado: '{name}' | tier={tier} | model={model} | "
        f"tools={len(tools)} | mcp_servers={len(mcp_servers)} | "
        f"maxTurns={agent_max_turns} | effort={agent_effort} | "
        f"kb_injected={len(kb_domains) if kb_content else 0} | "
        f"cache_prefix={bool(prefix)}"
    )
    return name, agent


def load_all_agents(
    registry_dir: Path | None = None,
    available_mcp_servers: set[str] | None = None,
    tier_model_map: dict[str, str] | None = None,
    tier_turns_map: dict[str, int] | None = None,
    tier_effort_map: dict[str, str] | None = None,
    inject_kb_index: bool = False,
    kb_base_dir: Path | None = None,
    inject_cache_prefix: bool = True,
    cache_prefix_path: Path | None = None,
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
        tier_model_map: Mapeamento tier -> modelo para model routing.
            Se None ou vazio, usa o model do frontmatter (comportamento padrão).
        tier_turns_map: Mapeamento tier -> maxTurns. Se None, sem limite por tier.
        tier_effort_map: Mapeamento tier -> effort. Se None, sem override por tier.
        inject_kb_index: Se True, injeta index.md das KBs no prompt dos agentes.
        kb_base_dir: Diretório base das KBs. Padrão: kb/ na raiz do projeto.
        inject_cache_prefix: Se True (padrão), prepend o prefixo de cache
            compartilhado a todos os agentes. Ver `load_agent` para detalhes.
        cache_prefix_path: Caminho alternativo para o arquivo de prefixo.

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
            name, agent = load_agent(
                path,
                tier_model_map=tier_model_map,
                tier_turns_map=tier_turns_map,
                tier_effort_map=tier_effort_map,
                inject_kb_index=inject_kb_index,
                kb_base_dir=kb_base_dir,
                inject_cache_prefix=inject_cache_prefix,
                cache_prefix_path=cache_prefix_path,
            )

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


def inject_memory_context(query: str, system_prompt: str) -> str:
    """
    Injeta memórias relevantes no system prompt do supervisor.

    Usa o Sonnet lateral para selecionar memórias do store que são
    relevantes para a query atual. Aplica decay antes do retrieval.

    Args:
        query: A query/tarefa atual do usuário.
        system_prompt: System prompt original do supervisor.

    Returns:
        System prompt enriquecido com memórias relevantes.
    """
    try:
        store = MemoryStore()

        # Aplica decay em todas as memórias antes do retrieval
        all_memories = store.list_all(active_only=False)
        if all_memories:
            apply_decay(all_memories, save_fn=store.save)

        # Busca memórias relevantes via Sonnet lateral
        relevant = retrieve_relevant_memories(query, store, max_memories=8)

        if not relevant:
            return system_prompt

        # Formata e injeta
        memory_context = format_memories_for_injection(relevant)
        enriched = system_prompt + memory_context

        logger.info(
            f"Memory injection: {len(relevant)} memórias injetadas "
            f"(+{len(memory_context)} chars no prompt)"
        )
        return enriched

    except Exception as e:
        logger.warning(f"Erro na injeção de memória (continuando sem memória): {e}")
        return system_prompt
