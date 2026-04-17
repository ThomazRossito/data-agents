"""
commands/monitor.py — Slash Commands do Business Monitor

Comandos disponíveis no chat:
  /monitor on          → ativa o ciclo automático
  /monitor off         → desativa o ciclo automático (daemon continua vivo)
  /monitor status      → estado atual + estatísticas do dia
  /monitor run         → dispara um ciclo imediatamente
  /monitor ask <texto> → pergunta interativa ao business-monitor sobre alertas recentes
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

logger = logging.getLogger("data_agents.commands.monitor")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = PROJECT_ROOT / "config" / "monitor_state.json"
OUTPUT_DIR = PROJECT_ROOT / "output"


# ── Helpers de Estado ──────────────────────────────────────────────────────


def _read_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enabled": True}


def _write_state(enabled: bool, reason: str = "", actor: str = "user") -> None:
    state = {
        "enabled": enabled,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": actor,
        "reason": reason,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Helpers de Relatório ───────────────────────────────────────────────────


def _load_today_alerts() -> list[dict]:
    """Carrega alertas e heartbeats do dia de hoje."""
    alerts_file = OUTPUT_DIR / f"monitor_alerts_{date.today().isoformat()}.jsonl"
    if not alerts_file.exists():
        return []
    entries = []
    for line in alerts_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def _load_recent_alerts(days: int = 7) -> list[dict]:
    """Carrega apenas os alertas (type=ALERT) dos últimos N dias."""
    all_alerts = []
    today = date.today()
    for i in range(days):
        target = today - timedelta(days=i)
        f = OUTPUT_DIR / f"monitor_alerts_{target.isoformat()}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "ALERT":
                    all_alerts.append(entry)
            except json.JSONDecodeError:
                pass
    return sorted(all_alerts, key=lambda x: x.get("timestamp", ""), reverse=True)


def _load_today_summary() -> dict | None:
    """Lê o último sumário de ciclo do dia."""
    summary_file = OUTPUT_DIR / f"monitor_summary_{date.today().isoformat()}.jsonl"
    if not summary_file.exists():
        return None
    lines = [line for line in summary_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except Exception:
        return None


# ── Handlers dos Comandos ─────────────────────────────────────────────────


def handle_monitor_on() -> str:
    _write_state(True, reason="ativado manualmente pelo usuário")
    return (
        "✅ **Business Monitor ATIVADO**\n\n"
        "O agent retomará o monitoramento no próximo ciclo programado.\n"
        "Se o daemon não estiver rodando, inicie com:\n"
        "```bash\npython scripts/monitor_daemon.py\n```"
    )


def handle_monitor_off() -> str:
    _write_state(False, reason="desativado manualmente pelo usuário")
    return (
        "⏸️ **Business Monitor DESATIVADO**\n\n"
        "O daemon continua ativo mas pulará todos os ciclos.\n"
        "Use `/monitor on` para reativar."
    )


def handle_monitor_status() -> str:
    state = _read_state()
    enabled = state.get("enabled", True)
    updated_at = state.get("updated_at", "—")
    updated_by = state.get("updated_by", "—")

    icon = "🟢" if enabled else "🔴"
    status_label = "ATIVO" if enabled else "DESATIVADO"

    # Estatísticas do dia
    today_entries = _load_today_alerts()
    alerts_today = [e for e in today_entries if e.get("type") == "ALERT"]
    ok_today = [e for e in today_entries if e.get("type") == "OK"]

    # Último sumário
    summary = _load_today_summary()
    last_cycle = "Nenhum ciclo executado hoje"
    if summary:
        last_cycle = summary.get("started_at", "—")

    # Próximo ciclo estimado
    try:
        pass  # type: ignore
    except Exception:
        pass

    lines = [
        f"## {icon} Business Monitor — {status_label}",
        "",
        f"**Última alteração:** {updated_at} (por: {updated_by})",
        f"**Último ciclo:** {last_cycle}",
        "",
        "### Resumo de Hoje",
        f"- Alertas emitidos: **{len(alerts_today)}**",
        f"- Verificações OK: **{len(ok_today)}**",
    ]

    if alerts_today:
        lines.append("")
        lines.append("### Alertas Recentes")
        for a in alerts_today[-5:]:
            sev = a.get("severity", "?")
            name = a.get("monitor", "?")
            ts = a.get("timestamp", "?")
            alert_id = a.get("alert_id", "?")
            lines.append(f"- `{ts}` [{sev}] **{name}** — `{alert_id}`")

    lines.extend(
        [
            "",
            "### Comandos Disponíveis",
            "```",
            "/monitor on       → reativar",
            "/monitor off      → pausar",
            "/monitor run      → ciclo imediato",
            "/monitor ask ...  → perguntar sobre um alerta",
            "```",
        ]
    )

    return "\n".join(lines)


PID_FILE = PROJECT_ROOT / "config" / "monitor_daemon.pid"


def handle_monitor_stop() -> str:
    """Para o daemon do Business Monitor lendo o PID salvo pelo start_chainlit.sh."""
    if not PID_FILE.exists():
        return (
            "ℹ️ **Nenhum daemon encontrado.**\n\n"
            "O Business Monitor não foi iniciado pelo `start_chainlit.sh`, "
            "ou já foi encerrado anteriormente."
        )

    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return "⚠️ Arquivo de PID inválido. Já foi limpo."

    import signal

    try:
        import os

        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink(missing_ok=True)
        _write_state(False, reason="daemon encerrado via /monitor stop", actor="user")
        return (
            f"🛑 **Business Monitor encerrado** (PID {pid}).\n\n"
            "Para reativar: reinicie com `./start_chainlit.sh` ou use `/monitor on` "
            "se o daemon já estiver rodando."
        )
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return (
            f"ℹ️ Processo {pid} não encontrado — o daemon já estava encerrado.\n"
            "Arquivo de PID removido."
        )
    except PermissionError:
        return f"❌ Sem permissão para encerrar o processo {pid}."


async def handle_monitor_run(console=None) -> str:
    """Dispara um ciclo imediato via subprocess para não bloquear o chat."""
    import subprocess
    import sys

    if console:
        console.print("[yellow]⏳ Disparando ciclo de monitoramento...[/yellow]")

    try:
        proc = subprocess.Popen(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "monitor_daemon.py"), "--once"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        stdout, _ = proc.communicate(timeout=120)
        if proc.returncode == 0:
            return f"✅ **Ciclo executado com sucesso.**\n\n```\n{stdout[-1000:]}\n```"
        else:
            return f"⚠️ **Ciclo concluído com erros.**\n\n```\n{stdout[-1000:]}\n```"
    except subprocess.TimeoutExpired:
        proc.kill()
        return "⚠️ Ciclo atingiu timeout de 120s. Verifique os logs em `output/`."
    except Exception as e:
        return f"❌ Erro ao executar ciclo: {e}"


async def handle_monitor_ask(question: str, console=None, client=None) -> str:
    """
    Roteia uma pergunta interativa ao business-monitor agent com contexto dos alertas recentes.

    O agent recebe:
      - Pergunta do usuário
      - Alertas dos últimos 7 dias (resumo)
      - Instrução para consultar dados ao vivo se necessário
    """
    recent = _load_recent_alerts(days=7)

    if not recent:
        context_block = "Não há alertas registrados nos últimos 7 dias."
    else:
        # Monta um resumo compacto para o context (máx 20 alertas)
        summary_lines = []
        for a in recent[:20]:
            summary_lines.append(
                f"- [{a.get('severity')}] {a.get('monitor')} | {a.get('timestamp')} | "
                f"ID: {a.get('alert_id')} | {a.get('records_affected', 0)} registro(s) | "
                f"{a.get('message', '')}"
            )
        context_block = "\n".join(summary_lines)

    prompt = (
        "Você é o business-monitor em modo interativo. O usuário recebeu alertas e "
        "quer tirar dúvidas sobre eles.\n\n"
        f"## Histórico de Alertas (últimos 7 dias)\n{context_block}\n\n"
        f"## Pergunta do Usuário\n{question}\n\n"
        "Instruções:\n"
        "1. Identifique qual alerta o usuário está referenciando (por nome, tabela ou contexto).\n"
        "2. Se necessário, consulte a tabela ao vivo via MCP para mostrar o estado atual.\n"
        "3. Explique a causa do alerta, o estado atual dos dados e a ação recomendada.\n"
        "4. Seja objetivo e direto — o usuário quer uma resposta de negócio, não técnica.\n"
        "5. Se não conseguir identificar o alerta, peça mais detalhes ao usuário."
    )

    # Executa via SDK apontando direto para o business-monitor
    try:
        from claude_agent_sdk import query, AssistantMessage, TextBlock, ResultMessage
        from agents.loader import load_agent_registry

        agents = load_agent_registry()
        monitor_agent = next((a for a in agents if a.name == "business-monitor"), None)

        if monitor_agent is None:
            return "❌ Agent business-monitor não encontrado no registry."

        response_text = ""
        async for event in query(prompt=prompt, options=monitor_agent):
            if isinstance(event, AssistantMessage):
                for block in event.content:
                    if isinstance(block, TextBlock):
                        response_text += block.text
            elif isinstance(event, ResultMessage):
                break

        return response_text or "O agent não retornou resposta."

    except Exception as e:
        logger.error(f"Erro ao consultar business-monitor: {e}")
        return f"❌ Erro ao consultar o monitor: {e}"


# ── Dispatcher Principal ───────────────────────────────────────────────────


async def run_monitor_command(args_str: str, console=None, client=None) -> str:
    """
    Entry point chamado pelo parser de comandos.

    Sintaxe: /monitor <subcommand> [argumentos]
    """
    parts = args_str.strip().split(None, 1)
    subcommand = parts[0].lower() if parts else "status"
    rest = parts[1].strip() if len(parts) > 1 else ""

    if subcommand == "on":
        return handle_monitor_on()
    elif subcommand == "off":
        return handle_monitor_off()
    elif subcommand == "stop":
        return handle_monitor_stop()
    elif subcommand == "status":
        return handle_monitor_status()
    elif subcommand == "run":
        return await handle_monitor_run(console=console)
    elif subcommand == "ask":
        if not rest:
            return "❓ Use: `/monitor ask <sua pergunta sobre o alerta>`"
        return await handle_monitor_ask(rest, console=console, client=client)
    else:
        return (
            "❓ **Subcomando desconhecido.**\n\n"
            "Comandos disponíveis:\n"
            "```\n"
            "/monitor on          → reativar ciclos automáticos\n"
            "/monitor off         → pausar ciclos (daemon continua vivo)\n"
            "/monitor stop        → encerrar o daemon completamente\n"
            "/monitor status      → ver estado e alertas do dia\n"
            "/monitor run         → executar ciclo imediato\n"
            "/monitor ask <texto> → perguntar sobre um alerta recebido\n"
            "```"
        )
