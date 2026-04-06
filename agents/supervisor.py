"""
Módulo principal do Agent Supervisor.

Constrói o ClaudeAgentOptions com:
  - System prompt do orquestrador
  - Subagents especialistas carregados dinamicamente via agents/registry/
  - Servidores MCP das plataformas com credenciais configuradas
  - Hooks de auditoria e segurança
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

from claude_agent_sdk import ClaudeAgentOptions, HookMatcher

from agents.loader import load_all_agents
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
    thinking_config = (
        {"type": "enabled", "budget_tokens": 8000}
        if enable_thinking
        else {"type": "disabled"}
    )

    # Carregamento dinâmico de agentes via Markdown/YAML
    # Lê todos os arquivos .md em agents/registry/ e instancia AgentDefinition
    agents = load_all_agents()

    return ClaudeAgentOptions(
        # --- Modelo e System Prompt ---
        model=settings.default_model,
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,

        # --- Tools do Supervisor (planejamento e delegação apenas) ---
        allowed_tools=[
            "Agent",            # Invocar subagents especialistas
            "Read",             # Ler arquivos locais (KBs, schemas, configs, skills)
            "Grep",             # Buscar conteúdo em arquivos
            "Glob",             # Encontrar arquivos por padrão
            "Write",            # Salvar PRDs e artefatos em output/
            "AskUserQuestion",  # Esclarecer ambiguidades com o usuário
            "Bash",             # Executar comandos auxiliares (mkdir, etc.)
        ],

        # --- Subagents Especialistas (carregados dinamicamente do registry) ---
        agents=agents,

        # --- Servidores MCP (plataformas com credenciais disponíveis) ---
        mcp_servers=build_mcp_registry(platforms),

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
