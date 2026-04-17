"""
Memory Store — CRUD de memórias em arquivos Markdown.

Armazena cada memória como um arquivo .md individual em:
  memory/data/{type}/{id}.md

Estrutura:
  memory/data/
  ├── user/          # Preferências do usuário
  ├── feedback/      # Correções e orientações
  ├── architecture/  # Decisões e padrões
  ├── progress/      # Estado de tarefas
  └── daily/         # Logs diários brutos (antes da compilação)

O index.md é gerado pelo compiler e fica em memory/data/index.md.
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.types import Memory, MemoryType

logger = logging.getLogger("data_agents.memory.store")

# Diretório base dos dados de memória
_DEFAULT_DATA_DIR = Path(__file__).parent.parent / "memory" / "data"


def _atomic_write(path: Path, content: str) -> None:
    """Escreve conteúdo de forma atômica usando arquivo temporário + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)  # atomic no mesmo filesystem


class MemoryStore:
    """
    Gerencia a persistência de memórias em arquivos Markdown.

    Cada memória é um arquivo .md com frontmatter YAML + conteúdo.
    O store é thread-safe para operações de leitura (escrita é sequencial).
    """

    def __init__(self, data_dir: Path | str | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else _DEFAULT_DATA_DIR
        self._lock = threading.Lock()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Cria a estrutura de diretórios se não existir."""
        for mem_type in MemoryType:
            (self.data_dir / mem_type.value).mkdir(parents=True, exist_ok=True)
        (self.data_dir / "daily").mkdir(parents=True, exist_ok=True)

    def _memory_path(self, memory: Memory) -> Path:
        """Retorna o caminho do arquivo para uma memória."""
        return self.data_dir / memory.type.value / f"{memory.id}.md"

    # ─── CRUD ─────────────────────────────────────────────────────

    def save(self, memory: Memory) -> Path:
        """
        Salva uma memória em arquivo Markdown (atomic write + thread-safe).

        Se o arquivo já existir, sobrescreve (update).
        Atualiza o updated_at automaticamente.
        """
        memory.updated_at = datetime.now(timezone.utc)
        path = self._memory_path(memory)

        with self._lock:
            try:
                _atomic_write(path, memory.to_markdown())
                logger.debug(f"Memória salva: {memory.id} ({memory.type.value}) → {path}")
            except OSError as e:
                logger.error(f"Erro ao salvar memória {memory.id}: {e}")
                raise

        return path

    def load(self, memory_id: str, memory_type: MemoryType) -> Memory | None:
        """Carrega uma memória específica por ID e tipo."""
        path = self.data_dir / memory_type.value / f"{memory_id}.md"
        if not path.exists():
            return None
        return self._parse_memory_file(path)

    def delete(self, memory_id: str, memory_type: MemoryType) -> bool:
        """Remove uma memória (hard delete). Retorna True se removeu."""
        path = self.data_dir / memory_type.value / f"{memory_id}.md"
        if path.exists():
            try:
                os.remove(path)
                logger.info(f"Memória removida: {memory_id} ({memory_type.value})")
                return True
            except OSError as e:
                logger.error(f"Erro ao remover memória {memory_id}: {e}")
        return False

    def supersede(self, old_id: str, old_type: MemoryType, new_memory: Memory) -> Memory:
        """
        Marca uma memória como substituída e salva a nova.

        A memória antiga recebe superseded_by = new_memory.id e confidence = 0.
        A nova memória recebe related_ids = [old_id].
        """
        old = self.load(old_id, old_type)
        if old:
            old.superseded_by = new_memory.id
            old.confidence = 0.0
            self.save(old)

        if old_id not in new_memory.related_ids:
            new_memory.related_ids.append(old_id)
        self.save(new_memory)

        logger.info(f"Memória {old_id} substituída por {new_memory.id}")
        return new_memory

    # ─── Queries ──────────────────────────────────────────────────

    def list_all(
        self,
        memory_type: MemoryType | None = None,
        active_only: bool = True,
        min_confidence: float = 0.1,
    ) -> list[Memory]:
        """
        Lista memórias, opcionalmente filtradas por tipo e status.

        Args:
            memory_type: Se fornecido, filtra por tipo. None = todos os tipos.
            active_only: Se True, exclui memórias superseded e com baixa confidence.
            min_confidence: Threshold mínimo de confidence.
        """
        memories: list[Memory] = []
        types = [memory_type] if memory_type else list(MemoryType)

        for mt in types:
            type_dir = self.data_dir / mt.value
            if not type_dir.exists():
                continue

            for path in sorted(type_dir.glob("*.md")):
                mem = self._parse_memory_file(path)
                if mem is None:
                    continue
                if active_only and not mem.is_active(min_confidence):
                    continue
                memories.append(mem)

        return memories

    def list_by_tags(self, tags: list[str], match_all: bool = False) -> list[Memory]:
        """
        Busca memórias por tags.

        Args:
            tags: Tags para buscar.
            match_all: Se True, memória deve ter TODAS as tags. Se False, qualquer uma.
        """
        all_memories = self.list_all(active_only=True)
        results: list[Memory] = []

        for mem in all_memories:
            mem_tags = set(mem.tags)
            search_tags = set(tags)
            if match_all:
                if search_tags.issubset(mem_tags):
                    results.append(mem)
            else:
                if search_tags & mem_tags:
                    results.append(mem)

        return results

    def get_stale_memories(
        self,
        threshold: float = 0.1,
        memory_type: MemoryType | None = None,
    ) -> list[Memory]:
        """
        Retorna memórias cuja confidence decaída está abaixo do threshold (Ch. 11).

        Inclui apenas tipos com decay (PROGRESS, FEEDBACK).
        USER e ARCHITECTURE são ignorados pois nunca decaem.

        Args:
            threshold: Threshold de confidence. Padrão 0.1 (nível de expiração).
            memory_type: Filtra por tipo específico. None = todos os tipos com decay.

        Returns:
            Lista de memórias stale (não supersedidas, confidence decaída < threshold).
        """
        from memory.decay import compute_decayed_confidence
        from memory.types import DECAY_CONFIG

        now = datetime.now(timezone.utc)
        all_memories = self.list_all(
            memory_type=memory_type,
            active_only=False,
            min_confidence=0.0,
        )

        stale: list[Memory] = []
        for mem in all_memories:
            if mem.superseded_by is not None:
                continue
            # Ignora tipos sem decay
            if DECAY_CONFIG.get(mem.type) is None:
                continue

            current_conf = compute_decayed_confidence(mem, now)
            if current_conf < threshold:
                stale.append(mem)

        return stale

    def prune_stale_memories(
        self,
        threshold: float = 0.1,
        dry_run: bool = False,
    ) -> list[Memory]:
        """
        Remove memórias cuja confidence decaída está abaixo do threshold (Ch. 11).

        Args:
            threshold: Threshold de confidence para considerar memória stale.
            dry_run: Se True, apenas identifica as memórias sem remover.

        Returns:
            Lista de memórias que foram (ou seriam no dry_run) removidas.
        """
        stale = self.get_stale_memories(threshold=threshold)

        if not dry_run:
            for mem in stale:
                self.delete(mem.id, mem.type)
                logger.info(
                    f"Memória stale removida: {mem.id} ({mem.type.value}) conf={mem.confidence:.3f}"
                )
            if stale:
                logger.info(
                    f"Poda concluída: {len(stale)} memórias removidas (threshold={threshold})"
                )
        else:
            logger.info(
                f"Dry run: {len(stale)} memórias stale encontradas "
                f"(threshold={threshold}) — nenhuma removida."
            )

        return stale

    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do store."""
        stats: dict[str, Any] = {"total": 0, "by_type": {}, "active": 0, "superseded": 0}

        for mt in MemoryType:
            all_of_type = self.list_all(memory_type=mt, active_only=False)
            active = [m for m in all_of_type if m.is_active()]
            stats["by_type"][mt.value] = {
                "total": len(all_of_type),
                "active": len(active),
            }
            stats["total"] += len(all_of_type)
            stats["active"] += len(active)
            stats["superseded"] += len(all_of_type) - len(active)

        return stats

    # ─── Daily Logs ───────────────────────────────────────────────

    def append_daily_log(self, content: str, date: datetime | None = None) -> Path:
        """
        Appenda conteúdo ao log diário (daily/{YYYY-MM-DD}.md).

        Daily logs são o buffer bruto antes da compilação.
        O compiler processa esses logs e gera knowledge articles.
        """
        dt = date or datetime.now(timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        path = self.data_dir / "daily" / f"{date_str}.md"

        header = ""
        if not path.exists():
            header = f"# Daily Log — {date_str}\n\n"

        with self._lock:
            try:
                # Se o arquivo já existe e tem marcador COMPILED, remove-o antes de
                # appender — novo conteúdo significa que o log precisa ser recompilado.
                existing = ""
                if path.exists():
                    existing = path.read_text(encoding="utf-8")
                    if "<!-- COMPILED" in existing:
                        import re as _re

                        existing = _re.sub(r"\s*<!-- COMPILED[^>]*-->\s*$", "", existing)
                        _atomic_write(path, existing)
                        logger.debug(f"Marcador COMPILED removido de {date_str} (novo conteúdo)")

                with open(path, "a", encoding="utf-8") as f:
                    if header:
                        f.write(header)
                    f.write(f"\n---\n\n{content}\n")
                logger.debug(f"Daily log atualizado: {date_str} (+{len(content)} chars)")
            except OSError as e:
                logger.error(f"Erro ao escrever daily log: {e}")

        return path

    def list_daily_logs(self, unprocessed_only: bool = False) -> list[Path]:
        """Lista todos os daily logs, opcionalmente apenas os não processados."""
        daily_dir = self.data_dir / "daily"
        if not daily_dir.exists():
            return []

        logs = sorted(daily_dir.glob("*.md"))

        if unprocessed_only:
            # Logs processados têm um marcador no final
            unprocessed: list[Path] = []
            for log_path in logs:
                content = log_path.read_text(encoding="utf-8")
                if "<!-- COMPILED" not in content:
                    unprocessed.append(log_path)
            return unprocessed

        return logs

    # ─── Index ────────────────────────────────────────────────────

    def build_index(self) -> str:
        """
        Gera o index.md com resumos de todas as memórias ativas.

        Este index é lido pelo Sonnet lateral durante o retrieval.
        Formato compacto: uma linha por memória para maximizar a
        quantidade de context que o modelo consegue processar.
        """
        lines: list[str] = [
            "# Memory Index",
            "",
            f"*Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
            "",
        ]

        for mt in MemoryType:
            memories = self.list_all(memory_type=mt, active_only=True)
            if not memories:
                continue

            lines.append(f"## {mt.value.upper()} ({len(memories)})")
            lines.append("")

            for mem in sorted(memories, key=lambda m: m.confidence, reverse=True):
                tags_str = f" [{', '.join(mem.tags)}]" if mem.tags else ""
                conf_str = f" (conf={mem.confidence:.2f})" if mem.confidence < 1.0 else ""
                lines.append(f"- **{mem.id}**: {mem.summary}{tags_str}{conf_str}")

            lines.append("")

        index_content = "\n".join(lines)

        # Salva o index.md (atomic write para evitar leitura parcial durante retrieval)
        index_path = self.data_dir / "index.md"
        with self._lock:
            try:
                _atomic_write(index_path, index_content)
                logger.info(f"Index gerado: {len(lines)} linhas → {index_path}")
            except OSError as e:
                logger.error(f"Erro ao gerar index: {e}")

        return index_content

    # ─── Internal ─────────────────────────────────────────────────

    def _parse_memory_file(self, path: Path) -> Memory | None:
        """Parse de um arquivo .md com frontmatter YAML para Memory."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Erro ao ler {path}: {e}")
            return None

        try:
            from utils.frontmatter import parse_yaml_frontmatter

            metadata, body = parse_yaml_frontmatter(content)
        except ValueError:
            logger.warning(f"Arquivo sem frontmatter válido: {path}")
            return None

        metadata["content"] = body
        return Memory.from_dict(metadata)
