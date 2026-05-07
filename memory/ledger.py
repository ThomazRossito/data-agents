"""
Ledger — Camada de integridade e consulta sobre o audit log.

Responsabilidades:
  - Assinar entradas do audit log com HMAC-SHA256 (tamper-proof)
  - Verificar integridade de entradas assinadas
  - Consultar entradas por session_id (load_range)
  - Listar sessões registradas no audit log (list_sessions)

O arquivo de log (audit.jsonl) é append-only e gerenciado pelo audit_hook.
O Ledger não escreve diretamente — assina antes de gravar e consulta depois.

Fluxo de assinatura:
  session_lifecycle.on_session_start()
    → Ledger.generate_session_key()            # 32 bytes aleatórios por sessão
    → audit_hook.set_current_session(sid, key) # registra para uso nos hooks
  audit_hook.audit_tool_usage()
    → Ledger.sign_entry(entry, key)            # HMAC-SHA256 da entrada
    → grava entry + ledger_entry_hash no JSONL

Fluxo de verificação (opcional, via ledger_verify_on_load=True):
  Ledger.load_range(session_id)
    → lê audit.jsonl
    → Ledger.verify_entry(entry, key) por entrada
    → loga warning se hash inválido (tamper detectado)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from pathlib import Path
from typing import Any

logger = logging.getLogger("data_agents.memory.ledger")

# Nome do campo de hash nas entradas do log
_HASH_FIELD = "ledger_entry_hash"


class Ledger:
    """
    Integridade e consulta sobre o audit log append-only.

    Instanciar uma vez (em main.py ou supervisor.py).
    Usar generate_session_key() + audit_hook.set_current_session() no start.
    """

    def __init__(self, log_path: Path) -> None:
        self._log_path = log_path

    # ── Geração de chave ──────────────────────────────────────────────────────

    @staticmethod
    def generate_session_key() -> bytes:
        """Gera uma chave de sessão aleatória segura (32 bytes / 256 bits)."""
        return secrets.token_bytes(32)

    # ── Assinatura e verificação ──────────────────────────────────────────────

    def sign_entry(self, entry: dict[str, Any], session_key: bytes) -> str:
        """
        Gera HMAC-SHA256 de uma entrada de log.

        Serializa a entrada como JSON com chaves ordenadas, excluindo o campo
        ledger_entry_hash para evitar recursão. Garante determinismo entre
        plataformas com ensure_ascii=False + sort_keys=True.
        """
        entry_to_sign = {k: v for k, v in entry.items() if k != _HASH_FIELD}
        canonical = json.dumps(entry_to_sign, ensure_ascii=False, sort_keys=True)
        return hmac.new(session_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_entry(self, entry: dict[str, Any], session_key: bytes) -> bool:
        """
        Verifica integridade de uma entrada assinada.

        Retorna False se o campo ledger_entry_hash estiver ausente, vazio ou
        divergir do HMAC recalculado. Usa compare_digest para resistir a
        timing attacks.
        """
        stored_hash = entry.get(_HASH_FIELD, "")
        if not stored_hash:
            return False
        expected = self.sign_entry(entry, session_key)
        return hmac.compare_digest(stored_hash, expected)

    # ── Consulta ──────────────────────────────────────────────────────────────

    def load_range(
        self,
        session_id: str,
        verify: bool = False,
        session_key: bytes | None = None,
    ) -> list[dict[str, Any]]:
        """
        Carrega todas as entradas do audit log para um session_id específico.

        Args:
            session_id: ID da sessão a consultar.
            verify: Se True, verifica HMAC de cada entrada e loga warnings
                    para entradas com hash inválido. Requer session_key.
            session_key: Chave da sessão para verificação (só usada se verify=True).

        Returns:
            Lista de entries em ordem cronológica. Vazia se sessão não existir.
            Linhas malformadas são ignoradas silenciosamente.
        """
        if not self._log_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        tampered_count = 0

        try:
            with open(self._log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("session_id") != session_id:
                            continue
                        if verify and session_key:
                            if not self.verify_entry(entry, session_key):
                                tampered_count += 1
                                logger.warning(
                                    f"Ledger: entrada com hash inválido detectada "
                                    f"(tool={entry.get('tool_name')}, "
                                    f"id={entry.get('tool_use_id')})"
                                )
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            logger.warning(f"Ledger.load_range: erro ao ler {self._log_path}: {e}")

        if tampered_count:
            logger.error(
                f"Ledger: {tampered_count} entrada(s) com tamper detectado na sessão {session_id!r}"
            )

        return entries

    def list_sessions(self) -> list[str]:
        """
        Retorna session_ids únicos registrados no audit log.

        Mantém ordem de primeira aparição. Entradas sem session_id são ignoradas.
        Retorna lista vazia se o arquivo não existir.
        """
        if not self._log_path.exists():
            return []

        seen: set[str] = set()
        sessions: list[str] = []

        try:
            with open(self._log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        sid = entry.get("session_id")
                        if sid and sid not in seen:
                            seen.add(sid)
                            sessions.append(sid)
                    except json.JSONDecodeError:
                        continue
        except OSError as e:
            logger.warning(f"Ledger.list_sessions: erro ao ler {self._log_path}: {e}")

        return sessions
