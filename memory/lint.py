"""
Memory Lint — Health checks para o sistema de memória.

Executa 7 verificações sem custo (nenhuma chamada LLM):
  1. Orphan references: memórias que referenciam IDs inexistentes
  2. Broken supersedes: cadeias de supersede que apontam para memórias deletadas
  3. Stale memories: memórias com confidence decaída abaixo do limiar (Ch. 11)
     - PROGRESS        → warning a <0.30  (decay rápido: 7 dias por padrão)
     - PIPELINE_STATUS → warning a <0.30  (decay médio: 14 dias por padrão)
     - FEEDBACK        → info    a <0.20  (decay lento: 90 dias por padrão)
     - USER / ARCHITECTURE / DATA_ASSET / PLATFORM_DECISION: nunca decaem — ignoradas
  4. Empty content: memórias sem conteúdo significativo
  5. Duplicate summaries: memórias com resumos idênticos ou quase
  6. Missing index: index.md desatualizado ou ausente
  7. Tag hygiene: tags inconsistentes ou mal formatadas
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from memory.store import MemoryStore
from memory.types import Memory, MemoryType
from memory.decay import compute_decayed_confidence

logger = logging.getLogger("data_agents.memory.lint")

# ─── Staleness thresholds (Ch. 11) ───────────────────────────────────────────
# Limiar de confidence decaída abaixo do qual uma memória é considerada stale.
# Apenas tipos com decay são verificados.
# USER, ARCHITECTURE, DATA_ASSET, PLATFORM_DECISION nunca decaem — ignorados.
_STALE_THRESHOLDS: dict[MemoryType, float] = {
    MemoryType.PROGRESS: 0.30,  # warning cedo — decay rápido (7 dias padrão)
    MemoryType.PIPELINE_STATUS: 0.30,  # warning cedo — decay médio (14 dias padrão)
    MemoryType.FEEDBACK: 0.20,  # info depois  — decay lento (90 dias padrão)
}

# Severidade associada a cada tipo stale
_STALE_SEVERITY: dict[MemoryType, str] = {
    MemoryType.PROGRESS: "warning",
    MemoryType.PIPELINE_STATUS: "warning",
    MemoryType.FEEDBACK: "info",
}


@dataclass
class LintIssue:
    """Uma issue encontrada pelo linter."""

    severity: str  # "error", "warning", "info"
    check: str  # Nome do check
    memory_id: str  # ID da memória afetada (ou "system" para issues globais)
    message: str  # Descrição da issue

    def __str__(self) -> str:
        icon = {"error": "X", "warning": "!", "info": "i"}.get(self.severity, "?")
        return f"[{icon}] {self.check}: {self.memory_id} — {self.message}"


@dataclass
class LintReport:
    """Relatório completo de lint."""

    issues: list[LintIssue] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    ran_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def summary(self) -> str:
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        info = sum(1 for i in self.issues if i.severity == "info")
        return f"Lint: {errors} errors, {warnings} warnings, {info} info"

    def to_markdown(self) -> str:
        lines = [
            f"# Memory Lint Report — {self.ran_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            f"**{self.summary}**",
            "",
        ]

        if not self.issues:
            lines.append("Nenhuma issue encontrada. Sistema de memória saudável.")
            return "\n".join(lines)

        for severity in ["error", "warning", "info"]:
            issues = [i for i in self.issues if i.severity == severity]
            if not issues:
                continue
            lines.append(f"## {severity.upper()}S ({len(issues)})")
            lines.append("")
            for issue in issues:
                lines.append(f"- **{issue.check}** [{issue.memory_id}]: {issue.message}")
            lines.append("")

        if self.stats:
            lines.append("## Estatísticas")
            lines.append("")
            for key, val in self.stats.items():
                lines.append(f"- {key}: {val}")

        return "\n".join(lines)


def lint_memories(store: MemoryStore) -> LintReport:
    """
    Executa todos os health checks no sistema de memória.

    Args:
        store: MemoryStore para verificar.

    Returns:
        LintReport com todas as issues encontradas.
    """
    report = LintReport()

    # Carrega todas as memórias (incluindo inativas)
    all_memories = store.list_all(active_only=False, min_confidence=0.0)
    all_ids = {m.id for m in all_memories}

    report.stats = {
        "total_memories": len(all_memories),
        "active": sum(1 for m in all_memories if m.is_active()),
        "superseded": sum(1 for m in all_memories if m.superseded_by),
        "low_confidence": sum(1 for m in all_memories if m.confidence < 0.1),
    }

    # 1. Orphan references
    _check_orphan_references(all_memories, all_ids, report)

    # 2. Broken supersedes
    _check_broken_supersedes(all_memories, all_ids, report)

    # 3. Stale memories
    _check_stale_memories(all_memories, report)

    # 4. Empty content
    _check_empty_content(all_memories, report)

    # 5. Duplicate summaries
    _check_duplicate_summaries(all_memories, report)

    # 6. Missing index
    _check_missing_index(store, report)

    # 7. Tag hygiene
    _check_tag_hygiene(all_memories, report)

    logger.info(report.summary)
    return report


def _check_orphan_references(memories: list[Memory], all_ids: set[str], report: LintReport) -> None:
    """Verifica referências a IDs inexistentes."""
    for mem in memories:
        for ref_id in mem.related_ids:
            if ref_id not in all_ids:
                report.issues.append(
                    LintIssue(
                        severity="warning",
                        check="orphan_reference",
                        memory_id=mem.id,
                        message=f"Referencia ID inexistente: {ref_id}",
                    )
                )


def _check_broken_supersedes(memories: list[Memory], all_ids: set[str], report: LintReport) -> None:
    """Verifica cadeias de supersede quebradas."""
    for mem in memories:
        if mem.superseded_by and mem.superseded_by not in all_ids:
            report.issues.append(
                LintIssue(
                    severity="error",
                    check="broken_supersede",
                    memory_id=mem.id,
                    message=f"Superseded por ID inexistente: {mem.superseded_by}",
                )
            )


def _check_stale_memories(memories: list[Memory], report: LintReport) -> None:
    """
    Verifica memórias com confidence decaída abaixo do limiar de alerta (Ch. 11).

    Cobre todos os tipos que têm decay:
      - PROGRESS        → warning a <0.30 (~3-4 dias de idade)
      - PIPELINE_STATUS → warning a <0.30 (~7 dias de idade)
      - FEEDBACK        → info    a <0.20 (~70+ dias de idade)
      - USER / ARCHITECTURE / DATA_ASSET / PLATFORM_DECISION: ignorados — nunca decaem.
    """
    now = datetime.now(timezone.utc)
    for mem in memories:
        threshold = _STALE_THRESHOLDS.get(mem.type)
        if threshold is None:
            # Tipo sem decay (USER, ARCHITECTURE) — nunca fica stale
            continue

        if mem.superseded_by is not None:
            # Já superseded — não é stale, é histórico
            continue

        current_conf = compute_decayed_confidence(mem, now)

        # Confiança exatamente 0 = memória já completamente expirada
        # (provavelmente listada como inativa; não duplicar o aviso)
        if current_conf == 0.0:
            continue

        if current_conf < threshold:
            days_old = (now - mem.created_at).days
            severity = _STALE_SEVERITY.get(mem.type, "info")
            check_name = f"stale_{mem.type.value}"
            report.issues.append(
                LintIssue(
                    severity=severity,
                    check=check_name,
                    memory_id=mem.id,
                    message=(
                        f"Memória {mem.type.value.upper()} com confidence decaída "
                        f"{current_conf:.3f} (limiar: {threshold:.2f}, {days_old} dias). "
                        f"Considere remover ou renovar."
                    ),
                )
            )


def _check_empty_content(memories: list[Memory], report: LintReport) -> None:
    """Verifica memórias sem conteúdo significativo."""
    for mem in memories:
        if len(mem.content.strip()) < 10:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    check="empty_content",
                    memory_id=mem.id,
                    message=f"Conteúdo muito curto ({len(mem.content.strip())} chars)",
                )
            )


def _check_duplicate_summaries(memories: list[Memory], report: LintReport) -> None:
    """Verifica memórias com resumos idênticos."""
    seen: dict[str, str] = {}  # normalized_summary → first_id
    for mem in memories:
        if not mem.is_active():
            continue
        key = mem.normalized_summary
        if key in seen:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    check="duplicate_summary",
                    memory_id=mem.id,
                    message=f"Resumo duplicado com memória {seen[key]}",
                )
            )
        else:
            seen[key] = mem.id


def _check_missing_index(store: MemoryStore, report: LintReport) -> None:
    """Verifica se o index.md existe e está atualizado."""
    index_path = store.data_dir / "index.md"
    if not index_path.exists():
        report.issues.append(
            LintIssue(
                severity="warning",
                check="missing_index",
                memory_id="system",
                message="index.md não encontrado. Execute store.build_index().",
            )
        )
        return

    # Verifica se está muito desatualizado (>24h)
    import os

    mtime = datetime.fromtimestamp(os.path.getmtime(index_path), tz=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
    if age_hours > 24:
        report.issues.append(
            LintIssue(
                severity="info",
                check="stale_index",
                memory_id="system",
                message=f"index.md tem {age_hours:.0f}h. Considere regenerar.",
            )
        )


def _check_tag_hygiene(memories: list[Memory], report: LintReport) -> None:
    """Verifica tags inconsistentes."""
    tag_counts: dict[str, int] = {}
    for mem in memories:
        if not mem.is_active():
            continue
        for tag in mem.tags:
            # Tags devem ser lowercase, sem espaços
            if tag != tag.lower() or " " in tag:
                report.issues.append(
                    LintIssue(
                        severity="info",
                        check="tag_format",
                        memory_id=mem.id,
                        message=f"Tag mal formatada: '{tag}' (use lowercase sem espaços)",
                    )
                )
            tag_counts[tag.lower()] = tag_counts.get(tag.lower(), 0) + 1

    # Tags usadas apenas uma vez (pode indicar typo)
    singletons = [t for t, c in tag_counts.items() if c == 1]
    if len(singletons) > 10:
        report.issues.append(
            LintIssue(
                severity="info",
                check="tag_singletons",
                memory_id="system",
                message=f"{len(singletons)} tags usadas apenas uma vez. Considere consolidar.",
            )
        )
