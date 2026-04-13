"""
Testes para a expansão do sistema de staleness em memory/lint.py (Ch. 11).

Cobre:
  - _STALE_THRESHOLDS e _STALE_SEVERITY definidos corretamente
  - stale_progress: warning a <0.30 para PROGRESS (decay rápido, 7 dias)
  - stale_feedback: info    a <0.20 para FEEDBACK (decay lento, 90 dias)
  - USER e ARCHITECTURE: nunca ficam stale (nunca decaem)
  - Memórias superseded: ignoradas pelo check de staleness
"""

from datetime import datetime, timedelta, timezone

import pytest

from memory.lint import _STALE_THRESHOLDS, _STALE_SEVERITY, lint_memories
from memory.store import MemoryStore
from memory.types import Memory, MemoryType


@pytest.fixture
def store(tmp_path):
    return MemoryStore(data_dir=tmp_path / "lint_stale_test")


# ─── Configuração dos thresholds ─────────────────────────────────────────────


class TestStaleThresholdsConfig:
    def test_progress_threshold_is_030(self):
        assert _STALE_THRESHOLDS[MemoryType.PROGRESS] == pytest.approx(0.30)

    def test_feedback_threshold_is_020(self):
        assert _STALE_THRESHOLDS[MemoryType.FEEDBACK] == pytest.approx(0.20)

    def test_user_has_no_threshold(self):
        assert MemoryType.USER not in _STALE_THRESHOLDS

    def test_architecture_has_no_threshold(self):
        assert MemoryType.ARCHITECTURE not in _STALE_THRESHOLDS

    def test_progress_severity_is_warning(self):
        assert _STALE_SEVERITY[MemoryType.PROGRESS] == "warning"

    def test_feedback_severity_is_info(self):
        assert _STALE_SEVERITY[MemoryType.FEEDBACK] == "info"


# ─── stale_progress ──────────────────────────────────────────────────────────


class TestStaleProgressLint:
    def test_reports_stale_progress_at_4_days(self, store):
        """PROGRESS com 4 dias (confidence ~0.27) está abaixo de 0.30 → warning."""
        old = datetime.now(timezone.utc) - timedelta(days=4)
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso de 4 dias já abaixo do limiar.",
            summary="Progresso antigo",
            tags=["task"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(issues) >= 1
        assert issues[0].severity == "warning"

    def test_fresh_progress_not_stale(self, store):
        """PROGRESS recente (0 dias) tem confidence ~1.0 → não é stale."""
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Tarefa em andamento hoje.",
            summary="Progresso recente",
            tags=["task"],
            confidence=1.0,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(issues) == 0

    def test_progress_20_days_triggers_warning(self, store):
        """PROGRESS com 20 dias (confidence << 0.30) → warning."""
        old = datetime.now(timezone.utc) - timedelta(days=20)
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso muito antigo e irrelevante.",
            summary="Progresso 20d",
            tags=["task"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(issues) >= 1

    def test_superseded_progress_not_reported(self, store):
        """PROGRESS superseded não deve ser reportado como stale."""
        old = datetime.now(timezone.utc) - timedelta(days=20)
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso antigo mas já superseded.",
            summary="Progresso superseded",
            tags=["task"],
            confidence=1.0,
            created_at=old,
            superseded_by="outro_id",
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(issues) == 0


# ─── stale_feedback ──────────────────────────────────────────────────────────


class TestStaleFeedbackLint:
    def test_reports_stale_feedback_at_100_days(self, store):
        """FEEDBACK com 100 dias (confidence ~0.08) está abaixo de 0.20 → info."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Orientação dada há 100 dias — pode estar desatualizada.",
            summary="Feedback antigo",
            tags=["feedback"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) >= 1
        assert issues[0].severity == "info"

    def test_fresh_feedback_not_stale(self, store):
        """FEEDBACK recente (0 dias) tem confidence ~1.0 → não é stale."""
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Correção dada hoje pelo usuário.",
            summary="Feedback recente",
            tags=["feedback"],
            confidence=1.0,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) == 0

    def test_feedback_70_days_not_yet_stale(self, store):
        """FEEDBACK com 70 dias (confidence ~0.16) está abaixo de 0.20 → já é stale."""
        # λ = -ln(0.1)/90 ≈ 0.02558
        # conf_70 = exp(-0.02558 * 70) ≈ exp(-1.79) ≈ 0.167 < 0.20
        old = datetime.now(timezone.utc) - timedelta(days=70)
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Orientação dada 70 dias atrás.",
            summary="Feedback 70d",
            tags=["feedback"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        # 70 dias → confidence ≈ 0.167 < 0.20 → deve aparecer como stale
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) >= 1

    def test_feedback_30_days_not_stale(self, store):
        """FEEDBACK com 30 dias (confidence ~0.46) está acima de 0.20 → não é stale."""
        old = datetime.now(timezone.utc) - timedelta(days=30)
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Orientação recente ainda válida.",
            summary="Feedback 30d",
            tags=["feedback"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) == 0

    def test_superseded_feedback_not_reported(self, store):
        """FEEDBACK superseded não deve ser reportado como stale."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Orientação antiga já substituída.",
            summary="Feedback superseded",
            tags=["feedback"],
            confidence=1.0,
            created_at=old,
            superseded_by="novo_feedback_id",
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) == 0


# ─── USER e ARCHITECTURE: imunes a staleness ─────────────────────────────────


class TestNonDecayingTypesNotStale:
    def test_ancient_architecture_is_never_stale(self, store):
        """ARCHITECTURE com anos de idade jamais aparece como stale."""
        old = datetime.now(timezone.utc) - timedelta(days=1000)
        mem = Memory(
            type=MemoryType.ARCHITECTURE,
            content="Decisão arquitetural permanente.",
            summary="Decisão arq antiga",
            tags=["arch"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        stale_issues = [i for i in report.issues if "stale" in i.check]
        assert len(stale_issues) == 0

    def test_ancient_user_memory_is_never_stale(self, store):
        """USER com anos de idade jamais aparece como stale."""
        old = datetime.now(timezone.utc) - timedelta(days=500)
        mem = Memory(
            type=MemoryType.USER,
            content="Preferência permanente do usuário.",
            summary="Preferência user antiga",
            tags=["user"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        stale_issues = [i for i in report.issues if "stale" in i.check]
        assert len(stale_issues) == 0


# ─── check name no issue ─────────────────────────────────────────────────────


class TestStaleCheckNames:
    def test_stale_progress_uses_correct_check_name(self, store):
        """O check name para PROGRESS deve ser 'stale_progress'."""
        old = datetime.now(timezone.utc) - timedelta(days=20)
        mem = Memory(
            type=MemoryType.PROGRESS,
            content="Progresso antigo.",
            summary="Prog antigo",
            tags=["task"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_progress"]
        assert len(issues) >= 1

    def test_stale_feedback_uses_correct_check_name(self, store):
        """O check name para FEEDBACK deve ser 'stale_feedback'."""
        old = datetime.now(timezone.utc) - timedelta(days=100)
        mem = Memory(
            type=MemoryType.FEEDBACK,
            content="Feedback antigo.",
            summary="Feedback antigo",
            tags=["feedback"],
            confidence=1.0,
            created_at=old,
        )
        store.save(mem)
        report = lint_memories(store)
        issues = [i for i in report.issues if i.check == "stale_feedback"]
        assert len(issues) >= 1
