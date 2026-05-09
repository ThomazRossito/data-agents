"""
Memory Hook — Captura automática de memórias durante a sessão.

Hook PostToolUse que monitora a conversa e captura informações relevantes
para o sistema de memória persistente.

Estratégia de captura (para minimizar custo):
  - NÃO chama o extractor a cada tool use (custaria ~$0.01 por tool call)
  - Em vez disso, acumula o contexto da sessão em um buffer
  - O flush é acionado apenas em momentos estratégicos:
    1. Ao final da sessão (session_end)
    2. Quando o buffer atinge um threshold de tamanho
    3. Quando o usuário executa /memory flush
    4. No checkpoint (budget_exceeded, idle_timeout, user_reset)

Além disso, captura instantaneamente (sem Sonnet) padrões simples:
  - Correções explícitas do usuário ("não faça X", "prefiro Y")
  - Decisões arquiteturais marcadas com #decision ou #pattern
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from memory.short_term import ShortTermMemory

logger = logging.getLogger("data_agents.memory.hook")

# ── Estado da sessão ──────────────────────────────────────────────────────────
# Atualizado por init_memory_hook() em session_lifecycle.on_session_start().
# Quando None (antes da init), usa fallback in-memory para compatibilidade.
_short_term: "ShortTermMemory | None" = None
_hook_session_id: str = ""

# Fallback in-memory (usado até init_memory_hook() ser chamado)
_fallback_buffer: list[str] = []
_fallback_char_count: int = 0

# Threshold para flush automático (50K chars ≈ ~12K tokens)
_BUFFER_FLUSH_THRESHOLD = 50_000

# ── Estado para detecção de LESSON_LEARNED triggers ──────────────────────────
# Contagem de ops HIGH na sessão (mcp__databricks__run_job_now etc.)
_session_high_op_count: int = 0
# Contagem de delegações por agente (para detectar retentativas excessivas)
_session_agent_call_count: dict[str, int] = {}
# Tempo de início de cada tool_use_id (para slow_op detection)
_tool_start_times_lesson: dict[str, float] = {}
# Flag para evitar dupla captura de lesson no mesmo tool_use_id
_captured_lessons: set[str] = set()

# Tools classificadas como HIGH (subconjunto de COST_TIERS em cost_guard_hook)
_HIGH_COST_TOOLS = {
    "mcp__databricks__run_job_now",
    "mcp__databricks__start_cluster",
    "mcp__databricks__start_pipeline",
    "mcp__databricks__cancel_run",
}
# Threshold de HIGH ops para disparar o trigger high_cost
_HIGH_COST_THRESHOLD = 5
# Threshold de retentativas por agente para disparar trigger retries
_RETRIES_THRESHOLD = 3
# Threshold de duração (segundos) para disparar trigger slow_op
_SLOW_OP_THRESHOLD_S = 60.0


def reset_lesson_state() -> None:
    """Reseta o estado de detecção de lessons (chamado no início de cada sessão)."""
    global _session_high_op_count, _session_agent_call_count
    global _tool_start_times_lesson, _captured_lessons
    _session_high_op_count = 0
    _session_agent_call_count.clear()
    _tool_start_times_lesson.clear()
    _captured_lessons.clear()


def init_memory_hook(session_id: str, short_term: "ShortTermMemory") -> None:
    """
    Inicializa o hook com a sessão ativa e o buffer SQLite.

    Chamado por session_lifecycle.on_session_start() antes do loop de agente.
    Após a init, capture_session_context() escreve no SQLite (não no fallback).
    """
    global _short_term, _hook_session_id, _fallback_buffer, _fallback_char_count
    _short_term = short_term
    _hook_session_id = session_id
    _fallback_buffer = []
    _fallback_char_count = 0
    reset_lesson_state()
    logger.debug(f"memory_hook inicializado: sessão={session_id!r}, backend=SQLite")


async def capture_session_context(
    input_data: dict[str, Any],
    tool_use_id: str | None,
    context: Any,
) -> dict[str, Any]:
    """
    Hook PostToolUse que captura contexto da sessão para o sistema de memória.

    Acumula o contexto no buffer e detecta padrões de captura instantânea.
    NÃO chama LLM na path principal — apenas acumula texto para flush posterior.
    Quando detecta um trigger de lesson, chama Haiku assíncronamente para capturar.

    Assinatura alinhada com o SDK: (input_data, tool_use_id, context).
    input_data contém: tool_name, tool_input, tool_output.

    Returns:
        {} (hook não modifica o output).
    """
    global _buffer_char_count

    if not input_data or not isinstance(input_data, dict):
        return {}

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input") or {}
    tool_output = input_data.get("tool_output")
    if isinstance(tool_output, dict):
        tool_output = str(tool_output)

    # Normalize tool_use_id — SDK may pass non-str types (e.g. dict) in some versions.
    tool_use_id_safe: str = str(tool_use_id) if tool_use_id is not None else tool_name

    _track_lesson_state(tool_name, tool_input, tool_use_id_safe)

    # Ignora tools de infraestrutura (não geram contexto útil)
    skip_tools = {"Glob", "Grep", "Read", "Bash"}
    if tool_name in skip_tools:
        return {}

    # Captura contexto relevante
    context_entry = _format_context_entry(tool_name, tool_input, tool_output)
    if context_entry:
        if _short_term is not None:
            # Backend SQLite — persistente, sobrevive a crashes
            _short_term.append(context_entry, session_id=_hook_session_id, tool_name=tool_name)
        else:
            # Fallback in-memory (antes de init_memory_hook() ser chamado)
            global _fallback_char_count
            _fallback_buffer.append(context_entry)
            _fallback_char_count += len(context_entry)

    # Captura instantânea de padrões explícitos (sem LLM)
    if tool_output:
        _check_instant_patterns(str(tool_output))

    # Detecção de triggers para LESSON_LEARNED (fire-and-forget assíncrono)
    await _maybe_capture_lesson(
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=str(tool_output) if tool_output else "",
        tool_use_id=tool_use_id_safe,
        input_data=input_data,
    )

    # Aviso de flush automático (threshold baseado no backend ativo)
    char_count = (
        _short_term.get_stats(_hook_session_id).get("active", 0) * 200  # estimativa
        if _short_term is not None
        else _fallback_char_count
    )
    if char_count >= _BUFFER_FLUSH_THRESHOLD:
        logger.info(
            "Buffer de memória atingiu threshold — flush será acionado no próximo checkpoint."
        )

    return {}


def _format_context_entry(
    tool_name: str,
    tool_input: dict[str, Any] | None,
    tool_output: str | None,
) -> str:
    """Formata uma entrada de contexto para o buffer."""
    parts: list[str] = []

    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    parts.append(f"[{timestamp}] Tool: {tool_name}")

    # Extrai informação relevante do input
    if tool_input:
        if tool_name == "Agent":
            # Para delegações, captura o agente e o prompt
            agent = tool_input.get("agent_name", tool_input.get("name", ""))
            prompt = tool_input.get("prompt", "")[:200]
            if agent:
                parts.append(f"  Delegado para: {agent}")
            if prompt:
                parts.append(f"  Prompt: {prompt}")

        elif tool_name == "Write":
            path = tool_input.get("file_path", "")
            parts.append(f"  Arquivo: {path}")

        elif tool_name == "AskUserQuestion":
            question = tool_input.get("question", "")
            parts.append(f"  Pergunta: {question}")

    # Output truncado
    if tool_output and len(tool_output) > 0:
        output_preview = tool_output[:300].replace("\n", " ")
        parts.append(f"  Output: {output_preview}")

    return "\n".join(parts)


# ── Lesson Learned trigger detection ─────────────────────────────────────────

_ERROR_INDICATORS = ["error", "failed", "exception", "traceback", "unauthorized", "timeout"]


async def pre_track_lesson_timing(
    tool_name: str, tool_input: dict[str, Any], tool_use_id: str | None
) -> dict[str, Any]:
    """PreToolUse: registra o instante de início de cada tool call para slow_op detection."""
    global _tool_start_times_lesson

    # Normalize to str — SDK may pass non-str types in some runtime versions.
    tid = str(tool_use_id) if tool_use_id is not None else tool_name
    _tool_start_times_lesson[tid] = time.monotonic()
    return {}


def _track_lesson_state(
    tool_name: str, tool_input: dict[str, Any], tool_use_id: str | None
) -> None:
    """Atualiza contadores de sessão usados para triggers de LESSON_LEARNED."""
    global _session_high_op_count, _session_agent_call_count

    if tool_name in _HIGH_COST_TOOLS:
        _session_high_op_count += 1

    if tool_name == "Agent":
        agent = (
            tool_input.get("subagent_type")
            or tool_input.get("agent_name")
            or tool_input.get("name")
            or "unknown"
        )
        _session_agent_call_count[agent] = _session_agent_call_count.get(agent, 0) + 1


def _detect_lesson_triggers(
    tool_name: str,
    tool_output: str,
    tool_error: str,
    tool_use_id: str,
) -> list[str]:
    """
    Detecta triggers para captura de LESSON_LEARNED.

    Returns: lista de triggers detectados (pode ser vazia ou ter múltiplos).
    """
    triggers: list[str] = []

    # Trigger 1: erro em tool MCP
    # Combina tool_error + tool_output: "Table not found" está no tool_error
    # mas "AnalysisException" pode estar só no tool_output — verificar ambos.
    if tool_name.startswith("mcp__"):
        error_text = " ".join(filter(None, [tool_error, tool_output]))
        if error_text and any(kw in error_text.lower() for kw in _ERROR_INDICATORS):
            triggers.append("error")

    # Trigger 2: acúmulo de HIGH ops na sessão (threshold configurável)
    if _session_high_op_count >= _HIGH_COST_THRESHOLD and tool_name in _HIGH_COST_TOOLS:
        triggers.append("high_cost")

    # Trigger 3: retentativas excessivas (mesmo agente chamado N+ vezes)
    if tool_name == "Agent":
        for agent, count in _session_agent_call_count.items():
            if count > _RETRIES_THRESHOLD:
                triggers.append("retries")
                break

    # Trigger 4: operação lenta
    start = _tool_start_times_lesson.get(str(tool_use_id))
    if start is not None:
        duration = time.monotonic() - start
        if duration >= _SLOW_OP_THRESHOLD_S and tool_name.startswith("mcp__"):
            triggers.append("slow_op")

    return triggers


def _extract_agent_from_tool_input(tool_input: dict[str, Any]) -> str:
    """Extrai o nome do agente do input do tool Agent."""
    return (
        tool_input.get("subagent_type")
        or tool_input.get("agent_name")
        or tool_input.get("name")
        or "unknown"
    )


async def _maybe_capture_lesson(
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: str,
    tool_use_id: str,
    input_data: dict[str, Any],
) -> None:
    """
    Verifica se algum trigger está ativo e captura LESSON_LEARNED diretamente.

    Fire-and-forget: erros são logados mas não propagados para não bloquear a pipeline.
    Usa Haiku para sumarização (~$0.001 por lesson).
    """
    from config.settings import settings

    if not settings.memory_enabled or not settings.memory_capture_enabled:
        return

    # Evita dupla captura para o mesmo evento
    if tool_use_id in _captured_lessons:
        return

    tool_error = str(input_data.get("tool_error", "") or "")
    triggers = _detect_lesson_triggers(tool_name, tool_output, tool_error, tool_use_id)

    if not triggers:
        return

    trigger = triggers[0]  # captura o trigger mais prioritário
    _captured_lessons.add(tool_use_id)

    # Determina o agente envolvido
    if tool_name == "Agent":
        agent = _extract_agent_from_tool_input(tool_input)
    else:
        # Tenta inferir do nome da tool (ex: mcp__databricks__run_job → databricks-engineer)
        if "databricks" in tool_name:
            agent = "databricks-engineer"
        elif "fabric_rti" in tool_name:
            agent = "fabric-rti"
        elif "fabric" in tool_name:
            agent = "fabric-engineer"
        else:
            agent = "unknown"

    error_text = tool_error or tool_output[:300]
    context_snippet = get_session_buffer()[:400] if trigger != "error" else ""

    try:
        from utils.summarizer import summarize_lesson
        from memory.store import MemoryStore
        from memory.types import Memory, MemoryType

        result = await summarize_lesson(
            agent=agent,
            trigger=trigger,
            tool_name=tool_name,
            error_text=error_text,
            context_snippet=context_snippet,
        )

        store = MemoryStore()

        # Extrair task_type do nome da tool (ex: run_job_now → run_job)
        task_type = tool_name.split("__")[-1] if "__" in tool_name else tool_name

        lesson = Memory(
            type=MemoryType.LESSON_LEARNED,
            content=result["content"],
            summary=result["summary"],
            tags=[agent, trigger, task_type, "lesson_learned"],
            confidence=1.0,
            source_session=_hook_session_id,
            metadata={
                "agent": agent,
                "trigger": trigger,
                "task_type": task_type,
                "tool_name": tool_name,
                "platform": tool_name.split("__")[1] if tool_name.startswith("mcp__") else "local",
                "cost_usd": result.get("cost_usd", 0.0),
            },
        )
        store.save(lesson)

        # Poda se exceder o limite por agente
        store.prune_lessons_by_agent(agent_name=agent)

        logger.info(
            f"LESSON_LEARNED capturada: agent={agent} trigger={trigger} "
            f"tool={tool_name} id={lesson.id}"
        )

    except Exception as e:
        logger.warning(f"Falha ao capturar LESSON_LEARNED (ignorado): {e}")


# Padrões default de captura instantânea
_DEFAULT_INSTANT_PATTERNS: dict[str, str] = {
    # Correções do usuário
    r"(?i)(?:não|nao)\s+(?:faça|faca|use|gere|crie)\s+(.+)": "feedback",
    r"(?i)(?:prefiro|prefira|sempre use|use sempre)\s+(.+)": "feedback",
    # Decisões marcadas
    r"(?i)#decision\s*[:\-]?\s*(.+)": "architecture",
    r"(?i)#pattern\s*[:\-]?\s*(.+)": "architecture",
    r"(?i)#gotcha\s*[:\-]?\s*(.+)": "architecture",
}


def _get_instant_patterns() -> dict[str, str]:
    """Retorna padrões de captura configurados via settings (com fallback para defaults)."""
    from config.settings import settings  # importação local — evita circular

    if not settings.memory_instant_patterns:
        return _DEFAULT_INSTANT_PATTERNS

    patterns: dict[str, str] = dict(_DEFAULT_INSTANT_PATTERNS)
    for entry in settings.memory_instant_patterns:
        if "::" in entry:
            pattern, mem_type = entry.rsplit("::", 1)
            patterns[pattern.strip()] = mem_type.strip()
    return patterns


def _check_instant_patterns(text: str) -> None:
    """
    Verifica padrões de captura instantânea no texto.

    Quando detecta, adiciona uma entrada formatada ao buffer
    com marcador de tipo para que o compiler saiba classificar.
    Limita a settings.memory_max_captures_per_output por chamada para evitar buffer bloat.
    """
    from config.settings import settings

    max_captures = settings.memory_max_captures_per_output
    capture_count = 0

    for pattern, mem_type in _get_instant_patterns().items():
        if capture_count >= max_captures:
            logger.debug(
                f"Limite de capturas instantâneas atingido ({max_captures}) — ignorando restantes."
            )
            break
        matches = re.findall(pattern, text)
        for match in matches:
            if capture_count >= max_captures:
                break
            entry = (
                f"[INSTANT_CAPTURE] type={mem_type}\n"
                f"  pattern_matched: {pattern}\n"
                f"  content: {match.strip()}"
            )
            if _short_term is not None:
                _short_term.append(entry, session_id=_hook_session_id, tool_name="instant_capture")
            else:
                _fallback_buffer.append(entry)
                global _fallback_char_count
                _fallback_char_count += len(entry)
            capture_count += 1
            logger.debug(f"Captura instantânea ({mem_type}): {match.strip()[:80]}")


def get_session_buffer() -> str:
    """Retorna o conteúdo acumulado do buffer da sessão."""
    if _short_term is not None:
        return _short_term.get_session_buffer(_hook_session_id)
    return "\n\n---\n\n".join(_fallback_buffer)


def get_buffer_stats() -> dict[str, int]:
    """Retorna estatísticas do buffer."""
    if _short_term is not None:
        stats = _short_term.get_stats(_hook_session_id)
        return {
            "entries": stats.get("active", 0),
            "total_chars": stats.get("active", 0) * 200,  # estimativa
            "instant_captures": 0,
        }
    return {
        "entries": len(_fallback_buffer),
        "total_chars": _fallback_char_count,
        "instant_captures": sum(1 for e in _fallback_buffer if "[INSTANT_CAPTURE]" in e),
    }


def clear_session_buffer() -> None:
    """Limpa o buffer da sessão (chamado após flush). Preserva o SQLite — TTL gerencia expiração."""
    global _fallback_char_count
    _fallback_buffer.clear()
    _fallback_char_count = 0
    logger.debug("Buffer de memória limpo (fallback). SQLite preservado — TTL gerencia expiração.")


def flush_session_memories(session_id: str = "") -> int:
    """
    Processa o buffer da sessão: extrai memórias e salva nos daily logs.

    Este é o ponto de integração entre o hook (captura) e o store (persistência).
    Chamado em momentos estratégicos para minimizar custo.

    Args:
        session_id: Identificador da sessão.

    Returns:
        Número de memórias extraídas e salvas.
    """
    from memory.store import MemoryStore
    from memory.extractor import extract_memories_from_conversation

    buffer_content = get_session_buffer()
    if not buffer_content.strip():
        logger.debug("Buffer vazio — nada para flush.")
        return 0

    stats = get_buffer_stats()
    logger.info(
        f"Flush de memória: {stats['entries']} entradas, "
        f"{stats['total_chars']} chars, "
        f"{stats['instant_captures']} capturas instantâneas"
    )

    store = MemoryStore()

    # Extrai memórias via Sonnet
    existing = store.list_all(active_only=True)
    existing_summaries = [m.summary for m in existing]

    memories = extract_memories_from_conversation(
        conversation_text=buffer_content,
        session_id=session_id,
        existing_summaries=existing_summaries,
    )

    # Salva no daily log (o compiler vai processar depois)
    if memories:
        for mem in memories:
            entry_text = (
                f"type: {mem.type.value}\n"
                f"summary: {mem.summary}\n"
                f"tags: {', '.join(mem.tags)}\n"
                f"source_session: {session_id}\n"
                f"confidence: {mem.confidence}\n\n"
                f"{mem.content}"
            )
            store.append_daily_log(entry_text)

        logger.info(f"Flush: {len(memories)} memórias salvas no daily log.")

    # Limpa o buffer
    clear_session_buffer()

    return len(memories)
