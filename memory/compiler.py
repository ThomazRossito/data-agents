"""
Memory Compiler — Transforma daily logs em knowledge articles.

O compiler processa os daily logs brutos (gerados pelo extractor/hook)
e organiza em memórias estruturadas no store.

Pipeline:
  daily/{YYYY-MM-DD}.md → parse → dedup → Memory objects → store.save()

O compiler também:
  - Detecta contradições com memórias existentes e faz supersede
  - Cruza referências entre memórias relacionadas
  - Gera novo index.md após compilação
  - Marca daily logs como processados (<!-- COMPILED -->)
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.store import MemoryStore
from memory.telemetry import record as _telemetry
from memory.types import Memory, MemoryType
from memory.decay import apply_decay
from config.settings import settings

logger = logging.getLogger("data_agents.memory.compiler")

# ── Configuração Sonnet para detecção de contradições ─────────────────────────
_CONTRADICTION_MODEL = "claude-sonnet-4-6"
_CONTRADICTION_MAX_TOKENS = 256

_CONTRADICTION_SYSTEM = """\
Você é um detector de contradições em uma base de conhecimento.
Sua tarefa é determinar se uma NOVA memória contradiz uma memória EXISTENTE.

Uma contradição ocorre quando as duas memórias fazem afirmações INCOMPATÍVEIS sobre o MESMO assunto.

Exemplos de contradição:
- Existente: "O pipeline usa Auto Loader para ingestão"  vs  Nova: "O pipeline usa COPY INTO, não Auto Loader"
- Existente: "Usuário prefere respostas curtas e diretas"  vs  Nova: "Usuário prefere respostas detalhadas com exemplos"
- Existente: "A camada Bronze usa formato Parquet"  vs  Nova: "A camada Bronze usa formato Delta"

NÃO é contradição:
- Informações complementares sobre assuntos diferentes
- Uma memória mais detalhada que expande (sem negar) a anterior
- Memórias sobre aspectos distintos do mesmo sistema

Responda SOMENTE com JSON, sem markdown, sem explicação adicional:
{"is_contradiction": true|false, "confidence": 0.0-1.0, "reason": "explicação em uma linha"}
"""


def compile_daily_logs(
    store: MemoryStore,
    apply_decay_on_compile: bool = True,
    use_sonnet_contradiction: bool = True,
) -> dict[str, int]:
    """
    Processa todos os daily logs não compilados e cria memórias no store.

    Args:
        store: MemoryStore para salvar as memórias compiladas.
        apply_decay_on_compile: Se True, aplica decay em todas as memórias
            existentes durante a compilação.
        use_sonnet_contradiction: Se True, usa Sonnet para confirmar contradições
            (mais preciso). Se False, usa apenas heurística word-overlap (sem custo).

    Returns:
        Dict com métricas: {"processed_logs": N, "new_memories": M,
                            "superseded": K, "skipped_dupes": D,
                            "contradiction_checks": C}
    """
    metrics = {
        "processed_logs": 0,
        "new_memories": 0,
        "superseded": 0,
        "skipped_dupes": 0,
        "contradiction_checks": 0,
        "cleaned_logs": 0,
        "lessons_deduped": 0,
    }

    # 1. Listar daily logs não processados
    unprocessed = store.list_daily_logs(unprocessed_only=True)
    if not unprocessed:
        logger.info("Nenhum daily log para compilar.")
        return metrics

    logger.info(f"Compilando {len(unprocessed)} daily logs...")

    # 2. Carregar resumos existentes para dedup
    existing_memories = store.list_all(active_only=True)
    existing_summaries = {m.normalized_summary for m in existing_memories}

    # 3. Processar cada daily log
    for log_path in unprocessed:
        try:
            raw_content = log_path.read_text(encoding="utf-8")
            entries = _parse_daily_entries(raw_content)

            for entry in entries:
                memory = _entry_to_memory(entry)
                if memory is None:
                    continue

                # Dedup: pula se resumo já existe
                if memory.normalized_summary in existing_summaries:
                    metrics["skipped_dupes"] += 1
                    continue

                # Detecta contradições e faz supersede
                contradiction = _find_contradiction(
                    memory, existing_memories, use_sonnet=use_sonnet_contradiction
                )
                if contradiction:
                    metrics["contradiction_checks"] += 1
                    store.supersede(contradiction.id, contradiction.type, memory)
                    metrics["superseded"] += 1
                    # Remove da lista de existentes e adiciona nova
                    existing_memories = [m for m in existing_memories if m.id != contradiction.id]
                else:
                    store.save(memory)
                    metrics["new_memories"] += 1

                existing_memories.append(memory)
                existing_summaries.add(memory.normalized_summary)

            # Marcar como compilado
            _mark_as_compiled(log_path)
            metrics["processed_logs"] += 1

        except Exception as e:
            logger.error(f"Erro ao compilar {log_path.name}: {e}")

    # 4. Aplicar decay se configurado
    if apply_decay_on_compile:
        all_memories = store.list_all(active_only=False)
        apply_decay(all_memories, save_fn=store.save)

    # 5. Deduplicar LESSON_LEARNED (merge de lessons similares por agente)
    dedup_metrics = deduplicate_lessons(store)
    metrics["lessons_deduped"] = dedup_metrics.get("merged", 0)

    # 6. Regenerar index
    store.build_index()

    # 7. Limpeza de daily logs compilados antigos (se habilitado via settings)
    cleaned = _cleanup_compiled_logs(store)
    if cleaned:
        metrics["cleaned_logs"] = cleaned
        logger.info(f"Limpeza: {cleaned} daily logs compilados antigos removidos.")
    else:
        metrics["cleaned_logs"] = 0

    logger.info(
        f"Compilação concluída: {metrics['processed_logs']} logs, "
        f"{metrics['new_memories']} novas, {metrics['superseded']} substituídas, "
        f"{metrics['skipped_dupes']} dupes ignoradas, {metrics['cleaned_logs']} logs limpos"
    )

    return metrics


def _parse_daily_entries(content: str) -> list[dict[str, Any]]:
    """
    Parseia um daily log em entradas individuais.

    Cada entrada é separada por --- e pode conter frontmatter YAML simples.
    """
    entries: list[dict[str, Any]] = []

    # Divide por separador ---
    sections = re.split(r"\n---\n", content)

    for section in sections:
        section = section.strip()
        if not section or section.startswith("# Daily Log"):
            continue

        # Tenta parsear como frontmatter + body
        entry = _parse_entry_section(section)
        if entry:
            entries.append(entry)

    return entries


def _parse_entry_section(section: str) -> dict[str, Any] | None:
    """Parseia uma seção individual do daily log.

    Formato esperado (produzido pelo memory_hook e extractor)::

        type_field: architecture
        summary: Pipeline usa Auto Loader
        tags: pipeline, bronze

        Conteúdo da memória...

    Ou formato livre (adicionado manualmente) sem frontmatter.
    """

    frontmatter_match = re.match(r"^((?:\w+:.*\n)+)\n*(.*)", section, re.DOTALL)

    if frontmatter_match:
        yaml_part = frontmatter_match.group(1)
        body = frontmatter_match.group(2).strip()

        metadata: dict[str, Any] = {}
        for line in yaml_part.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                if key == "tags":
                    metadata[key] = [t.strip() for t in value.split(",") if t.strip()]
                elif key == "confidence" and value:
                    try:
                        metadata[key] = float(value)
                    except ValueError:
                        pass
                else:
                    metadata[key] = value

        metadata["content"] = body
        return metadata if metadata.get("type") and metadata.get("summary") else None

    return None


def _entry_to_memory(entry: dict[str, Any]) -> Memory | None:
    """Converte um dict de entrada para Memory."""
    try:
        mem_type = MemoryType(entry.get("type", "progress"))
    except ValueError:
        return None

    return Memory(
        type=mem_type,
        content=entry.get("content", ""),
        summary=entry.get("summary", ""),
        tags=entry.get("tags", []),
        confidence=float(entry.get("confidence", 1.0)),
        source_session=entry.get("source_session", ""),
    )


def _find_contradiction(
    new_memory: Memory,
    existing: list[Memory],
    use_sonnet: bool = True,
) -> Memory | None:
    """
    Detecta se uma nova memória contradiz uma existente.

    Estratégia em duas etapas:
      1. Pré-filtro barato (sem LLM): mesmo tipo + pelo menos 1 tag em comum.
         Reduz o conjunto de candidatos antes de chamar o Sonnet.
      2. Confirmação via Sonnet (se use_sonnet=True): verifica semântica real.
         Fallback para heurística word-overlap se a chamada falhar.

    Args:
        new_memory: Memória recém-extraída do daily log.
        existing: Lista de memórias ativas no store.
        use_sonnet: Se True, usa Sonnet para confirmação (padrão). Se False,
            usa apenas heurística (sem custo, menos preciso).

    Returns:
        A memória existente que deve ser superseded, ou None.
    """
    candidates = _filter_contradiction_candidates(new_memory, existing)
    if not candidates:
        return None

    for candidate in candidates:
        if use_sonnet:
            is_contra = _sonnet_check_contradiction(new_memory, candidate)
        else:
            is_contra = _heuristic_contradiction(new_memory, candidate)

        if is_contra:
            return candidate

    return None


def _filter_contradiction_candidates(
    new_memory: Memory,
    existing: list[Memory],
) -> list[Memory]:
    """
    Pré-filtro rápido: retorna candidatos a contradição sem chamar LLM.

    Critérios (ambos necessários):
      - Mesmo tipo de memória (USER, ARCHITECTURE, etc.)
      - Pelo menos 1 tag em comum (mesmo domínio de assunto)

    A intenção é reduzir o espaço de candidatos antes do Sonnet.
    É propositalmente generoso (1 tag basta) — o Sonnet confirma a seguir.
    """
    if not new_memory.tags:
        # Sem tags: compara apenas pelo tipo e verifica sobreposição de palavras-chave
        stopwords = {"o", "a", "e", "de", "do", "da", "em", "para", "com", "que", "os", "as"}
        new_kw = {
            w for w in new_memory.summary.lower().split() if w not in stopwords and len(w) > 3
        }
        candidates = []
        for mem in existing:
            if mem.type != new_memory.type or not mem.is_active():
                continue
            existing_kw = {
                w for w in mem.summary.lower().split() if w not in stopwords and len(w) > 3
            }
            if len(new_kw & existing_kw) >= 2:
                candidates.append(mem)
        return candidates

    new_tags = set(new_memory.tags)
    candidates = []
    for mem in existing:
        if mem.type != new_memory.type:
            continue
        if not mem.is_active():
            continue
        if new_tags & set(mem.tags):  # pelo menos 1 tag em comum
            candidates.append(mem)
    return candidates


def _sonnet_check_contradiction(new_memory: Memory, candidate: Memory) -> bool:
    """
    Usa Sonnet para determinar se duas memórias são contraditórias.

    Retorna True se Sonnet confirmar contradição com confidence >= 0.7.
    Em caso de erro na chamada API, faz fallback para a heurística.

    Custo típico: ~$0.003–0.006 por par verificado
    (input ~400 tokens + output ~60 tokens @ claude-sonnet-4-6)
    """
    user_message = (
        f"## Memória EXISTENTE\n"
        f"Tipo: {candidate.type.value}\n"
        f"Resumo: {candidate.summary}\n"
        f"Tags: {', '.join(candidate.tags)}\n"
        f"Conteúdo: {candidate.content[:400]}\n\n"
        f"## Memória NOVA\n"
        f"Tipo: {new_memory.type.value}\n"
        f"Resumo: {new_memory.summary}\n"
        f"Tags: {', '.join(new_memory.tags)}\n"
        f"Conteúdo: {new_memory.content[:400]}\n\n"
        f"Essas duas memórias se contradizem?"
    )

    payload = json.dumps(
        {
            "model": _CONTRADICTION_MODEL,
            "max_tokens": _CONTRADICTION_MAX_TOKENS,
            "system": _CONTRADICTION_SYSTEM,
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
            "User-Agent": "data-agents/1.0 memory-contradiction",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        text = (data.get("content") or [{}])[0].get("text", "").strip()

        # Remove eventuais code fences da resposta
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())

        result = json.loads(text)
        is_contra: bool = bool(result.get("is_contradiction", False))
        confidence: float = float(result.get("confidence", 0.0))
        reason: str = result.get("reason", "")

        usage = data.get("usage", {})
        cost = (
            usage.get("input_tokens", 0) * 3.00 + usage.get("output_tokens", 0) * 15.00
        ) / 1_000_000

        logger.debug(
            f"Sonnet contradiction check: {candidate.id[:8]} ↔ {new_memory.id[:8]} "
            f"→ {is_contra} (conf={confidence:.2f}) — {reason[:80]}  [${cost:.5f}]"
        )
        _telemetry(
            "compiler.contradiction_check",
            is_contradiction=is_contra,
            confidence=confidence,
            cost_usd=cost,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )

        return is_contra and confidence >= 0.7

    except Exception as e:
        logger.warning(
            f"Sonnet contradiction check falhou ({candidate.id[:8]} ↔ {new_memory.id[:8]}): {e}. "
            f"Usando fallback heurístico."
        )
        return _heuristic_contradiction(new_memory, candidate)


def _heuristic_contradiction(new_memory: Memory, candidate: Memory) -> bool:
    """
    Fallback: heurística word-overlap para detecção de contradição.

    Usada quando Sonnet não está disponível (sem API key, timeout, etc.)
    ou quando use_sonnet=False.

    Critério: >50% das palavras significativas do summary coincidem
    (indica que tratam do mesmo assunto específico).
    """
    new_words = set(new_memory.summary.lower().split())
    existing_words = set(candidate.summary.lower().split())
    word_overlap = new_words & existing_words
    min_len = min(len(new_words), len(existing_words))
    return min_len > 0 and len(word_overlap) / min_len > 0.5


def _cleanup_compiled_logs(store: MemoryStore) -> int:
    """
    Remove daily logs compilados com mais de N dias (configurável via settings).

    Logs compilados já tiveram seu conteúdo extraído para o store — o arquivo
    bruto é redundante e apenas acumula disco.

    Retorna o número de arquivos removidos.
    """
    from config.settings import settings  # importação local — evita circular import

    if not settings.memory_auto_clean_daily_logs:
        return 0

    keep_days = settings.memory_keep_compiled_days
    now = datetime.now(timezone.utc)
    removed = 0

    all_logs = store.list_daily_logs(unprocessed_only=False)

    for log_path in all_logs:
        # Só remove logs com marcador COMPILED
        try:
            content = log_path.read_text(encoding="utf-8")
        except OSError:
            continue

        if "<!-- COMPILED" not in content:
            continue  # Não compilado — não remove

        # Extrai data do nome do arquivo (YYYY-MM-DD.md)
        try:
            date_str = log_path.stem  # ex: "2026-03-15"
            log_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # Nome inesperado — não remove

        age_days = (now - log_date).days
        if age_days >= keep_days:
            try:
                log_path.unlink()
                removed += 1
                logger.debug(f"Daily log antigo removido: {log_path.name} ({age_days} dias)")
            except OSError as e:
                logger.warning(f"Erro ao remover {log_path.name}: {e}")

    return removed


def deduplicate_lessons(store: MemoryStore) -> dict[str, int]:
    """
    Deduplicação de LESSON_LEARNED por chave composta (agent + task_type + erro similar).

    Para cada par de lessons com a mesma chave (agent + task_type) e summary com
    sobreposição > 60%, consolida em uma única: incrementa confidence da mais recente
    e marca a mais antiga como superseded.

    Returns:
        Dict com métricas: {"merged": N, "unchanged": M}
    """
    from memory.types import MemoryType

    metrics = {"merged": 0, "unchanged": 0}

    lessons = store.list_all(memory_type=MemoryType.LESSON_LEARNED, active_only=True)
    if len(lessons) < 2:
        return metrics

    # Agrupa por (agent, task_type)
    groups: dict[tuple[str, str], list] = {}
    for lesson in lessons:
        agent = lesson.metadata.get("agent", "")
        task_type = lesson.metadata.get("task_type", "")
        key = (agent, task_type)
        groups.setdefault(key, []).append(lesson)

    # Dentro de cada grupo, merge de lessons similares
    for (agent, task_type), group in groups.items():
        if len(group) < 2:
            continue

        # Ordena por created_at: mais recente primeiro
        group.sort(key=lambda m: m.created_at, reverse=True)
        canonical = group[0]  # a mais recente é a canonical

        for other in group[1:]:
            if other.superseded_by is not None:
                continue
            overlap = _summary_overlap(canonical.summary, other.summary)
            if overlap >= 0.6:
                # Merge: incrementa confidence do canonical (capped em 1.0)
                canonical.confidence = min(1.0, canonical.confidence + 0.1)
                if other.id not in canonical.related_ids:
                    canonical.related_ids.append(other.id)
                store.supersede(other.id, MemoryType.LESSON_LEARNED, canonical)
                metrics["merged"] += 1
                logger.info(
                    f"Lessons merged: {other.id[:8]} → {canonical.id[:8]} "
                    f"(agent={agent}, task_type={task_type}, overlap={overlap:.2f})"
                )
            else:
                metrics["unchanged"] += 1

    if metrics["merged"]:
        logger.info(
            f"Dedup lessons: {metrics['merged']} consolidadas, {metrics['unchanged']} mantidas"
        )

    return metrics


def _summary_overlap(s1: str, s2: str) -> float:
    """Calcula a sobreposição de palavras-chave entre dois summaries (0.0 a 1.0)."""
    stopwords = {"o", "a", "e", "de", "do", "da", "em", "para", "com", "que", "the", "in", "at"}
    w1 = {w for w in s1.lower().split() if len(w) > 3 and w not in stopwords}
    w2 = {w for w in s2.lower().split() if len(w) > 3 and w not in stopwords}
    if not w1 or not w2:
        return 0.0
    intersection = w1 & w2
    min_len = min(len(w1), len(w2))
    return len(intersection) / min_len


def _mark_as_compiled(log_path: Path) -> None:
    """Marca um daily log como compilado adicionando marcador no final."""
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n<!-- COMPILED {datetime.now(timezone.utc).isoformat()} -->\n")
    except OSError as e:
        logger.warning(f"Erro ao marcar {log_path.name} como compilado: {e}")
