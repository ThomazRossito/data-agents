"""Tests for ui/exporter.py — export_html and export_markdown."""

from __future__ import annotations

import os


from ui.exporter import _strip_metrics, export_html, export_markdown


# ── Fixtures ──────────────────────────────────────────────────────────────────

HISTORY: list[dict] = [
    {
        "role": "user",
        "author": "Usuário",
        "content": "Qual a diferença entre Delta Lake e Iceberg?",
        "timestamp": "09/05/2026 10:00",
    },
    {
        "role": "assistant",
        "author": "Supervisor",
        "content": "## Delta Lake vs Iceberg\n\nAmbos são formatos de tabela open-source...\n\n```python\ndf.write.format('delta').save(path)\n```",
        "timestamp": "09/05/2026 10:00",
    },
]

HISTORY_WITH_METRICS: list[dict] = [
    {
        "role": "assistant",
        "author": "Supervisor",
        "content": "Resposta aqui.\n\n---\n*💰 `$0.0042` · 🔄 `3 turns` · ⏱️ `4.2s`*",
        "timestamp": "",
    },
]


# ── _strip_metrics ─────────────────────────────────────────────────────────────


class TestStripMetrics:
    def test_strips_cost_footer(self) -> None:
        content = "Conteúdo principal.\n\n---\n*💰 `$0.0042` · 🔄 `3 turns` · ⏱️ `4.2s`*"
        result = _strip_metrics(content)
        assert "💰" not in result
        assert "Conteúdo principal." in result

    def test_passthrough_no_metrics(self) -> None:
        content = "Texto sem métricas."
        assert _strip_metrics(content) == content

    def test_strips_multiline_footer(self) -> None:
        content = "Texto.\n\n---\n*💰 `$0.001` · 🔄 `1 turns` · ⏱️ `1.0s`*\n"
        result = _strip_metrics(content)
        assert "💰" not in result


# ── export_html ────────────────────────────────────────────────────────────────


class TestExportHtml:
    def test_returns_existing_html_file(self) -> None:
        path = export_html(HISTORY, title="Test Session")
        assert os.path.isfile(path)
        assert path.endswith(".html")

    def test_html_contains_title(self) -> None:
        path = export_html(HISTORY, title="Minha Sessão")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Minha Sessão" in content

    def test_html_contains_message_content(self) -> None:
        path = export_html(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Delta Lake" in content

    def test_html_strips_metrics(self) -> None:
        path = export_html(HISTORY_WITH_METRICS, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "💰" not in content

    def test_html_empty_history(self) -> None:
        path = export_html([], title="Vazio")
        assert os.path.isfile(path)

    def test_html_renders_code_block(self) -> None:
        path = export_html(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "<pre>" in content or "<code>" in content

    def test_html_message_count_in_badge(self) -> None:
        path = export_html(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "2 mensagens" in content


# ── export_markdown ───────────────────────────────────────────────────────────


class TestExportMarkdown:
    def test_returns_existing_md_file(self) -> None:
        path = export_markdown(HISTORY, title="Test Session")
        assert os.path.isfile(path)
        assert path.endswith(".md")

    def test_md_contains_title_heading(self) -> None:
        path = export_markdown(HISTORY, title="Minha Sessão")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "# Minha Sessão" in content

    def test_md_contains_message_content(self) -> None:
        path = export_markdown(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Delta Lake" in content

    def test_md_contains_author_headings(self) -> None:
        path = export_markdown(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "## 👤 Usuário" in content
        assert "## 🤖 Supervisor" in content

    def test_md_contains_timestamp(self) -> None:
        path = export_markdown(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "09/05/2026 10:00" in content

    def test_md_strips_metrics(self) -> None:
        path = export_markdown(HISTORY_WITH_METRICS, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "💰" not in content

    def test_md_empty_history(self) -> None:
        path = export_markdown([], title="Vazio")
        assert os.path.isfile(path)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "# Vazio" in content

    def test_md_message_count_in_header(self) -> None:
        path = export_markdown(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "2 mensagens" in content

    def test_md_horizontal_rules_between_messages(self) -> None:
        path = export_markdown(HISTORY, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert content.count("---") >= 3  # header separator + one per message

    def test_md_no_metrics_passthrough(self) -> None:
        history = [{"role": "user", "author": "User", "content": "Olá", "timestamp": ""}]
        path = export_markdown(history, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "Olá" in content

    def test_md_assistant_icon_for_unknown_role(self) -> None:
        history = [
            {"role": "system", "author": "Sistema", "content": "Configuração", "timestamp": ""}
        ]
        path = export_markdown(history, title="Test")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "🤖 Sistema" in content
