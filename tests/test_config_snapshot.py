"""
Testes para config/snapshot.py (Ch. 12).

Cobre:
  - ConfigSnapshot: imutabilidade (frozen=True), campos presentes
  - freeze(): captura valores corretos do settings
  - detect_drift(): detecta mudanças em cada campo crítico
"""

import pytest
from unittest.mock import MagicMock

from config.snapshot import ConfigSnapshot, freeze, detect_drift


def _make_settings(**overrides):
    """Cria um mock de Settings com valores padrão."""
    settings = MagicMock()
    settings.default_model = "claude-sonnet-4-6"
    settings.max_turns = 50
    settings.max_budget_usd = 5.0
    settings.tier_model_map = {"T1": "claude-opus-4-6"}
    settings.tier_turns_map = {"T1": 20, "T2": 12, "T3": 5}
    settings.tier_effort_map = {"T1": "high", "T2": "medium", "T3": "low"}
    settings.inject_kb_index = True
    settings.memory_enabled = True
    for key, val in overrides.items():
        setattr(settings, key, val)
    return settings


# ─── ConfigSnapshot ──────────────────────────────────────────────────────────


class TestConfigSnapshot:
    def test_is_immutable(self):
        """ConfigSnapshot é frozen — não aceita modificação após criação."""
        snap = ConfigSnapshot(
            default_model="claude-sonnet-4-6",
            max_turns=50,
            max_budget_usd=5.0,
            tier_model_map=(("T1", "claude-opus-4-6"),),
            tier_turns_map=(("T1", 20),),
            tier_effort_map=(("T1", "high"),),
            inject_kb_index=True,
            memory_enabled=True,
            created_at="2026-01-01T00:00:00+00:00",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            snap.default_model = "changed"  # type: ignore[misc]

    def test_has_all_expected_fields(self):
        """ConfigSnapshot deve ter todos os campos necessários."""
        snap = freeze(_make_settings())
        assert hasattr(snap, "default_model")
        assert hasattr(snap, "max_turns")
        assert hasattr(snap, "max_budget_usd")
        assert hasattr(snap, "tier_model_map")
        assert hasattr(snap, "tier_turns_map")
        assert hasattr(snap, "tier_effort_map")
        assert hasattr(snap, "inject_kb_index")
        assert hasattr(snap, "memory_enabled")
        assert hasattr(snap, "created_at")

    def test_tier_maps_are_tuples(self):
        """Os tier maps devem ser tuplas (hashable) no snapshot."""
        snap = freeze(_make_settings())
        assert isinstance(snap.tier_model_map, tuple)
        assert isinstance(snap.tier_turns_map, tuple)
        assert isinstance(snap.tier_effort_map, tuple)


# ─── freeze ──────────────────────────────────────────────────────────────────


class TestFreeze:
    def test_captures_default_model(self):
        s = _make_settings(default_model="claude-opus-4-6")
        snap = freeze(s)
        assert snap.default_model == "claude-opus-4-6"

    def test_captures_max_turns(self):
        s = _make_settings(max_turns=30)
        snap = freeze(s)
        assert snap.max_turns == 30

    def test_captures_max_budget(self):
        s = _make_settings(max_budget_usd=2.5)
        snap = freeze(s)
        assert snap.max_budget_usd == pytest.approx(2.5)

    def test_captures_inject_kb_index(self):
        s = _make_settings(inject_kb_index=False)
        snap = freeze(s)
        assert snap.inject_kb_index is False

    def test_captures_memory_enabled(self):
        s = _make_settings(memory_enabled=False)
        snap = freeze(s)
        assert snap.memory_enabled is False

    def test_tier_model_map_serialized_correctly(self):
        s = _make_settings(tier_model_map={"T1": "claude-opus-4-6", "T2": "claude-sonnet-4-6"})
        snap = freeze(s)
        # Deve estar ordenado e como tupla de pares
        assert snap.tier_model_map == (("T1", "claude-opus-4-6"), ("T2", "claude-sonnet-4-6"))

    def test_created_at_is_iso_string(self):
        snap = freeze(_make_settings())
        # Verifica que é uma string ISO 8601 válida
        from datetime import datetime

        parsed = datetime.fromisoformat(snap.created_at)
        assert parsed is not None

    def test_empty_tier_maps_work(self):
        s = _make_settings(tier_model_map={}, tier_turns_map={}, tier_effort_map={})
        snap = freeze(s)
        assert snap.tier_model_map == ()
        assert snap.tier_turns_map == ()
        assert snap.tier_effort_map == ()


# ─── detect_drift ────────────────────────────────────────────────────────────


class TestDetectDrift:
    def test_no_drift_when_identical(self):
        """Sem alterações, detect_drift retorna lista vazia."""
        s = _make_settings()
        snap = freeze(s)
        drifts = detect_drift(s, snap)
        assert drifts == []

    def test_detects_model_change(self):
        """Mudança de default_model deve ser detectada."""
        s = _make_settings(default_model="claude-sonnet-4-6")
        snap = freeze(s)
        s.default_model = "claude-opus-4-6"
        drifts = detect_drift(s, snap)
        assert any("default_model" in d for d in drifts)

    def test_detects_max_turns_change(self):
        """Mudança de max_turns deve ser detectada."""
        s = _make_settings(max_turns=50)
        snap = freeze(s)
        s.max_turns = 200
        drifts = detect_drift(s, snap)
        assert any("max_turns" in d for d in drifts)

    def test_detects_budget_change(self):
        """Mudança de max_budget_usd deve ser detectada."""
        s = _make_settings(max_budget_usd=5.0)
        snap = freeze(s)
        s.max_budget_usd = 100.0
        drifts = detect_drift(s, snap)
        assert any("max_budget_usd" in d for d in drifts)

    def test_detects_inject_kb_index_change(self):
        """Mudança de inject_kb_index deve ser detectada."""
        s = _make_settings(inject_kb_index=True)
        snap = freeze(s)
        s.inject_kb_index = False
        drifts = detect_drift(s, snap)
        assert any("inject_kb_index" in d for d in drifts)

    def test_detects_memory_enabled_change(self):
        """Mudança de memory_enabled deve ser detectada."""
        s = _make_settings(memory_enabled=True)
        snap = freeze(s)
        s.memory_enabled = False
        drifts = detect_drift(s, snap)
        assert any("memory_enabled" in d for d in drifts)

    def test_detects_tier_model_map_change(self):
        """Mudança de tier_model_map deve ser detectada."""
        s = _make_settings(tier_model_map={"T1": "claude-opus-4-6"})
        snap = freeze(s)
        s.tier_model_map = {"T1": "injected-model"}
        drifts = detect_drift(s, snap)
        assert any("tier_model_map" in d for d in drifts)

    def test_detects_tier_turns_map_change(self):
        """Mudança de tier_turns_map deve ser detectada."""
        s = _make_settings(tier_turns_map={"T1": 20})
        snap = freeze(s)
        s.tier_turns_map = {"T1": 999}
        drifts = detect_drift(s, snap)
        assert any("tier_turns_map" in d for d in drifts)

    def test_detects_tier_effort_map_change(self):
        """Mudança de tier_effort_map deve ser detectada."""
        s = _make_settings(tier_effort_map={"T1": "high"})
        snap = freeze(s)
        s.tier_effort_map = {"T1": "max"}
        drifts = detect_drift(s, snap)
        assert any("tier_effort_map" in d for d in drifts)

    def test_returns_multiple_drifts(self):
        """Múltiplas mudanças simultâneas são todas detectadas."""
        s = _make_settings()
        snap = freeze(s)
        s.default_model = "injected-model"
        s.max_budget_usd = 999.0
        s.memory_enabled = False
        drifts = detect_drift(s, snap)
        assert len(drifts) >= 3

    def test_no_drift_for_identical_tier_maps(self):
        """Tier maps idênticos não devem gerar drift."""
        s = _make_settings(tier_model_map={"T1": "claude-opus-4-6", "T2": "claude-sonnet-4-6"})
        snap = freeze(s)
        drifts = detect_drift(s, snap)
        assert drifts == []
