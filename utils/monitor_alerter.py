"""
monitor_alerter.py — Engine de Alertas do Business Monitor

Responsável por:
  1. Log estruturado (console + arquivo)
  2. Persistência em JSONL (output/monitor_alerts_YYYY-MM-DD.jsonl)
  3. Envio de email HTML via SMTP
  4. Geração de Alert IDs rastreáveis

O contexto de cada alerta é persistido no JSONL para que o business-monitor
possa recuperá-lo durante conversas interativas do usuário no chat.
"""

import hashlib
import json
import logging
import smtplib
from datetime import datetime, date
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

logger = logging.getLogger("data_agents.monitor_alerter")

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

SEVERITY_EMOJI = {
    "CRITICA": "🚨",
    "ALTA": "⚠️",
    "MEDIA": "🔶",
    "BAIXA": "🔵",
}

SEVERITY_COLOR = {
    "CRITICA": "#dc2626",
    "ALTA": "#ea580c",
    "MEDIA": "#d97706",
    "BAIXA": "#2563eb",
}


def generate_alert_id(monitor_name: str) -> str:
    """Gera um Alert ID único e rastreável: alert_YYYYMMDD_HHMMSS_hash6."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    h = hashlib.md5(f"{monitor_name}{ts}".encode(), usedforsecurity=False).hexdigest()[:6]  # noqa: S324
    return f"alert_{ts}_{h}"


def get_alerts_file(target_date: date | None = None) -> Path:
    """Retorna o caminho do arquivo JSONL de alertas para a data alvo."""
    d = target_date or date.today()
    return OUTPUT_DIR / f"monitor_alerts_{d.isoformat()}.jsonl"


def emit_alert(
    monitor_name: str,
    severity: str,
    platform: str,
    table: str,
    message: str,
    records_affected: int,
    sample_data: list[dict[str, Any]],
    check_sql: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Emite um alerta completo pelos três canais: log, JSONL e email.

    Retorna o alert_id gerado.
    """
    alert_id = generate_alert_id(monitor_name)
    ts = datetime.now().isoformat(timespec="seconds")
    emoji = SEVERITY_EMOJI.get(severity, "🔔")

    payload = {
        "alert_id": alert_id,
        "timestamp": ts,
        "type": "ALERT",
        "monitor": monitor_name,
        "severity": severity,
        "platform": platform,
        "table": table,
        "message": message,
        "records_affected": records_affected,
        "sample": sample_data,
        "check_sql": check_sql,
        **(extra or {}),
    }

    # ── Canal 1: Log estruturado ──────────────────────────────────────────────
    log_level = (
        logging.CRITICAL
        if severity == "CRITICA"
        else (logging.ERROR if severity == "ALTA" else logging.WARNING)
    )
    logger.log(
        log_level,
        f"{emoji} [{severity}] {monitor_name} | {table} | {records_affected} registro(s) | {alert_id}",
        extra={"alert_payload": payload},
    )

    # Console legível
    sep = "━" * 55
    print(f"\n{sep}")
    print(f"{emoji} [{severity}] {monitor_name}")
    print(f"   Tabela:    {table}")
    print(f"   Plataforma: {platform}")
    print(f"   Mensagem:  {message}")
    print(f"   Afetados:  {records_affected} registro(s)")
    print(f"   Alert ID:  {alert_id}")
    print(f"   Timestamp: {ts}")
    if sample_data:
        print("   Amostra:")
        for row in sample_data[:5]:
            print(f"     {row}")
    print(sep)

    # ── Canal 2: JSONL ────────────────────────────────────────────────────────
    alerts_file = get_alerts_file()
    with alerts_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    logger.debug(f"Alerta persistido em {alerts_file}")

    # ── Canal 3: Email ────────────────────────────────────────────────────────
    try:
        sent = _send_email(payload)
        if not sent:
            logger.info(
                "Email não enviado — SMTP não configurado. "
                "Preencha SMTP_HOST, SMTP_USER, SMTP_PASSWORD e MONITOR_ALERT_EMAIL_TO no .env"
            )
    except Exception as e:
        import traceback

        logger.warning(
            f"Falha ao enviar email para alerta {alert_id}: {e}\n{traceback.format_exc()}"
        )

    return alert_id


def emit_heartbeat(monitor_name: str, platform: str, table: str) -> None:
    """Registra um ciclo OK no JSONL (sem alerta)."""
    payload = {
        "alert_id": None,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "type": "OK",
        "monitor": monitor_name,
        "platform": platform,
        "table": table,
    }
    alerts_file = get_alerts_file()
    with alerts_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_recent_alerts(days: int = 7) -> list[dict[str, Any]]:
    """
    Carrega alertas dos últimos N dias a partir dos arquivos JSONL.
    Usado pelo business-monitor em modo interativo para recuperar contexto.
    """
    from datetime import timedelta

    alerts = []
    today = date.today()
    for i in range(days):
        target = today - timedelta(days=i)
        f = get_alerts_file(target)
        if f.exists():
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "ALERT":
                        alerts.append(entry)
                except json.JSONDecodeError:
                    pass
    return sorted(alerts, key=lambda x: x.get("timestamp", ""), reverse=True)


def _send_email(payload: dict[str, Any]) -> bool:
    """Envia email HTML via SMTP com o conteúdo do alerta. Retorna True se enviado."""
    from config.settings import settings  # importação local — evita circular import

    smtp_host = getattr(settings, "smtp_host", "")
    smtp_port = int(getattr(settings, "smtp_port", 587))
    smtp_user = getattr(settings, "smtp_user", "")
    # Remove espaços e strip comentário inline caso o dotenv não tenha removido
    smtp_password = getattr(settings, "smtp_password", "")
    smtp_password = smtp_password.split("#")[0].strip().replace(" ", "")
    to_email = getattr(settings, "monitor_alert_email_to", "")

    if not all([smtp_host, smtp_user, smtp_password, to_email]):
        return False  # não configurado

    severity = payload["severity"]
    color = SEVERITY_COLOR.get(severity, "#374151")
    emoji = SEVERITY_EMOJI.get(severity, "🔔")

    sample_rows = ""
    for row in payload.get("sample", [])[:10]:
        cells = "".join(
            f"<td style='padding:4px 8px;border:1px solid #e5e7eb'>{v}</td>" for v in row.values()
        )
        sample_rows += f"<tr>{cells}</tr>"

    sample_headers = ""
    if payload.get("sample"):
        sample_headers = "".join(
            f"<th style='padding:4px 8px;background:#f3f4f6;border:1px solid #e5e7eb'>{k}</th>"
            for k in payload["sample"][0].keys()
        )

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f9fafb;padding:24px">
<div style="max-width:640px;margin:auto;background:#fff;border-radius:8px;
            border-top:4px solid {color};box-shadow:0 1px 4px rgba(0,0,0,0.08)">

  <div style="padding:24px 28px 16px">
    <h2 style="margin:0;color:{color};font-size:18px">
      {emoji} [{severity}] {payload["monitor"]}
    </h2>
    <p style="color:#6b7280;font-size:13px;margin:4px 0 0">
      {payload["timestamp"]} &nbsp;|&nbsp; Alert ID: <code>{payload["alert_id"]}</code>
    </p>
  </div>

  <div style="padding:0 28px 20px">
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <tr>
        <td style="padding:6px 0;color:#6b7280;width:120px">Plataforma</td>
        <td style="padding:6px 0;font-weight:500">{payload["platform"]}</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#6b7280">Tabela</td>
        <td style="padding:6px 0;font-family:monospace;font-size:13px">{payload["table"]}</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#6b7280">Registros</td>
        <td style="padding:6px 0;font-weight:500">{payload["records_affected"]} afetado(s)</td>
      </tr>
      <tr>
        <td style="padding:6px 0;color:#6b7280">Mensagem</td>
        <td style="padding:6px 0">{payload["message"]}</td>
      </tr>
    </table>
  </div>

  {"<div style='padding:0 28px 20px'><p style='font-size:13px;color:#374151;margin:0 0 8px'><strong>Amostra de dados:</strong></p><table style='border-collapse:collapse;font-size:12px;width:100%'><thead><tr>" + sample_headers + "</tr></thead><tbody>" + sample_rows + "</tbody></table></div>" if payload.get("sample") else ""}

  <div style="padding:16px 28px;background:#f9fafb;border-top:1px solid #e5e7eb;
              border-radius:0 0 8px 8px;font-size:12px;color:#9ca3af">
    Responda a este alerta no chat: <strong>/monitor ask [sua pergunta]</strong>
  </div>
</div>
</body>
</html>
"""

    subject = f"[{severity}] {payload['monitor']} - {payload['records_affected']} registro(s)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")  # Header() encoda non-ASCII corretamente
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg.attach(MIMEText(html.encode("utf-8"), "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_bytes())  # as_bytes() resolve o ascii error

    logger.info(f"Email enviado para {to_email} | Alert ID: {payload['alert_id']}")
    return True
