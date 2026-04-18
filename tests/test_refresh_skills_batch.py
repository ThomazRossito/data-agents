"""
Testes para scripts/refresh_skills.py — migração para Batch API (T5.2).

Cobrem:
  - Cost estimation com 50% de desconto do batch
  - _build_batch_request monta params corretos (model, tools, system, custom_id)
  - _extract_updated_skill lida com NO_CHANGE, delimitadores faltando e conteúdo válido
  - _process_batch_result roteia ok/no_change/empty_response e escreve arquivo
  - run_refresh submete um batch único, processa resultados e agrega métricas
  - run_refresh não chama API no dry-run e respeita skip por idade
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.refresh_skills import (
    _build_batch_request,
    _estimate_cost,
    _extract_updated_skill,
    _process_batch_result,
    _SKILL_BEGIN,
    _SKILL_END,
    run_refresh,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def skill_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """SKILL.md válida com frontmatter e conteúdo mínimo.

    Também monkeypatch `_PROJECT_ROOT` para o tmp_path — o script usa
    `relative_to(_PROJECT_ROOT)` e tmp_path não está sob o projeto real.
    """
    monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)
    path = tmp_path / "patterns" / "sample" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: sample\nupdated_at: 2025-01-01\n---\n# Sample\n\nOld content.\n",
        encoding="utf-8",
    )
    return path


def _fake_usage(input_tokens: int = 1_000, output_tokens: int = 500) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)


def _fake_text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _fake_message(
    text: str, input_tokens: int = 1_000, output_tokens: int = 500
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[_fake_text_block(text)],
        usage=_fake_usage(input_tokens, output_tokens),
    )


# ── Cost estimation ──────────────────────────────────────────────────────────


class TestEstimateCost:
    def test_batch_discount_is_50_percent(self):
        on_demand = _estimate_cost(1_000_000, 1_000_000, batch=False)
        batch = _estimate_cost(1_000_000, 1_000_000, batch=True)
        assert batch == pytest.approx(on_demand * 0.5)

    def test_default_is_batch(self):
        assert _estimate_cost(1_000_000, 1_000_000) == pytest.approx(
            _estimate_cost(1_000_000, 1_000_000, batch=True)
        )

    def test_zero_tokens_is_zero_cost(self):
        assert _estimate_cost(0, 0) == 0.0

    def test_cost_scales_linearly(self):
        half = _estimate_cost(500_000, 500_000)
        full = _estimate_cost(1_000_000, 1_000_000)
        assert full == pytest.approx(2 * half)


# ── Request building ──────────────────────────────────────────────────────────


class TestBuildBatchRequest:
    def test_custom_id_and_model_are_passed_through(self, skill_file: Path):
        request = _build_batch_request(skill_file, "skill-042", "claude-sonnet-4-6")
        assert request["custom_id"] == "skill-042"
        assert request["params"]["model"] == "claude-sonnet-4-6"

    def test_web_search_tool_is_included(self, skill_file: Path):
        request = _build_batch_request(skill_file, "skill-000", "claude-sonnet-4-6")
        tools = request["params"]["tools"]
        assert len(tools) == 1
        assert tools[0]["type"] == "web_search_20250305"
        assert tools[0]["name"] == "web_search"

    def test_user_prompt_embeds_skill_content(self, skill_file: Path):
        request = _build_batch_request(skill_file, "skill-000", "claude-sonnet-4-6")
        user_msg = request["params"]["messages"][0]["content"]
        assert "Old content." in user_msg
        assert "SKILL.md ATUAL" in user_msg

    def test_system_prompt_is_set(self, skill_file: Path):
        request = _build_batch_request(skill_file, "skill-000", "claude-sonnet-4-6")
        assert "Skill Updater" in request["params"]["system"]


# ── _extract_updated_skill ────────────────────────────────────────────────────


class TestExtractUpdatedSkill:
    def test_no_delimiters_returns_none(self):
        assert _extract_updated_skill("sem delimitadores") is None

    def test_extracts_content_between_delimiters(self):
        text = f"resumo\n{_SKILL_BEGIN}\n# Nova skill\nlinha 2\n{_SKILL_END}\nfim"
        assert _extract_updated_skill(text) == "# Nova skill\nlinha 2\n"

    def test_only_begin_returns_none(self):
        assert _extract_updated_skill(f"resumo\n{_SKILL_BEGIN}\n# só inicio") is None


# ── _process_batch_result ─────────────────────────────────────────────────────


class TestProcessBatchResult:
    def test_no_change_keeps_file_untouched(self, skill_file: Path):
        original = skill_file.read_text()
        message = _fake_message("NO_CHANGE")
        result = _process_batch_result(skill_file, message)
        assert result["status"] == "no_change"
        assert result["cost"] > 0
        assert skill_file.read_text() == original

    def test_empty_response_keeps_file_untouched(self, skill_file: Path):
        original = skill_file.read_text()
        message = _fake_message("resumo sem delimitadores")
        result = _process_batch_result(skill_file, message)
        assert result["status"] == "empty_response"
        assert skill_file.read_text() == original
        assert "resumo sem" in result["preview"]

    def test_ok_writes_new_content(self, skill_file: Path):
        new_body = "---\nname: sample\nupdated_at: 2026-01-01\n---\n# Sample\n\nNew content.\n"
        text = f"resumo\n{_SKILL_BEGIN}\n{new_body}\n{_SKILL_END}"
        result = _process_batch_result(skill_file, _fake_message(text))
        assert result["status"] == "ok"
        written = skill_file.read_text()
        assert "New content." in written
        assert "Old content." not in written

    def test_cost_applies_batch_discount(self, skill_file: Path):
        message = _fake_message("NO_CHANGE", input_tokens=1_000_000, output_tokens=1_000_000)
        result = _process_batch_result(skill_file, message)
        on_demand = _estimate_cost(1_000_000, 1_000_000, batch=False)
        assert result["cost"] == pytest.approx(on_demand * 0.5)


# ── run_refresh (integration) ─────────────────────────────────────────────────


def _make_skill(root: Path, domain: str, name: str, content: str) -> Path:
    skill_path = root / domain / name / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(content, encoding="utf-8")
    return skill_path


def _batch_entry(custom_id: str, message) -> SimpleNamespace:
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(type="succeeded", message=message),
    )


def _batch_error_entry(custom_id: str, err: str) -> SimpleNamespace:
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(type="errored", error=err),
    )


class _AsyncIterator:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


def _build_mock_client(entries: list[SimpleNamespace], batch_id: str = "batch_abc123") -> MagicMock:
    """Cria um AsyncAnthropic mock que responde ao ciclo create→retrieve→results."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.batches = MagicMock()
    client.messages.batches.create = AsyncMock(
        return_value=SimpleNamespace(id=batch_id, processing_status="in_progress")
    )
    client.messages.batches.retrieve = AsyncMock(
        return_value=SimpleNamespace(
            id=batch_id,
            processing_status="ended",
            request_counts=SimpleNamespace(
                succeeded=len(entries),
                errored=0,
                expired=0,
                canceled=0,
                processing=0,
            ),
        )
    )
    client.messages.batches.results = AsyncMock(return_value=_AsyncIterator(entries))
    return client


class TestRunRefresh:
    def test_dry_run_does_not_hit_api(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("scripts.refresh_skills._SKILLS_DIR", tmp_path)
        monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)
        _make_skill(tmp_path, "domain", "alpha", "# Alpha old\n")

        called = {"n": 0}

        def _fake_anthropic(*a, **kw):
            called["n"] += 1
            raise AssertionError("dry-run não deveria instanciar AsyncAnthropic")

        monkeypatch.setattr("anthropic.AsyncAnthropic", _fake_anthropic)
        metrics = asyncio.run(
            run_refresh(
                domains=["domain"],
                interval_days=0,
                force=True,
                dry_run=True,
                model="claude-sonnet-4-6",
            )
        )
        assert metrics["refreshed"] == 1
        assert metrics["errors"] == 0
        assert called["n"] == 0

    def test_empty_domain_returns_zero_metrics(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("scripts.refresh_skills._SKILLS_DIR", tmp_path)
        monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)

        metrics = asyncio.run(
            run_refresh(
                domains=["nao-existe"],
                interval_days=3,
                force=False,
                dry_run=False,
                model="claude-sonnet-4-6",
            )
        )
        assert metrics["total"] == 0
        assert metrics["refreshed"] == 0
        assert metrics["batch_id"] is None

    def test_single_batch_submission_processes_all_skills(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("scripts.refresh_skills._SKILLS_DIR", tmp_path)
        monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)

        skill_a = _make_skill(tmp_path, "domain", "alpha", "---\nname: alpha\n---\n# Alpha old\n")
        skill_b = _make_skill(tmp_path, "domain", "beta", "---\nname: beta\n---\n# Beta old\n")

        new_alpha = "---\nname: alpha\nupdated_at: 2026-01-01\n---\n# Alpha new\n"
        entries = [
            _batch_entry(
                "skill-000", _fake_message(f"resumo\n{_SKILL_BEGIN}\n{new_alpha}\n{_SKILL_END}")
            ),
            _batch_entry("skill-001", _fake_message("NO_CHANGE")),
        ]
        client = _build_mock_client(entries)
        monkeypatch.setattr("anthropic.AsyncAnthropic", lambda *a, **kw: client)

        metrics = asyncio.run(
            run_refresh(
                domains=["domain"],
                interval_days=0,
                force=True,
                dry_run=False,
                model="claude-sonnet-4-6",
            )
        )

        # Submeteu um único batch com 2 requests
        assert client.messages.batches.create.call_count == 1
        call_kwargs = client.messages.batches.create.call_args.kwargs
        assert len(call_kwargs["requests"]) == 2
        assert {r["custom_id"] for r in call_kwargs["requests"]} == {"skill-000", "skill-001"}

        # Alpha foi atualizada, Beta manteve
        assert "Alpha new" in skill_a.read_text()
        assert "Beta old" in skill_b.read_text()
        assert metrics["refreshed"] == 1
        assert metrics["no_change"] == 1
        assert metrics["batch_id"] == "batch_abc123"
        assert metrics["cost"] > 0

    def test_batch_error_is_counted(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("scripts.refresh_skills._SKILLS_DIR", tmp_path)
        monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)
        _make_skill(tmp_path, "domain", "alpha", "---\nname: alpha\n---\n# Alpha\n")

        entries = [_batch_error_entry("skill-000", "rate_limit")]
        client = _build_mock_client(entries)
        monkeypatch.setattr("anthropic.AsyncAnthropic", lambda *a, **kw: client)

        metrics = asyncio.run(
            run_refresh(
                domains=["domain"],
                interval_days=0,
                force=True,
                dry_run=False,
                model="claude-sonnet-4-6",
            )
        )
        assert metrics["refreshed"] == 0
        assert metrics["errors"] == 1
        assert metrics["details"][0]["status"] == "errored"

    def test_submission_failure_counts_all_as_errors(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr("scripts.refresh_skills._SKILLS_DIR", tmp_path)
        monkeypatch.setattr("scripts.refresh_skills._PROJECT_ROOT", tmp_path)
        _make_skill(tmp_path, "domain", "alpha", "---\nname: alpha\n---\n# Alpha\n")
        _make_skill(tmp_path, "domain", "beta", "---\nname: beta\n---\n# Beta\n")

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.batches = MagicMock()
        client.messages.batches.create = AsyncMock(side_effect=RuntimeError("network down"))
        monkeypatch.setattr("anthropic.AsyncAnthropic", lambda *a, **kw: client)

        metrics = asyncio.run(
            run_refresh(
                domains=["domain"],
                interval_days=0,
                force=True,
                dry_run=False,
                model="claude-sonnet-4-6",
            )
        )
        assert metrics["errors"] == 2
        assert metrics["refreshed"] == 0
        assert metrics["batch_id"] is None
