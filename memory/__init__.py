"""
Memory Module — Sistema de Memória Persistente Multi-Camada

Arquitetura de 3 camadas:
  ShortTermMemory  — SQLite TTL buffer (captura da sessão atual, 3 dias)
  LongTermMemory   — SQLite FTS5 + embeddings opcionais (persistente, sem TTL)
  Ledger           — Audit log HMAC-SHA256 append-only (integridade)

Tipos de memória com taxonomia fechada (7 tipos, decay por tipo):
  USER, FEEDBACK, ARCHITECTURE, PROGRESS,
  DATA_ASSET, PLATFORM_DECISION, PIPELINE_STATUS

Pipeline:
  Sessão → memory_hook captura → ShortTermMemory (SQLite)
  → flush → extractor (Haiku) → daily logs
  → compiler → MemoryStore (arquivos .md) + LongTermMemory (índice FTS5)
  → MemoryManager.inject_context() → contexto injetado no prompt do Supervisor
"""

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.retrieval import retrieve_relevant_memories, format_memories_for_injection
from memory.extractor import extract_memories_from_conversation
from memory.compiler import compile_daily_logs
from memory.decay import apply_decay
from memory.lint import lint_memories
from memory.manager import MemoryManager
from memory.ledger import Ledger
from memory.short_term import ShortTermMemory
from memory.long_term import LongTermMemory

__all__ = [
    "Memory",
    "MemoryType",
    "MemoryStore",
    "MemoryManager",
    "Ledger",
    "ShortTermMemory",
    "LongTermMemory",
    "retrieve_relevant_memories",
    "format_memories_for_injection",
    "extract_memories_from_conversation",
    "compile_daily_logs",
    "apply_decay",
    "lint_memories",
]
