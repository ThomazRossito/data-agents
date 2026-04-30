"""
Memory Retrieval — Busca de memórias relevantes via Sonnet lateral.

Em vez de embeddings + busca vetorial, usa uma chamada LLM lateral (Sonnet)
para selecionar memórias relevantes a partir do index.md.

Por que Sonnet lateral supera embeddings em escala pessoal (~50-500 memórias):
  1. Entende relações semânticas profundas ("deployment" ↔ "CI/CD")
  2. Pode considerar o CONTEXTO da query, não apenas similaridade lexical
  3. Não requer infraestrutura de vector DB
  4. Custo ~$0.003-0.01 por query — viável para uso interativo

Fluxo:
  1. Carrega o index.md (resumos compactos de todas as memórias ativas)
  2. Envia ao Sonnet: "Dada esta query, quais memórias são relevantes?"
  3. Sonnet retorna IDs das memórias selecionadas
  4. Carrega o conteúdo completo das memórias selecionadas
  5. Retorna contexto formatado para injeção no prompt do supervisor
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

from memory.store import MemoryStore
from memory.telemetry import record as _telemetry
from memory.types import Memory, MemoryType
from config.settings import settings

logger = logging.getLogger("data_agents.memory.retrieval")

# Contador de falhas consecutivas para throttling adaptativo
# Se >= _MAX_CONSECUTIVE_FAILURES, pula retrieval e loga warning
_consecutive_failures: int = 0
_MAX_CONSECUTIVE_FAILURES = 5

# Modelo e limites lidos de settings para permitir override via .env

_RETRIEVAL_SYSTEM_PROMPT = """\
Você é um sistema de retrieval de memórias. Sua tarefa é selecionar as memórias mais
relevantes para responder à query do usuário.

Você receberá:
1. Uma query (a pergunta ou tarefa atual do usuário)
2. Um index de memórias (resumos compactos com IDs)

Retorne APENAS um JSON array com os IDs das memórias relevantes, ordenados por relevância.
Selecione entre 0 e 10 memórias. Selecione 0 se nenhuma memória for relevante.

Critérios de relevância:
- A memória fornece contexto direto para a tarefa
- A memória contém decisões ou padrões aplicáveis
- A memória registra feedback do usuário sobre tema similar
- A memória documenta preferências relevantes do usuário

NÃO selecione memórias apenas por terem palavras similares — considere a INTENÇÃO da query.

Responda SOMENTE com o JSON array, sem markdown, sem explicação.
Exemplo: ["abc123", "def456"]
"""


def retrieve_relevant_memories(
    query: str,
    store: MemoryStore,
    max_memories: int | None = None,
    include_types: list[MemoryType] | None = None,
) -> list[Memory]:
    """
    Busca memórias relevantes usando Sonnet lateral.

    Args:
        query: A query/tarefa atual do usuário.
        store: MemoryStore com as memórias persistidas.
        max_memories: Máximo de memórias a retornar.
        include_types: Se fornecido, filtra por tipos. None = todos.

    Returns:
        Lista de Memory objects relevantes, com conteúdo completo.
    """
    if max_memories is None:
        max_memories = settings.memory_retrieval_max

    t0 = time.time()

    # 1. Carregar index
    index_path = store.data_dir / "index.md"
    if not index_path.exists():
        logger.info("Index não encontrado — gerando...")
        store.build_index()

    if not index_path.exists():
        logger.warning("Nenhuma memória disponível para retrieval.")
        _telemetry(
            "retrieval.query",
            reason="no_index",
            selected=0,
            loaded=0,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return []

    index_content = index_path.read_text(encoding="utf-8")
    if not index_content.strip() or "**" not in index_content:
        logger.info("Index vazio — sem memórias para retrieval.")
        _telemetry(
            "retrieval.query",
            reason="empty_index",
            selected=0,
            loaded=0,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return []

    # 2. Query ao Sonnet lateral
    selected_ids, cost_usd = _query_sonnet_for_ids(query, index_content)

    if not selected_ids:
        logger.debug(f"Sonnet não selecionou memórias para query: {query[:80]}")
        _telemetry(
            "retrieval.query",
            reason="no_selection",
            selected=0,
            loaded=0,
            cost_usd=cost_usd,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return []

    # 3. Carregar memórias completas
    memories: list[Memory] = []
    for mem_id in selected_ids[:max_memories]:
        # Tenta carregar de cada tipo (o ID é único globalmente)
        types_to_search = include_types or list(MemoryType)
        for mt in types_to_search:
            mem = store.load(mem_id, mt)
            if mem and mem.is_active():
                memories.append(mem)
                break

    logger.info(
        f"Retrieval: query='{query[:60]}' → {len(selected_ids)} selecionadas, "
        f"{len(memories)} carregadas"
    )
    _telemetry(
        "retrieval.query",
        reason="ok",
        selected=len(selected_ids),
        loaded=len(memories),
        cost_usd=cost_usd,
        duration_ms=int((time.time() - t0) * 1000),
    )

    return memories


def _query_sonnet_for_ids(query: str, index_content: str) -> tuple[list[str], float]:
    """
    Faz a chamada lateral ao Sonnet para selecionar IDs relevantes.

    Inclui retry com backoff exponencial (3 tentativas) para erros 429/5xx.
    Implementa throttling adaptativo: após _MAX_CONSECUTIVE_FAILURES falhas
    consecutivas, pula o retrieval e emite warning até o próximo sucesso.

    Usa urllib direto (sem dependência do SDK anthropic) — consistente
    com o padrão do _stream_geral no main.py.
    """
    global _consecutive_failures

    if _consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
        logger.warning(
            f"Memory retrieval desabilitado temporariamente após {_consecutive_failures} "
            "falhas consecutivas. Será reativado no próximo sucesso."
        )
        return [], 0.0

    user_message = f"## Query do Usuário\n\n{query}\n\n## Index de Memórias\n\n{index_content}"

    payload = json.dumps(
        {
            "model": settings.memory_retrieval_model,
            "max_tokens": settings.memory_retrieval_max_tokens,
            "system": _RETRIEVAL_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "data-agents/1.0 memory-retrieval",
        },
        method="POST",
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
                data = json.loads(resp.read().decode("utf-8"))

            text = data["content"][0]["text"] if data.get("content") else "[]"

            # Parse custo para logging
            usage = data.get("usage", {})
            input_tok = usage.get("input_tokens", 0)
            output_tok = usage.get("output_tokens", 0)
            cost = (input_tok * 3.00 + output_tok * 15.00) / 1_000_000
            logger.debug(f"Retrieval Sonnet: {input_tok} in / {output_tok} out = ${cost:.5f}")

            # Extrair JSON array da resposta
            text = text.strip()
            if text.startswith("["):
                try:
                    ids = json.loads(text)
                    if isinstance(ids, list):
                        _consecutive_failures = 0  # reset ao primeiro sucesso
                        return [str(i) for i in ids], cost
                except json.JSONDecodeError:
                    pass

            logger.warning(f"Resposta do Sonnet não é JSON array válido: {text[:100]}")
            _consecutive_failures = 0
            return [], cost

        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2**attempt
                logger.warning(
                    f"Rate limit no retrieval (429) — aguardando {wait}s (tentativa {attempt + 1}/{max_retries})"
                )
                time.sleep(wait)
                continue
            _consecutive_failures += 1
            logger.error(
                f"Erro HTTP no retrieval Sonnet: {e.code} {e.reason} — falhas consecutivas: {_consecutive_failures}"
            )
            return [], 0.0
        except Exception as e:
            _consecutive_failures += 1
            logger.error(
                f"Erro no retrieval Sonnet: {e} — falhas consecutivas: {_consecutive_failures}"
            )
            return [], 0.0

    return [], 0.0


def format_memories_for_injection(memories: list[Memory]) -> str:
    """
    Formata memórias recuperadas para injeção no prompt do supervisor.

    Formato otimizado para contexto: compacto mas informativo.
    """
    if not memories:
        return ""

    sections: list[str] = [
        "\n\n---\n\n"
        "## [Contexto Injetado] Memórias Relevantes da Sessão\n\n"
        "As memórias abaixo foram recuperadas automaticamente como contexto "
        "relevante para a tarefa atual. Use-as para informar suas decisões.\n"
    ]

    # Agrupa por tipo para melhor legibilidade
    by_type: dict[MemoryType, list[Memory]] = {}
    for mem in memories:
        by_type.setdefault(mem.type, []).append(mem)

    type_labels = {
        MemoryType.USER: "Preferências do Usuário",
        MemoryType.FEEDBACK: "Feedback & Correções",
        MemoryType.ARCHITECTURE: "Decisões Arquiteturais",
        MemoryType.PROGRESS: "Progresso & Contexto",
        MemoryType.DATA_ASSET: "Assets de Dados",
        MemoryType.PLATFORM_DECISION: "Decisões de Plataforma",
        MemoryType.PIPELINE_STATUS: "Status de Pipelines",
    }

    for mt, mems in by_type.items():
        label = type_labels.get(mt, mt.value.replace("_", " ").title())
        sections.append(f"\n### {label}\n")
        for mem in mems:
            conf = f" (confidence: {mem.confidence:.2f})" if mem.confidence < 1.0 else ""
            sections.append(f"**[{mem.id}]** {mem.summary}{conf}\n")
            # Conteúdo truncado para não explodir o contexto
            content = mem.content[:500]
            if len(mem.content) > 500:
                content += "...\n*(conteúdo truncado — leia o arquivo completo se necessário)*"
            sections.append(f"{content}\n")

    return "\n".join(sections)
