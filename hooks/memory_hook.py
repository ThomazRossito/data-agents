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
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("data_agents.memory.hook")

# Buffer de contexto da sessão (acumula entre tool calls)
_session_buffer: list[str] = []
_buffer_char_count: int = 0

# Threshold para flush automático (50K chars ≈ ~12K tokens)
_BUFFER_FLUSH_THRESHOLD = 50_000


def capture_session_context(
    tool_name: str,
    tool_input: dict[str, Any] | None,
    tool_output: str | None,
    hook_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """
    Hook PostToolUse que captura contexto da sessão para o sistema de memória.

    Acumula o contexto no buffer e detecta padrões de captura instantânea.
    NÃO chama LLM — apenas acumula texto para flush posterior.

    Args:
        tool_name: Nome da tool chamada.
        tool_input: Input da tool (JSON).
        tool_output: Output da tool (texto).
        hook_context: Contexto adicional do hook.

    Returns:
        None (hook não modifica o output).
    """
    global _buffer_char_count

    # Ignora tools de infraestrutura (não geram contexto útil)
    skip_tools = {"Glob", "Grep", "Read", "Bash"}
    if tool_name in skip_tools:
        return None

    # Captura contexto relevante
    context_entry = _format_context_entry(tool_name, tool_input, tool_output)
    if context_entry:
        _session_buffer.append(context_entry)
        _buffer_char_count += len(context_entry)

    # Captura instantânea de padrões explícitos (sem LLM)
    if tool_output:
        _check_instant_patterns(tool_output)

    # Flush automático se buffer muito grande
    if _buffer_char_count >= _BUFFER_FLUSH_THRESHOLD:
        logger.info(
            f"Buffer de memória atingiu {_buffer_char_count} chars — "
            f"flush será acionado no próximo checkpoint."
        )

    return None


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


# Padrões de captura instantânea (regex)
_INSTANT_PATTERNS = {
    # Correções do usuário
    r"(?i)(?:não|nao)\s+(?:faça|faca|use|gere|crie)\s+(.+)": "feedback",
    r"(?i)(?:prefiro|prefira|sempre use|use sempre)\s+(.+)": "feedback",
    # Decisões marcadas
    r"(?i)#decision\s*[:\-]?\s*(.+)": "architecture",
    r"(?i)#pattern\s*[:\-]?\s*(.+)": "architecture",
    r"(?i)#gotcha\s*[:\-]?\s*(.+)": "architecture",
}


def _check_instant_patterns(text: str) -> None:
    """
    Verifica padrões de captura instantânea no texto.

    Quando detecta, adiciona uma entrada formatada ao buffer
    com marcador de tipo para que o compiler saiba classificar.
    """
    for pattern, mem_type in _INSTANT_PATTERNS.items():
        matches = re.findall(pattern, text)
        for match in matches:
            entry = (
                f"[INSTANT_CAPTURE] type={mem_type}\n"
                f"  pattern_matched: {pattern}\n"
                f"  content: {match.strip()}"
            )
            _session_buffer.append(entry)
            logger.debug(f"Captura instantânea ({mem_type}): {match.strip()[:80]}")


def get_session_buffer() -> str:
    """Retorna o conteúdo acumulado do buffer da sessão."""
    return "\n\n---\n\n".join(_session_buffer)


def get_buffer_stats() -> dict[str, int]:
    """Retorna estatísticas do buffer."""
    return {
        "entries": len(_session_buffer),
        "total_chars": _buffer_char_count,
        "instant_captures": sum(1 for e in _session_buffer if "[INSTANT_CAPTURE]" in e),
    }


def clear_session_buffer() -> None:
    """Limpa o buffer da sessão (chamado após flush)."""
    global _buffer_char_count
    _session_buffer.clear()
    _buffer_char_count = 0
    logger.debug("Buffer de memória limpo.")


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
