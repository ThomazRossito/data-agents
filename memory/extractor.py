"""
Memory Extractor — Extrai memórias de conversas via Sonnet.

Após cada sessão (ou periodicamente durante a sessão), o extractor
analisa a conversa e identifica informações que devem ser memorizadas.

O extractor produz "raw extractions" que vão para o daily log.
O compiler depois organiza essas extrações em knowledge articles.

Categorias de extração:
  - Decisões tomadas (→ ARCHITECTURE)
  - Padrões descobertos (→ ARCHITECTURE)
  - Preferências expressas pelo usuário (→ USER)
  - Correções feitas pelo usuário (→ FEEDBACK)
  - Contexto de progresso (→ PROGRESS)
"""

from __future__ import annotations

import json
import logging
import urllib.request
from datetime import datetime, timezone

from memory.types import Memory, MemoryType
from config.settings import settings

logger = logging.getLogger("data_agents.memory.extractor")

_EXTRACTOR_MODEL = "claude-sonnet-4-6"
_EXTRACTOR_MAX_TOKENS = 2048

_EXTRACTOR_SYSTEM_PROMPT = """\
Você é um sistema de extração de memórias. Sua tarefa é analisar uma conversa entre
um usuário e um sistema de agentes de dados, e extrair informações que devem ser
memorizadas para sessões futuras.

Extraia APENAS informações que seriam valiosas em sessões futuras. Ignore detalhes
efêmeros como erros temporários ou tentativas de debug.

Categorias de extração (taxonomia fechada — use EXATAMENTE estes tipos):

1. **user** — Preferências, papel, expertise, estilo de comunicação do usuário.
   Exemplos: "usuário prefere código comentado em português", "trabalha com Databricks e Fabric"

2. **feedback** — Correções e orientações dadas pelo usuário ao sistema.
   Exemplos: "usuário pediu para não usar SELECT *", "prefere Delta Lake sobre Parquet"

3. **architecture** — Decisões arquiteturais, padrões, gotchas, regras de negócio.
   Exemplos: "pipeline usa Medallion com 3 camadas", "tabela X tem schema drift frequente"

4. **progress** — Estado atual de tarefas, milestones atingidos.
   Exemplos: "pipeline de ingestão Bronze está pronto", "falta criar tabela Gold"

Para cada extração, retorne:
- type: um dos 4 tipos acima
- summary: resumo de 1 linha (para o index)
- content: descrição completa (2-5 linhas)
- tags: 2-5 tags relevantes

Retorne SOMENTE um JSON array de objetos. Sem markdown, sem explicação.
Se não houver nada para extrair, retorne [].

Exemplo:
[
  {
    "type": "architecture",
    "summary": "Pipeline Medallion usa Auto Loader na camada Bronze",
    "content": "O pipeline de ingestão foi configurado com Auto Loader (cloudFiles) na Bronze para processar arquivos JSON do blob storage. Formato: Delta. Particionamento por data.",
    "tags": ["pipeline", "bronze", "auto-loader", "delta"]
  }
]
"""


def extract_memories_from_conversation(
    conversation_text: str,
    session_id: str = "",
    existing_summaries: list[str] | None = None,
) -> list[Memory]:
    """
    Extrai memórias de um texto de conversa via Sonnet.

    Args:
        conversation_text: Texto da conversa (user + assistant messages).
        session_id: ID da sessão para rastreabilidade.
        existing_summaries: Resumos de memórias existentes (para evitar duplicatas).

    Returns:
        Lista de Memory objects extraídos.
    """
    if not conversation_text.strip():
        return []

    # Limita o texto de conversa para não exceder o contexto
    max_chars = 50000
    if len(conversation_text) > max_chars:
        conversation_text = (
            conversation_text[: max_chars // 2]
            + "\n\n[...TRUNCADO...]\n\n"
            + conversation_text[-max_chars // 2 :]
        )

    user_message = f"## Conversa para Análise\n\n{conversation_text}"

    if existing_summaries:
        dedup_section = "\n\n## Memórias Já Existentes (evite duplicatas)\n\n" + "\n".join(
            f"- {s}" for s in existing_summaries[:50]
        )
        user_message += dedup_section

    payload = json.dumps(
        {
            "model": _EXTRACTOR_MODEL,
            "max_tokens": _EXTRACTOR_MAX_TOKENS,
            "system": _EXTRACTOR_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "User-Agent": "data-agents/1.0 memory-extractor",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310
            data = json.loads(resp.read().decode("utf-8"))

        text = data["content"][0]["text"] if data.get("content") else "[]"

        # Log de custo
        usage = data.get("usage", {})
        input_tok = usage.get("input_tokens", 0)
        output_tok = usage.get("output_tokens", 0)
        cost = (input_tok * 3.00 + output_tok * 15.00) / 1_000_000
        logger.info(f"Extração: {input_tok} in / {output_tok} out = ${cost:.5f}")

        # Parse da resposta
        text = text.strip()
        # Remove markdown code fences se presentes
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        extractions = json.loads(text)
        if not isinstance(extractions, list):
            logger.warning(f"Resposta do extractor não é lista: {text[:100]}")
            return []

        # Converte para Memory objects
        memories: list[Memory] = []
        now = datetime.now(timezone.utc)

        for ext in extractions:
            if not isinstance(ext, dict):
                continue

            mem_type_str = ext.get("type", "progress")
            try:
                mem_type = MemoryType(mem_type_str)
            except ValueError:
                logger.warning(f"Tipo de memória inválido ignorado: {mem_type_str}")
                continue

            mem = Memory(
                type=mem_type,
                content=ext.get("content", ""),
                summary=ext.get("summary", ""),
                tags=ext.get("tags", []),
                confidence=1.0,
                created_at=now,
                updated_at=now,
                source_session=session_id,
            )
            memories.append(mem)

        logger.info(f"Extraídas {len(memories)} memórias da sessão {session_id}")
        return memories

    except json.JSONDecodeError as e:
        logger.error(f"Erro ao parsear resposta do extractor: {e}")
        return []
    except Exception as e:
        logger.error(f"Erro no extractor: {e}")
        return []
