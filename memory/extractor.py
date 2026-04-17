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

# Confidence por tipo de memória: USER/ARCHITECTURE têm alta confiança por serem
# declarativos; PROGRESS/PIPELINE_STATUS são mais transitórios e menos confiáveis.
_TYPE_CONFIDENCE: dict[str, float] = {
    "user": 0.95,
    "architecture": 0.95,
    "data_asset": 0.90,
    "feedback": 0.90,
    "platform_decision": 0.85,
    "progress": 0.75,
    "pipeline_status": 0.70,
}

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

3. **architecture** — Decisões arquiteturais, padrões, gotchas, regras de negócio gerais.
   Exemplos: "pipeline usa Medallion com 3 camadas", "tabela X tem schema drift frequente"

4. **progress** — Estado atual de tarefas, milestones atingidos, contexto de sessão.
   Exemplos: "pipeline de ingestão Bronze está pronto", "falta criar tabela Gold"

5. **data_asset** — Ativos de dados: tabelas, views, schemas, pipelines, datasets e suas características.
   Use quando há informações específicas sobre estrutura ou conteúdo de dados.
   Exemplos: "tabela silver_vendas tem colunas [id, data, valor, cliente_id]",
   "lakehouse TARN_LH_DEV contém schemas bronze, silver e gold",
   "coluna cpf na tabela clientes é dado PII"

6. **platform_decision** — Decisões sobre plataformas e tecnologias de dados.
   Use quando o usuário escolhe entre opções de tecnologia para um caso de uso específico.
   Exemplos: "Auto Loader escolhido para ingestão incremental (melhor que COPY INTO para streaming)",
   "Fabric escolhido para relatórios Power BI (Databricks para processamento Spark)"

7. **pipeline_status** — Estado atual de execução de pipelines, jobs e workflows de dados.
   Use para status operacional que muda com frequência (decai em 14 dias).
   Exemplos: "job de sync Fabric falhando há 2 dias (erro de permissão)",
   "backfill da camada Silver em andamento, 60% concluído"

Para cada extração, retorne:
- type: um dos 7 tipos acima
- summary: resumo de 1 linha (para o index)
- content: descrição completa (2-5 linhas)
- tags: 2-5 tags relevantes

Retorne SOMENTE um JSON array de objetos. Sem markdown, sem explicação.
Se não houver nada para extrair, retorne [].

Exemplo:
[
  {
    "type": "data_asset",
    "summary": "Tabela silver_vendas com schema definido no projeto HERON",
    "content": "A tabela silver_vendas contém as colunas: id (bigint), data_venda (date), valor (decimal), cliente_id (bigint), produto_id (bigint). Particionada por data_venda. Localizada no lakehouse TARN_LH_DEV, schema silver.",
    "tags": ["silver", "vendas", "lakehouse", "schema"]
  },
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
            "model": settings.memory_extractor_model,
            "max_tokens": settings.memory_extractor_max_tokens,
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

            base_confidence = _TYPE_CONFIDENCE.get(mem_type_str, 0.80)
            # Penaliza levemente memórias com conteúdo muito curto (< 30 chars)
            content = ext.get("content", "")
            if len(content) < 30:
                base_confidence = max(0.50, base_confidence - 0.15)

            mem = Memory(
                type=mem_type,
                content=content,
                summary=ext.get("summary", ""),
                tags=ext.get("tags", []),
                confidence=base_confidence,
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
