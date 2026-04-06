"""
Configuração de logging estruturado para o Data Agents.

Implementa:
  - Console handler com Rich formatting para desenvolvimento
  - JSONL file handler para produção/auditoria
  - Separação por nível: INFO+ no console, DEBUG+ no arquivo
  - Rotação automática de logs por tamanho

Uso:
    from config.logging_config import setup_logging
    setup_logging()  # Chamar uma vez no startup
"""

import logging
import logging.handlers
import os
import sys
from typing import Any

try:
    from rich.logging import RichHandler

    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


class JSONLFormatter(logging.Formatter):
    """
    Formatter que produz uma linha JSON por entry de log.
    Compatível com sistemas de observabilidade (Datadog, Splunk, Azure Monitor).
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_dict: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Adicionar exception info se presente
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        # Adicionar campos extras customizados
        for key in ("tool_name", "platform", "tool_use_id", "operation_type"):
            if hasattr(record, key):
                log_dict[key] = getattr(record, key)

        return json.dumps(log_dict, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    log_file: str = "./logs/app.jsonl",
    enable_console: bool = True,
    enable_file: bool = True,
) -> None:
    """
    Configura o sistema de logging do Data Agents.

    Args:
        log_level: Nível mínimo para o console (DEBUG, INFO, WARNING, ERROR).
        log_file: Caminho para o arquivo JSONL de log persistente.
        enable_console: Se True, ativa handler de console (Rich ou padrão).
        enable_file: Se True, ativa handler de arquivo JSONL.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Captura tudo; filtro nos handlers

    # Limpar handlers existentes para evitar duplicatas
    root_logger.handlers.clear()

    # ─── Console Handler ─────────────────────────────────────────
    if enable_console:
        console_handler: logging.Handler
        if _RICH_AVAILABLE:
            console_handler = RichHandler(
                level=getattr(logging, log_level.upper(), logging.INFO),
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
            )
        else:
            sh = logging.StreamHandler(sys.stdout)
            sh.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
            console_handler = sh

        root_logger.addHandler(console_handler)

    # ─── File Handler (JSONL) ─────────────────────────────────────
    if enable_file and log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)

            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(JSONLFormatter())
            root_logger.addHandler(file_handler)

        except OSError as e:
            # Não bloquear startup se o arquivo de log não puder ser criado
            logging.getLogger("data_agents.config").warning(
                f"Não foi possível criar handler de arquivo de log em {log_file}: {e}"
            )

    # Silenciar loggers verbosos de dependências
    for noisy_logger in ("httpx", "httpcore", "asyncio", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    logging.getLogger("data_agents").info(
        f"Logging configurado: level={log_level}, file={log_file if enable_file else 'desabilitado'}"
    )
