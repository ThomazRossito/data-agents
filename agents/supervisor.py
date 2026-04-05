"""
Módulo principal do Agent Supervisor.

Constrói o ClaudeAgentOptions com:
  - System prompt do orquestrador
  - Subagents especialistas (sql-expert, spark-expert, pipeline-architect)
  - Servidores MCP das plataformas com credenciais configuradas
  - Hooks de auditoria e segurança
  - Configurações de modelo, custo e permissões

Modos de thinking:
  - BMAD Full (/plan): thinking enabled com budget de 8000 tokens — para planejamento complexo
  - Demais modos: thinking disabled — economiza custo/latência em tarefas pontuais
"""

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from agents.definitions.sql_expert import create_sql_expert
from agents.definitions.spark_expert import create_spark_expert
from agents.definitions.pipeline_architect import create_pipeline_architect
from agents.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT
from config.mcp_servers import build_mcp_registry
from config.settings import settings
from hooks.audit_hook import audit_tool_usage
from hooks.cost_guard_hook import log_cost_generating_operations
from hooks.security_hook import block_destructive_commands


def build_supervisor_options(
    platforms: list[str] | None = None,
    enable_thinking: bool = False,
) -> ClaudeAgentOptions:
    """
    Constrói e retorna o ClaudeAgentOptions para o Agent Supervisor.

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
    thinking_config = (
        {"type": "enabled", "budget_tokens": 8000}
        if enable_thinking
        else {"type": "disabled"}
    )

    return ClaudeAgentOptions(
        # --- Modelo e System Prompt ---
        model=settings.default_model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,

        # --- Tools do Supervisor (planejamento e delegação apenas) ---
        allowed_tools=[
            "Agent",            # Invocar subagents especialistas
            "Read",             # Ler arquivos locais (schemas, configs, skills)
            "Grep",             # Buscar conteúdo em arquivos
            "Glob",             # Encontrar arquivos por padrão
            "Write",            # Salvar PRDs e artefatos em output/
            "AskUserQuestion",  # Esclarecer ambiguidades com o usuário
            "Bash",             # Executar comandos auxiliares (mkdir, etc.)
        ],

        # --- Subagents Especialistas ---
        agents={
            "sql-expert":         create_sql_expert(),
            "spark-expert":       create_spark_expert(),
            "pipeline-architect": create_pipeline_architect(),
        },

        # --- Servidores MCP (plataformas com credenciais disponíveis) ---
        mcp_servers=build_mcp_registry(platforms),

        # --- Controle de Execução ---
        permission_mode="acceptEdits",
        max_turns=settings.max_turns,
        max_budget_usd=settings.max_budget_usd,

        # --- Streaming parcial para feedback visual em tempo real ---
        include_partial_messages=True,

        # --- Thinking: desabilitado por padrão; ativo via enable_thinking=True ---
        thinking=thinking_config,
        effort="high",

        # --- Hooks de Auditoria, Custo e Segurança ---
        hooks={
            "PostToolUse": [
                HookMatcher(hooks=[audit_tool_usage]),
                HookMatcher(hooks=[log_cost_generating_operations]),
            ],
            "PreToolUse": [
                HookMatcher(
                    matcher="Bash",
                    hooks=[block_destructive_commands],
                ),
            ],
        },
    )
