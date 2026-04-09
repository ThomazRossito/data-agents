"""
Módulo principal do Agent Supervisor.

Constrói o ClaudeAgentOptions com:
  - System prompt do orquestrador
  - Subagents especialistas carregados dinamicamente via agents/registry/
  - Servidores MCP das plataformas com credenciais configuradas
  - Hooks de auditoria, segurança e compressão de output
  - Configurações de modelo, custo e permissões

Arquitetura de Agentes:
  Os agentes são definidos como arquivos Markdown em agents/registry/*.md
  com frontmatter YAML. O loader dinâmico (agents/loader.py) instancia
  AgentDefinition para cada arquivo, permitindo adicionar novos agentes
  sem modificar código Python.

  Para adicionar um novo agente: crie agents/registry/nome-agente.md
  seguindo o template em agents/registry/_template.md.

Modos de thinking:
  - BMAD Full (/plan): thinking enabled com budget de 8000 tokens — para planejamento complexo
  - Demais modos: thinking disabled — economiza custo/latência em tarefas pontuais
"""

from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from agents.loader import load_all_agents
from agents.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT
from config.mcp_servers import build_mcp_registry
from config.settings import settings
from hooks.audit_hook import audit_tool_usage
from hooks.cost_guard_hook import log_cost_generating_operations
from hooks.output_compressor_hook import compress_tool_output
from hooks.security_hook import block_destructive_commands, check_sql_cost


def build_supervisor_options(
    platforms: list[str] | None = None,
    enable_thinking: bool = False,
) -> ClaudeAgentOptions:
    """
    Constrói e retorna o ClaudeAgentOptions para o Agent Supervisor.

    Os agentes especialistas são carregados dinamicamente a partir dos
    arquivos Markdown em agents/registry/. Para adicionar um novo agente,
    basta criar um arquivo .md no registry — nenhuma modificação de código
    é necessária.

    Args:
        platforms: Plataformas MCP a ativar. None = detecta por credenciais disponíveis.
                   Opções: "databricks", "fabric", "fabric_rti"
        enable_thinking: Se True, ativa thinking com budget de 8000 tokens.
                         Use apenas para BMAD Full (/plan) — tarefas de planejamento complexo.
                         False por padrão para economizar custo e latência.

    Returns:
        ClaudeAgentOptions configurado e pronto para uso com query() ou ClaudeSDKClient.
    """
    # Thinking: ativo apenas quando explicitamente solicitado (modo BMAD Full)
    # Typed as Any because the SDK union (ThinkingConfigEnabled | ThinkingConfigDisabled | ...)
    # is not directly importable here without creating a hard dependency on SDK internals.
    thinking_config: Any = (
        {"type": "enabled", "budget_tokens": 8000} if enable_thinking else {"type": "disabled"}
    )

    # Servidores MCP (plataformas com credenciais disponíveis)
    mcp_registry = build_mcp_registry(platforms)

    # Carregamento dinâmico de agentes via Markdown/YAML
    # Filtra mcp_servers dos agentes para conter apenas servidores disponíveis no registry.
    # Isso evita referências a servidores sem credenciais (ex: fabric_rti sem KUSTO_SERVICE_URI).
    agents = load_all_agents(
        available_mcp_servers=set(mcp_registry.keys()),
        tier_model_map=settings.tier_model_map if settings.tier_model_map else None,
        inject_kb_index=settings.inject_kb_index,
    )

    return ClaudeAgentOptions(
        # --- Modelo e System Prompt ---
        model=settings.default_model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,
        # --- Tools do Supervisor (planejamento e delegação apenas) ---
        allowed_tools=[
            "Agent",  # Invocar subagents especialistas
            "Read",  # Ler arquivos locais (KBs, schemas, configs, skills)
            "Grep",  # Buscar conteúdo em arquivos
            "Glob",  # Encontrar arquivos por padrão
            "Write",  # Salvar PRDs e artefatos em output/
            "AskUserQuestion",  # Esclarecer ambiguidades com o usuário
            "Bash",  # Executar comandos auxiliares (mkdir, etc.)
        ],
        # --- Subagents Especialistas (carregados dinamicamente do registry) ---
        agents=agents,
        # --- Servidores MCP (plataformas com credenciais disponíveis) ---
        mcp_servers=mcp_registry,
        # --- Controle de Execução ---
        # permission_mode="acceptEdits",
        permission_mode="bypassPermissions",
        max_turns=settings.max_turns,
        max_budget_usd=settings.max_budget_usd,
        # --- Streaming parcial para feedback visual em tempo real ---
        include_partial_messages=True,
        # --- Thinking: desabilitado por padrão; ativo via enable_thinking=True ---
        thinking=thinking_config,
        effort="high",
        # --- Hooks de Auditoria, Custo e Segurança ---
        # Hooks use generic dict[str, Any] signatures; SDK expects its own union input types.
        # Behavior is correct at runtime — suppress the list-item mismatch below.
        hooks={
            "PostToolUse": [
                HookMatcher(hooks=[audit_tool_usage]),  # type: ignore[list-item]
                HookMatcher(hooks=[log_cost_generating_operations]),  # type: ignore[list-item]
                # RTK-style: comprime output verboso das tools antes de enviar ao modelo.
                # Executado por último para que audit/cost_guard observem o output original.
                HookMatcher(hooks=[compress_tool_output]),  # type: ignore[list-item]
            ],
            "PreToolUse": [
                HookMatcher(
                    matcher="Bash",
                    hooks=[block_destructive_commands],  # type: ignore[list-item]
                ),
                # check_sql_cost: detecta SELECT * sem WHERE/LIMIT em QUALQUER tool
                # (Bash com spark-sql, execute_sql via MCP, etc.)
                # Sem matcher → intercepta todas as tools.
                HookMatcher(
                    hooks=[check_sql_cost],  # type: ignore[list-item]
                ),
            ],
        },
    )
