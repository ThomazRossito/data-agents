"""QAOrchestrator — peer agent independente para contrato, execução e score."""

from __future__ import annotations

import logging
import re

from agents.base import AgentResult, BaseAgent
from orchestrator.models import (
    DeliveryResult,
    ReviewResult,
    ScoreReport,
    TaskSpec,
    parse_json_from_llm,
)

logger = logging.getLogger("data_agents.qa_orchestrator")

# Comandos que não produzem entregáveis verificáveis — bypass do protocolo QA
_BYPASS_COMMANDS = frozenset(
    {"/health", "/help", "/sessions", "/resume", "/kg", "/party", "/assessment"}
)
_NON_WORK_RE = re.compile(r"^(help|ajuda)$", re.IGNORECASE)


def should_bypass(user_input: str) -> bool:
    parts = user_input.strip().split(maxsplit=1)
    if not parts:
        return True
    cmd = parts[0].lower()
    return cmd in _BYPASS_COMMANDS or bool(_NON_WORK_RE.match(user_input.strip()))


class QAOrchestrator:
    """Coordena o protocolo Spec→Negociação→Execução→Score.

    O supervisor não sabe que está sendo avaliado durante a execução (fase 3):
    `execute()` chama `supervisor.route()` sem modificações, garantindo
    independência entre executor e avaliador.
    """

    def __init__(
        self,
        supervisor,
        qa_agent: BaseAgent,
        max_rounds: int = 3,
        pass_threshold: float = 0.7,
    ) -> None:
        self._supervisor = supervisor
        self._qa_agent = qa_agent
        self._max_rounds = max_rounds
        self._pass_threshold = pass_threshold

    # ── Public API ───────────────────────────────────────────────────────────

    def handle(self, user_input: str) -> tuple[AgentResult, ScoreReport | None]:
        """Ponto de entrada. Retorna (result, score_report | None).

        Soma tokens de todas as fases (negotiate + execute + verify) para
        auditoria fiel ao custo real do protocolo QA.
        """
        if should_bypass(user_input):
            return self._supervisor.route(user_input), None
        spec, _, neg_tokens, neg_calls = self.negotiate_spec(user_input)
        delivery = self.execute(user_input, spec)
        report, ver_tokens, ver_calls = self.verify(spec, delivery)
        total_tokens = neg_tokens + delivery.tokens_used + ver_tokens
        total_calls = neg_calls + delivery.tool_calls_count + ver_calls
        return (
            AgentResult(
                content=delivery.content,
                tool_calls_count=total_calls,
                tokens_used=total_tokens,
            ),
            report,
        )

    def negotiate_spec(
        self, user_input: str
    ) -> tuple[TaskSpec, int, int, int]:
        """Fase 1+2: draft + loop de revisão.

        Retorna (spec_final, rounds_usados, tokens_consumidos, tool_calls).
        """
        spec, draft_tokens, draft_calls = self._supervisor.draft_spec(user_input)
        total_tokens = draft_tokens
        total_calls = draft_calls
        for round_num in range(1, self._max_rounds + 1):
            review, r_tokens, r_calls = self._review_spec(spec)
            total_tokens += r_tokens
            total_calls += r_calls
            logger.info(
                "[QA round %d/%d] decision=%s spec_v%d",
                round_num,
                self._max_rounds,
                review.decision,
                spec.version,
            )
            if review.decision == "APPROVE":
                return spec, round_num, total_tokens, total_calls
            spec, rev_tokens, rev_calls = self._supervisor.revise_spec(
                spec, review.feedback, review.proposed_additions
            )
            total_tokens += rev_tokens
            total_calls += rev_calls
        logger.warning(
            "QA max_rounds=%d atingido — prosseguindo com spec v%d",
            self._max_rounds,
            spec.version,
        )
        return spec, self._max_rounds, total_tokens, total_calls

    def execute(self, user_input: str, spec: TaskSpec) -> DeliveryResult:
        """Fase 3: executa via agente acordado na spec, não via supervisor.route().

        Honra o contrato negociado em vez de re-rotear (que ignoraria spec).
        Fallback para supervisor.route() apenas se agent_name não for válido.
        """
        agent = self._supervisor.get_agent(spec.agent_name)
        if agent is None:
            logger.warning(
                "QA.execute: agent '%s' inválido na spec, fallback para supervisor.route()",
                spec.agent_name,
            )
            result = self._supervisor.route(user_input)
        else:
            spec_context = (
                f"## Spec acordada (QA round)\n{spec.to_json_str()}\n\n"
                "Atenda às acceptance_criteria acima."
            )
            result = agent.run(user_input, context=spec_context)
        return DeliveryResult(
            task_id=spec.task_id,
            spec_version=spec.version,
            content=result.content,
            tool_calls_count=result.tool_calls_count,
            tokens_used=result.tokens_used,
        )

    def verify(
        self, spec: TaskSpec, delivery: DeliveryResult
    ) -> tuple[ScoreReport, int, int]:
        """Fase 4: QA agent avalia entrega contra critérios da spec.

        Retorna (report, tokens_consumidos, tool_calls).
        Fail-closed: parse falhou ou criteria_results vazio → score=0.0, passed=False.
        """
        prompt = (
            "Avalie cada critério de aceitação com base EXCLUSIVAMENTE no "
            "conteúdo entregue abaixo. Retorne APENAS JSON, sem texto adicional.\n\n"
            f"## TaskSpec\n{spec.to_json_str()}\n\n"
            f"## Conteúdo Entregue\n{delivery.content[:4000]}\n\n"
            "Formato esperado:\n"
            '{"criteria_results": [{"criterion": "...", "passed": true, '
            '"evidence": "trecho ou observação"}], '
            '"issues": ["..."], "recommendations": ["..."]}'
        )
        result = self._qa_agent.run(prompt, json_mode=True)
        data = parse_json_from_llm(result.content)
        criteria = data.get("criteria_results", [])
        if not criteria:
            logger.warning(
                "QA.verify: criteria_results vazio (parse falhou?) — fail-closed"
            )
            score = 0.0
        else:
            score = sum(1 for c in criteria if c.get("passed")) / len(criteria)
        report = ScoreReport(
            task_id=spec.task_id,
            score=score,
            passed=score >= self._pass_threshold and bool(criteria),
            criteria_results=criteria,
            issues=data.get("issues", []),
            recommendations=data.get("recommendations", []),
        )
        return report, result.tokens_used, result.tool_calls_count

    # ── Internal ─────────────────────────────────────────────────────────────

    def _review_spec(self, spec: TaskSpec) -> tuple[ReviewResult, int, int]:
        prompt = (
            "Revise a spec de tarefa abaixo e retorne APENAS JSON.\n\n"
            f"## TaskSpec\n{spec.to_json_str()}\n\n"
            "Formato esperado:\n"
            '{"decision": "APPROVE" | "REQUEST_CHANGES", '
            '"feedback": "justificativa", "proposed_additions": ["..."]}'
        )
        result = self._qa_agent.run(prompt, json_mode=True)
        data = parse_json_from_llm(result.content)
        # Fail-closed: parse falhou → REQUEST_CHANGES (não aprova por omissão)
        decision = data.get("decision")
        if decision not in ("APPROVE", "REQUEST_CHANGES"):
            logger.warning(
                "QA._review_spec: decision inválida ou ausente — REQUEST_CHANGES"
            )
            decision = "REQUEST_CHANGES"
        review = ReviewResult(
            decision=decision,
            feedback=data.get("feedback", ""),
            proposed_additions=data.get("proposed_additions", []),
        )
        return review, result.tokens_used, result.tool_calls_count
