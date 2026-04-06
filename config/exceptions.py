"""
Hierarquia de exceções customizadas do Data Agents.

Todas as exceções do projeto herdam de DataAgentsError, permitindo
captura granular por tipo ou genérica pela classe base.

Uso:
    from config.exceptions import MCPConnectionError, BudgetExceededError

    try:
        registry = build_mcp_registry()
    except MCPConnectionError as e:
        logger.warning(f"MCP server indisponível: {e.platform} — {e}")
"""


class DataAgentsError(Exception):
    """Classe base para todas as exceções do Data Agents."""

    def __init__(self, message: str = "", *args, **kwargs):
        self.message = message
        super().__init__(message, *args)


# ─── MCP & Conectividade ─────────────────────────────────────────


class MCPConnectionError(DataAgentsError):
    """Falha ao conectar ou inicializar um servidor MCP."""

    def __init__(self, platform: str, message: str = "", cause: Exception | None = None):
        self.platform = platform
        self.cause = cause
        full_msg = f"[MCP:{platform}] {message}"
        if cause:
            full_msg += f" (causa: {type(cause).__name__}: {cause})"
        super().__init__(full_msg)


class MCPToolExecutionError(DataAgentsError):
    """Falha durante a execução de uma tool MCP."""

    def __init__(self, tool_name: str, message: str = "", cause: Exception | None = None):
        self.tool_name = tool_name
        self.cause = cause
        full_msg = f"[Tool:{tool_name}] {message}"
        if cause:
            full_msg += f" (causa: {type(cause).__name__}: {cause})"
        super().__init__(full_msg)


# ─── Autenticação & Credenciais ──────────────────────────────────


class AuthenticationError(DataAgentsError):
    """Credenciais ausentes ou inválidas para uma plataforma."""

    def __init__(self, platform: str, missing_fields: list[str] | None = None):
        self.platform = platform
        self.missing_fields = missing_fields or []
        fields_str = ", ".join(self.missing_fields) if self.missing_fields else "desconhecido"
        super().__init__(
            f"[Auth:{platform}] Credenciais inválidas ou ausentes: {fields_str}. "
            f"Configure no .env ou como variáveis de ambiente."
        )


# ─── Orçamento & Limites ─────────────────────────────────────────


class BudgetExceededError(DataAgentsError):
    """Custo acumulado da sessão excedeu o limite configurado."""

    def __init__(self, current_cost: float, max_budget: float):
        self.current_cost = current_cost
        self.max_budget = max_budget
        super().__init__(
            f"Orçamento excedido: ${current_cost:.4f} / ${max_budget:.2f}. "
            f"Aumente MAX_BUDGET_USD no .env ou inicie uma nova sessão."
        )


class MaxTurnsExceededError(DataAgentsError):
    """Número máximo de turnos da sessão foi atingido."""

    def __init__(self, max_turns: int):
        self.max_turns = max_turns
        super().__init__(
            f"Limite de {max_turns} turnos atingido. "
            f"Aumente MAX_TURNS no .env ou inicie uma nova sessão."
        )


# ─── Segurança ───────────────────────────────────────────────────


class SecurityViolationError(DataAgentsError):
    """Comando ou operação bloqueada pelo hook de segurança."""

    def __init__(self, command: str, pattern: str):
        self.command = command
        self.pattern = pattern
        super().__init__(
            f"Operação bloqueada por política de segurança. Padrão detectado: '{pattern}'."
        )


# ─── Skills & Configuração ───────────────────────────────────────


class SkillNotFoundError(DataAgentsError):
    """Arquivo de skill referenciado não encontrado."""

    def __init__(self, skill_path: str):
        self.skill_path = skill_path
        super().__init__(
            f"Skill não encontrada: {skill_path}. "
            f"Verifique se o arquivo existe no diretório skills/."
        )


class ConfigurationError(DataAgentsError):
    """Erro de configuração do sistema (settings, environment)."""

    def __init__(self, message: str = ""):
        super().__init__(f"Erro de configuração: {message}")
