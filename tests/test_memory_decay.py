"""
Testes para memory/decay.py.

Cobre:
  - _compute_decay_rate(): cálculo da taxa lambda
  - compute_decayed_confidence(): valores corretos para cada tipo e tempo
  - apply_decay(): batch processing, save_fn callback, retorno (ativas, expiradas)
"""

import math
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock


from memory.types import Memory, MemoryType
from memory.decay import (
    _compute_decay_rate,
    compute_decayed_confidence,
    apply_decay,
)


# ─── _compute_decay_rate ──────────────────────────────────────────────


class TestComputeDecayRate:
    def test_rate_positive(self):
        rate = _compute_decay_rate(90.0)
        assert rate > 0

    def test_zero_days_returns_zero(self):
        rate = _compute_decay_rate(0.0)
        assert rate == 0.0

    def test_negative_days_returns_zero(self):
        rate = _compute_decay_rate(-5.0)
        assert rate == 0.0

    def test_rate_results_in_threshold_at_deadline(self):
        """Aplicando o rate ao deadline deve resultar em confidence ~= threshold."""
        days = 7.0
        threshold = 0.1
        rate = _compute_decay_rate(days, threshold)
        # confidence = exp(-rate * days)
        result = math.exp(-rate * days)
        assert abs(result - threshold) < 0.001


# ─── compute_decayed_confidence ───────────────────────────────────────


class TestComputeDecayedConfidence:
    def _make_mem(self, mem_type, days_old=0, confidence=1.0):
        created = datetime.now(timezone.utc) - timedelta(days=days_old)
        return Memory(
            type=mem_type,
            confidence=confidence,
            created_at=created,
        )

    def test_user_never_decays(self):
        mem = self._make_mem(MemoryType.USER, days_old=100)
        result = compute_decayed_confidence(mem)
        assert result == mem.confidence

    def test_architecture_never_decays(self):
        mem = self._make_mem(MemoryType.ARCHITECTURE, days_old=365)
        result = compute_decayed_confidence(mem)
        assert result == mem.confidence

    def test_progress_decays_fast(self):
        """Após 7 dias, PROGRESS deve estar próximo de 0.1."""
        mem = self._make_mem(MemoryType.PROGRESS, days_old=7)
        result = compute_decayed_confidence(mem)
        assert abs(result - 0.1) < 0.01

    def test_progress_after_14_days_near_zero(self):
        """Após 14 dias (2x o prazo), PROGRESS deve estar muito próximo de 0."""
        mem = self._make_mem(MemoryType.PROGRESS, days_old=14)
        result = compute_decayed_confidence(mem)
        assert result < 0.02

    def test_feedback_decays_slowly(self):
        """Após 90 dias, FEEDBACK deve estar próximo de 0.1."""
        mem = self._make_mem(MemoryType.FEEDBACK, days_old=90)
        result = compute_decayed_confidence(mem)
        assert abs(result - 0.1) < 0.01

    def test_feedback_after_30_days_still_high(self):
        """Após 30 dias (1/3 do prazo), FEEDBACK deve ter confidence > 0.4."""
        mem = self._make_mem(MemoryType.FEEDBACK, days_old=30)
        result = compute_decayed_confidence(mem)
        assert result > 0.4

    def test_zero_days_returns_original_confidence(self):
        mem = self._make_mem(MemoryType.PROGRESS, days_old=0)
        result = compute_decayed_confidence(mem)
        # Confiança inicial deve ser retornada (ou muito próxima)
        assert abs(result - mem.confidence) < 0.01

    def test_result_bounded_between_zero_and_one(self):
        mem = self._make_mem(MemoryType.PROGRESS, days_old=100, confidence=1.0)
        result = compute_decayed_confidence(mem)
        assert 0.0 <= result <= 1.0

    def test_monotonically_decreasing(self):
        """Confidence deve diminuir com o passar do tempo."""
        mem_3d = self._make_mem(MemoryType.PROGRESS, days_old=3)
        mem_5d = self._make_mem(MemoryType.PROGRESS, days_old=5)
        mem_7d = self._make_mem(MemoryType.PROGRESS, days_old=7)
        c3 = compute_decayed_confidence(mem_3d)
        c5 = compute_decayed_confidence(mem_5d)
        c7 = compute_decayed_confidence(mem_7d)
        assert c3 > c5 > c7

    def test_custom_now_parameter(self):
        """Deve usar o `now` fornecido em vez do datetime atual."""
        mem = Memory(
            type=MemoryType.PROGRESS,
            confidence=1.0,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        now_7d_later = datetime(2026, 1, 8, tzinfo=timezone.utc)
        result = compute_decayed_confidence(mem, now=now_7d_later)
        assert abs(result - 0.1) < 0.01


# ─── apply_decay ──────────────────────────────────────────────────────


class TestApplyDecay:
    def _make_old_progress(self, days=10) -> Memory:
        return Memory(
            type=MemoryType.PROGRESS,
            confidence=1.0,
            created_at=datetime.now(timezone.utc) - timedelta(days=days),
        )

    def _make_arch(self) -> Memory:
        return Memory(type=MemoryType.ARCHITECTURE, confidence=1.0)

    def test_returns_tuple_of_active_and_expired(self):
        fresh = Memory(type=MemoryType.ARCHITECTURE, confidence=1.0)
        old = self._make_old_progress(days=30)
        active, expired = apply_decay([fresh, old])
        assert isinstance(active, list)
        assert isinstance(expired, list)

    def test_architecture_stays_active(self):
        mem = self._make_arch()
        active, expired = apply_decay([mem])
        assert len(active) == 1
        assert len(expired) == 0

    def test_old_progress_expires(self):
        old = self._make_old_progress(days=30)
        active, expired = apply_decay([old])
        assert len(expired) == 1

    def test_save_fn_called_when_confidence_changes(self):
        old = self._make_old_progress(days=30)
        save_fn = MagicMock()
        apply_decay([old], save_fn=save_fn)
        save_fn.assert_called()

    def test_save_fn_not_called_for_stable_confidence(self):
        """Tipos que nunca decaem não devem acionar save_fn desnecessariamente."""
        mem = self._make_arch()
        save_fn = MagicMock()
        apply_decay([mem], save_fn=save_fn)
        # Sem mudança significativa → save_fn não deve ser chamado
        save_fn.assert_not_called()

    def test_empty_list_returns_empty_tuples(self):
        active, expired = apply_decay([])
        assert active == []
        assert expired == []

    def test_expired_memories_have_low_confidence(self):
        old = self._make_old_progress(days=30)
        _, expired = apply_decay([old])
        for mem in expired:
            assert mem.confidence < 0.1

    def test_custom_now_respected(self):
        mem = Memory(
            type=MemoryType.PROGRESS,
            confidence=1.0,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        # 30 dias após a criação
        future_now = datetime(2026, 1, 31, tzinfo=timezone.utc)
        active, expired = apply_decay([mem], now=future_now)
        assert len(expired) == 1
