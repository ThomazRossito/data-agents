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
import urllib.request

from memory.store import MemoryStore
from memory.types import Memory, MemoryType
from config.settings import settings

logger = logging.getLogger("data_agents.memory.retrieval")

# Modelo para retrieval lateral (Sonnet é o sweet spot custo/qualidade)
_RETRIEVAL_MODEL = "claude-sonnet-4-6"
_RETRIEVAL_MAX_TOKENS = 1024

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
    max_memories: int = 10,
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
    # 1. Carregar index
    index_path = store.data_dir / "index.md"
    if not index_path.exists():
        logger.info("Index não encontrado — gerando...")
        store.build_index()

    if not index_path.exists():
        logger.warning("Nenhuma memória disponível para retrieval.")
        return []

    index_content = index_path.read_text(encoding="utf-8")
    if not index_content.strip() or "**" not in index_content:
        logger.info("Index vazio — sem memórias para retrieval.")
        return []

    # 2. Query ao Sonnet lateral
    selected_ids = _query_sonnet_for_ids(query, index_content)

    if not selected_ids:
        logger.debug(f"Sonnet não selecionou memórias para query: {query[:80]}")
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

    return memories


def _query_sonnet_for_ids(query: str, index_content: str) -> list[str]:
    """
    Faz a chamada lateral ao Sonnet para selecionar IDs relevantes.

    Usa urllib direto (sem dependência do SDK anthropic) — consistente
    com o padrão do _stream_geral no main.py.
    """
    user_message = f"## Query do Usuário\n\n{query}\n\n## Index de Memórias\n\n{index_content}"

    payload = json.dumps(
        {
            "model": _RETRIEVAL_MODEL,
            "max_tokens": _RETRIEVAL_MAX_TOKENS,
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
            ids = json.loads(text)
            if isinstance(ids, list):
                return [str(i) for i in ids]

        logger.warning(f"Resposta do Sonnet não é JSON array válido: {text[:100]}")
        return []

    except Exception as e:
        logger.error(f"Erro no retrieval Sonnet: {e}")
        return []


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
    }

    for mt, mems in by_type.items():
        sections.append(f"\n### {type_labels[mt]}\n")
        for mem in mems:
            conf = f" (confidence: {mem.confidence:.2f})" if mem.confidence < 1.0 else ""
            sections.append(f"**[{mem.id}]** {mem.summary}{conf}\n")
            # Conteúdo truncado para não explodir o contexto
            content = mem.content[:500]
            if len(mem.content) > 500:
                content += "...\n*(conteúdo truncado — leia o arquivo completo se necessário)*"
            sections.append(f"{content}\n")

    return "\n".join(sections)
