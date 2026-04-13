"""
Memory Module — Sistema de Memória Persistente sem Banco de Dados

Implementa memória baseada em arquivos Markdown com retrieval via LLM lateral (Sonnet).
Inspirado na arquitetura claude-memory-compiler (Karpathy/Cole Medin).

Quatro tipos de memória com taxonomia fechada:
  - USER: preferências, papel, estilo de comunicação (nunca decai)
  - FEEDBACK: correções e orientações dadas pelo usuário (decay lento: 90 dias)
  - ARCHITECTURE: decisões arquiteturais, padrões, gotchas (nunca decai)
  - PROGRESS: estado atual de tarefas, contexto de sessão (decay rápido: 7 dias)

Pipeline:
  Sessão → memory_hook captura → extractor.flush() → daily logs
  → compiler.compile() → knowledge articles + index.md
  → retrieval.query() (Sonnet lateral) → contexto injetado no prompt
"""

from memory.types import Memory, MemoryType
from memory.store import MemoryStore
from memory.retrieval import retrieve_relevant_memories
from memory.extractor import extract_memories_from_conversation
from memory.compiler import compile_daily_logs
from memory.decay import apply_decay
from memory.lint import lint_memories

__all__ = [
    "Memory",
    "MemoryType",
    "MemoryStore",
    "retrieve_relevant_memories",
    "extract_memories_from_conversation",
    "compile_daily_logs",
    "apply_decay",
    "lint_memories",
]
