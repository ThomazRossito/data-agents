"""
monitor_daemon.py — Daemon do Business Monitor

Executa ciclos automáticos de monitoramento das 08h às 23h (configurável).
Lê monitor_state.json antes de cada ciclo — se disabled, pula sem executar.

Uso:
  python scripts/monitor_daemon.py           # inicia o daemon
  python scripts/monitor_daemon.py --once    # executa um único ciclo e sai
  python scripts/monitor_daemon.py --dry-run # mostra o que faria, sem executar SQLs

Controle em tempo real:
  Edite config/monitor_state.json ou use os slash commands no chat:
    /monitor on | /monitor off
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import yaml

# ── Garante que o root do projeto está no path ─────────────────────────────
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ── Força leitura do .env com python-dotenv (override=True) ───────────────
# Necessário porque start_chainlit.sh exporta env vars via bash, que não
# remove comentários inline (ex: SMTP_PASSWORD="xxx"  # comentário com ã).
# override=True garante que os valores do .env (parsed corretamente pelo
# python-dotenv) sobrescrevem os valores exportados pelo shell.
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=project_root / ".env", override=True)
except ImportError:
    pass  # python-dotenv não instalado — pydantic-settings usará os env vars do shell

from config.logging_config import setup_logging  # noqa: E402
from utils.monitor_alerter import emit_alert, emit_heartbeat  # noqa: E402

setup_logging()
logger = logging.getLogger("data_agents.monitor_daemon")

STATE_FILE = project_root / "config" / "monitor_state.json"
MANIFEST_FILE = project_root / "config" / "monitor_manifest.yaml"
SUMMARY_DIR = project_root / "output"
SUMMARY_DIR.mkdir(exist_ok=True)


# ── Estado ─────────────────────────────────────────────────────────────────


def read_state() -> dict:
    """Lê o estado atual do monitor (enabled/disabled)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enabled": True}


def write_state(enabled: bool, reason: str = "", actor: str = "daemon") -> None:
    """Persiste o estado do monitor."""
    state = {
        "enabled": enabled,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "updated_by": actor,
        "reason": reason,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Monitor state → enabled={enabled} (by={actor}, reason='{reason}')")


# ── Manifesto ──────────────────────────────────────────────────────────────


def load_manifest() -> dict:
    """Carrega e valida o manifesto de monitoramento."""
    if not MANIFEST_FILE.exists():
        logger.error(f"Manifesto não encontrado: {MANIFEST_FILE}")
        return {"global": {}, "monitors": []}
    with MANIFEST_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_within_schedule(manifest: dict) -> bool:
    """Verifica se o horário atual está dentro da janela de monitoramento."""
    from config.settings import settings  # importação local

    g = manifest.get("global", {})
    start_h = int(getattr(settings, "monitor_start_hour", g.get("start_hour", 8)))
    end_h = int(getattr(settings, "monitor_end_hour", g.get("end_hour", 23)))
    current_h = datetime.now().hour
    return start_h <= current_h < end_h


# ── Execução de um Monitor ─────────────────────────────────────────────────


async def run_single_monitor(monitor: dict, dry_run: bool = False) -> dict:
    """
    Executa a verificação de um único monitor.
    Retorna um dict com o resultado: {name, status, alert_id, records_affected, error}.
    """
    from config.settings import settings  # importação local

    name = monitor.get("name", "desconhecido")
    platform = monitor.get("platform", "databricks")
    table = monitor.get("table", "")
    check_sql = monitor.get("check_sql", "").strip()
    severity = monitor.get("severity", "MEDIA")
    message_template = monitor.get("message_template", "Anomalia detectada.")

    if not monitor.get("active", True):
        logger.debug(f"[{name}] Inativo — pulando.")
        return {"name": name, "status": "SKIPPED"}

    if dry_run:
        logger.info(f"[DRY-RUN] [{name}] Executaria SQL em {platform}:{table}")
        return {"name": name, "status": "DRY_RUN"}

    logger.info(f"[{name}] Iniciando verificação em {platform}:{table}")

    try:
        rows = await _execute_check(platform, check_sql, settings)
    except Exception as e:
        logger.error(f"[{name}] Erro ao executar check: {e}")
        return {"name": name, "status": "ERROR", "error": str(e)}

    if not rows:
        logger.info(f"[{name}] OK — sem anomalias.")
        emit_heartbeat(name, platform, table)
        return {"name": name, "status": "OK", "records_affected": 0}

    # Anomalia detectada
    count = len(rows)
    message = message_template.format(count=count, **rows[0]) if rows else message_template

    alert_id = emit_alert(
        monitor_name=name,
        severity=severity,
        platform=platform,
        table=table,
        message=message,
        records_affected=count,
        sample_data=rows[:10],
        check_sql=check_sql,
    )

    return {
        "name": name,
        "status": "ALERT",
        "alert_id": alert_id,
        "records_affected": count,
        "severity": severity,
    }


async def _execute_check(platform: str, sql: str, settings) -> list[dict]:
    """
    Executa o SQL de verificação na plataforma correta via MCP.
    Retorna lista de dicts com os registros problemáticos.

    NOTA: Em produção, esta função chama o MCP via claude_agent_sdk.
    Para testes locais sem MCP, retorna lista vazia (comportamento seguro).
    """
    try:
        if platform == "databricks":
            return await _run_databricks_sql(sql, settings)
        elif platform == "fabric_sql":
            return await _run_fabric_sql(sql, settings)
        else:
            logger.warning(f"Plataforma '{platform}' desconhecida — pulando.")
            return []
    except Exception as e:
        logger.error(f"Erro ao executar SQL em {platform}: {e}")
        raise


async def _run_databricks_sql(sql: str, settings) -> list[dict]:
    """Executa SQL no Databricks via SDK direto (sem passar pelo Supervisor)."""
    # Importação condicional — SDK pode não estar disponível em testes
    try:
        from databricks.sdk import WorkspaceClient

        client = WorkspaceClient(
            host=settings.databricks_host,
            token=settings.databricks_token,
        )
        # Usa Statement Execution API (synchronous)
        result = client.statement_execution.execute_statement(
            statement=sql,
            warehouse_id=settings.databricks_warehouse_id,
            wait_timeout="30s",
        )
        if result.status.state.value != "SUCCEEDED":
            raise RuntimeError(f"Databricks query failed: {result.status.error}")

        schema = [col.name for col in (result.manifest.schema.columns or [])]
        rows = []
        if result.result and result.result.data_array:
            for row in result.result.data_array:
                rows.append(dict(zip(schema, row)))
        return rows
    except ImportError:
        logger.warning("databricks-sdk não instalado — usando MCP agent fallback.")
        return await _run_via_agent(sql, "databricks")


async def _run_fabric_sql(sql: str, settings) -> list[dict]:
    """Executa T-SQL no Fabric SQL Endpoint via pyodbc/pymssql."""
    try:
        import pymssql  # type: ignore

        conn = pymssql.connect(
            server=settings.fabric_sql_server,
            user=settings.fabric_sql_user,
            password=settings.fabric_sql_password,
            database=settings.fabric_sql_database,
        )
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql)
        rows = cursor.fetchall()
        conn.close()
        return rows or []
    except ImportError:
        logger.warning("pymssql não instalado — usando MCP agent fallback.")
        return await _run_via_agent(sql, "fabric_sql")


async def _run_via_agent(sql: str, platform: str) -> list[dict]:
    """
    Fallback: executa o SQL através do business-monitor agent via SDK.
    Usado quando os SDKs nativos não estão disponíveis.
    """
    try:
        from claude_agent_sdk import query
        from agents.supervisor import build_supervisor_options

        prompt = (
            f"Execute este SQL no {platform} e retorne SOMENTE o resultado em JSON:\n"
            f"```sql\n{sql}\n```\n"
            f"Responda com um array JSON de objetos. Se não houver resultados, responda com []."
        )
        result_text = ""
        async for event in query(prompt=prompt, options=build_supervisor_options()):
            from claude_agent_sdk import AssistantMessage, TextBlock

            if isinstance(event, AssistantMessage):
                for block in event.content:
                    if isinstance(block, TextBlock):
                        result_text += block.text

        # Extrai JSON da resposta
        import re

        match = re.search(r"\[.*\]", result_text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return []
    except Exception as e:
        logger.error(f"Falha no agent fallback: {e}")
        return []


# ── Ciclo Principal ────────────────────────────────────────────────────────


async def run_monitor_cycle(dry_run: bool = False, ignore_schedule: bool = False) -> list[dict]:
    """Executa um ciclo completo: todos os monitores ativos do manifesto.

    Args:
        dry_run: Se True, mostra o que faria sem executar SQLs.
        ignore_schedule: Se True, ignora a janela de horário (usado por --once e /monitor run).
    """
    state = read_state()
    if not state.get("enabled", True):
        logger.info("Monitor DESATIVADO — ciclo cancelado. Use /monitor on para reativar.")
        return []

    manifest = load_manifest()

    if not ignore_schedule and not dry_run and not is_within_schedule(manifest):
        from config.settings import settings  # importação local

        g = manifest.get("global", {})
        start_h = int(getattr(settings, "monitor_start_hour", g.get("start_hour", 8)))
        end_h = int(getattr(settings, "monitor_end_hour", g.get("end_hour", 18)))
        logger.info(
            f"Fora da janela de monitoramento ({start_h}h–{end_h}h) — ciclo cancelado. "
            f"Use 'python scripts/monitor_daemon.py --once' para forçar fora do horário."
        )
        return []

    monitors = manifest.get("monitors", [])
    if not monitors:
        logger.warning("Nenhum monitor definido em monitor_manifest.yaml.")
        return []

    cycle_id = str(uuid.uuid4())[:8]
    started_at = datetime.now()
    logger.info(f"Iniciando ciclo {cycle_id} com {len(monitors)} monitor(es).")

    results = []
    for monitor in monitors:
        result = await run_single_monitor(monitor, dry_run=dry_run)
        results.append(result)

    # Salva sumário do ciclo
    summary = {
        "cycle_id": cycle_id,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "dry_run": dry_run,
        "results": results,
        "totals": {
            "ok": sum(1 for r in results if r.get("status") == "OK"),
            "alert": sum(1 for r in results if r.get("status") == "ALERT"),
            "error": sum(1 for r in results if r.get("status") == "ERROR"),
            "skipped": sum(1 for r in results if r.get("status") in ("SKIPPED", "DRY_RUN")),
        },
    }
    summary_file = SUMMARY_DIR / f"monitor_summary_{started_at.date().isoformat()}.jsonl"
    with summary_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")

    t = summary["totals"]
    logger.info(
        f"Ciclo {cycle_id} concluído — OK:{t['ok']} ALERT:{t['alert']} "
        f"ERROR:{t['error']} SKIP:{t['skipped']}"
    )
    return results


# ── Scheduler ─────────────────────────────────────────────────────────────


def start_daemon(dry_run: bool = False) -> None:
    """Inicia o daemon com APScheduler."""
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler não instalado. Execute: pip install apscheduler")
        sys.exit(1)

    manifest = load_manifest()
    g = manifest.get("global", {})
    interval = int(g.get("interval_minutes", 30))
    start_h = int(g.get("start_hour", 8))
    end_h = int(g.get("end_hour", 23))

    scheduler = BlockingScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        lambda: asyncio.run(run_monitor_cycle(dry_run=dry_run)),
        trigger=CronTrigger(
            hour=f"{start_h}-{end_h - 1}",
            minute=f"*/{interval}",
        ),
        id="business_monitor",
        name="Business Monitor Cycle",
        max_instances=1,  # nunca dois ciclos simultâneos
        coalesce=True,  # se atrasou, executa uma vez só
        misfire_grace_time=120,  # tolera até 2 min de atraso
    )

    logger.info(
        f"Business Monitor DAEMON iniciado — ciclos a cada {interval}min "
        f"({start_h}h–{end_h}h, America/Sao_Paulo)"
    )
    logger.info("Use /monitor off no chat ou Ctrl+C para parar.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Daemon interrompido pelo usuário.")


# ── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Business Monitor Daemon")
    parser.add_argument(
        "--once", action="store_true", help="Executa um único ciclo e sai (ignora horário)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostra o que faria sem executar SQLs"
    )
    args = parser.parse_args()

    if args.once or args.dry_run:
        results = asyncio.run(run_monitor_cycle(dry_run=args.dry_run, ignore_schedule=True))
        print(f"\nCiclo concluído: {len(results)} monitor(es) verificados.")
    else:
        start_daemon(dry_run=False)
