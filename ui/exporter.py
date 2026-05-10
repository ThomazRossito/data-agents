"""
ui/exporter.py — Export de histórico de chat para HTML.

Fluxo:
  1. Métricas de custo removidas do conteúdo
  2. markdown2 converte o conteúdo para HTML
  3. Template HTML com CSS profissional gera o .html

Para PDF: abrir o .html no browser e usar Cmd+P → Salvar como PDF.
O CSS inclui @media print para resultado profissional.

Uso:
    from ui.exporter import export_html

    html_path = export_html(history, title="Sessão Data Agents")
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from typing import Any

import markdown2


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _safe_filename(title: str) -> str:
    safe = re.sub(r"[^\w\-]", "_", title)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{safe}_{ts}"


def _strip_metrics(content: str) -> str:
    """Remove o rodapé de métricas de custo gerado pelo Supervisor/Dev Assistant.

    Remove padrão: ---\\n*💰 `$X.XXXX` · 🔄 `X turns` · ⏱️ `X.Xs`*
    """
    content = re.sub(
        r"\n\n---\n\*[💰🔄⏱️`$\d\.\s·turnscost]+.*?\*\s*$",
        "",
        content,
        flags=re.DOTALL,
    )
    # Fallback mais amplo: remove qualquer linha que contenha 💰
    content = re.sub(r"\n---\n\*.*?💰.*?\*", "", content, flags=re.DOTALL)
    return content.strip()


def _md_to_html(content: str) -> str:
    """Converte markdown para HTML usando markdown2 com extras."""
    return markdown2.markdown(
        content,
        extras=[
            "fenced-code-blocks",
            "tables",
            "strike",
            "task_list",
            "code-friendly",
            "break-on-newline",
        ],
    )


# ── Template HTML ─────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f8fafc;
      color: #1e293b;
      font-size: 14px;
      line-height: 1.6;
    }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      color: #fff;
      padding: 32px 40px 24px;
      border-bottom: 3px solid #3b82f6;
    }}
    .header h1 {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.3px;
      margin-bottom: 6px;
    }}
    .header .meta {{
      font-size: 12px;
      color: #94a3b8;
    }}
    .header .badge {{
      display: inline-block;
      background: #3b82f6;
      color: #fff;
      font-size: 11px;
      font-weight: 600;
      padding: 2px 10px;
      border-radius: 99px;
      margin-top: 8px;
    }}

    /* ── Container ── */
    .container {{
      max-width: 860px;
      margin: 0 auto;
      padding: 32px 24px;
    }}

    /* ── Mensagem ── */
    .message {{
      margin-bottom: 24px;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }}

    .message-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 16px;
      font-size: 12px;
      font-weight: 600;
    }}
    .message-header .author {{ font-size: 13px; }}
    .message-header .timestamp {{ color: #94a3b8; font-weight: 400; margin-left: auto; }}

    .message-body {{
      padding: 14px 18px;
    }}

    /* ── Usuário ── */
    .message.user .message-header {{
      background: #dbeafe;
      color: #1d4ed8;
    }}
    .message.user .message-body {{
      background: #eff6ff;
      color: #1e3a5f;
    }}

    /* ── Assistente ── */
    .message.assistant .message-header {{
      background: #dcfce7;
      color: #166534;
    }}
    .message.assistant .message-body {{
      background: #f0fdf4;
      color: #14532d;
    }}

    /* ── Markdown rendering ── */
    .message-body h1, .message-body h2, .message-body h3 {{
      margin: 14px 0 6px;
      font-weight: 700;
      line-height: 1.3;
    }}
    .message-body h1 {{ font-size: 18px; }}
    .message-body h2 {{ font-size: 16px; }}
    .message-body h3 {{ font-size: 14px; }}

    .message-body p {{ margin-bottom: 8px; }}

    .message-body ul, .message-body ol {{
      margin: 8px 0 8px 20px;
    }}
    .message-body li {{ margin-bottom: 4px; }}

    .message-body code {{
      font-family: "JetBrains Mono", "Fira Code", Menlo, Consolas, monospace;
      font-size: 12px;
      background: rgba(0,0,0,0.06);
      padding: 1px 5px;
      border-radius: 4px;
    }}

    .message-body pre {{
      background: #1e293b;
      color: #e2e8f0;
      border-radius: 8px;
      padding: 14px 16px;
      overflow-x: auto;
      margin: 10px 0;
      font-size: 12px;
      line-height: 1.5;
    }}
    .message-body pre code {{
      background: none;
      padding: 0;
      color: inherit;
      font-size: inherit;
    }}

    .message-body table {{
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      font-size: 13px;
    }}
    .message-body th {{
      background: #334155;
      color: #f1f5f9;
      padding: 8px 12px;
      text-align: left;
      font-weight: 600;
    }}
    .message-body td {{
      padding: 7px 12px;
      border-bottom: 1px solid #e2e8f0;
    }}
    .message-body tr:nth-child(even) td {{ background: rgba(0,0,0,0.02); }}

    .message-body blockquote {{
      border-left: 3px solid #94a3b8;
      padding-left: 12px;
      color: #64748b;
      margin: 8px 0;
    }}

    .message-body strong {{ font-weight: 700; }}
    .message-body em {{ font-style: italic; }}
    .message-body hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 12px 0; }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 24px;
      font-size: 11px;
      color: #94a3b8;
      border-top: 1px solid #e2e8f0;
      margin-top: 16px;
    }}

    /* ── Print / PDF ── */
    @media print {{
      body {{ background: #fff; }}
      .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      .message-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      .message-body pre {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      .message {{ page-break-inside: avoid; box-shadow: none; border: 1px solid #e2e8f0; }}
    }}
  </style>
</head>
<body>

  <div class="header">
    <h1>🤖 {title}</h1>
    <div class="meta">Exportado em {exported_at}</div>
    <div class="badge">{msg_count} mensagens</div>
  </div>

  <div class="container">
    {messages_html}
  </div>

  <div class="footer">
    Data Agents — Exportado em {exported_at}
  </div>

</body>
</html>"""


def _render_message(entry: dict[str, Any]) -> str:
    role = entry.get("role", "assistant")
    author = entry.get("author", "Assistente")
    content = _strip_metrics(entry.get("content", ""))
    timestamp = entry.get("timestamp", "")

    if role == "user":
        icon = "👤"
        css_class = "user"
    else:
        icon = "🤖"
        css_class = "assistant"

    body_html = _md_to_html(content)

    ts_html = f'<span class="timestamp">{timestamp}</span>' if timestamp else ""

    return f"""
    <div class="message {css_class}">
      <div class="message-header">
        <span>{icon}</span>
        <span class="author">{author}</span>
        {ts_html}
      </div>
      <div class="message-body">{body_html}</div>
    </div>"""


# ── Export HTML ───────────────────────────────────────────────────────────────


def export_html(
    chat_history: list[dict[str, Any]],
    title: str = "Data Agents — Sessão",
) -> str:
    """Gera arquivo .html com histórico renderizado. Retorna caminho absoluto."""
    messages_html = "\n".join(_render_message(e) for e in chat_history)

    html = _HTML_TEMPLATE.format(
        title=title,
        exported_at=_now_str(),
        msg_count=len(chat_history),
        messages_html=messages_html,
    )

    filename = _safe_filename(title) + ".html"
    path = os.path.join(tempfile.gettempdir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return path
