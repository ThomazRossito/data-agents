"""Modelos de dados do protocolo QA."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field


def parse_json_from_llm(text: str) -> dict:
    """Extrai JSON de resposta LLM — suporta markdown code blocks e prefixos livres."""
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


@dataclass
class TaskSpec:
    task_id: str
    objective: str
    deliverables: list[str]
    acceptance_criteria: list[str]
    agent_name: str
    risks: list[str]
    version: int = 1

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:8]

    def to_json_str(self) -> str:
        return json.dumps(
            {
                "task_id": self.task_id,
                "objective": self.objective,
                "deliverables": self.deliverables,
                "acceptance_criteria": self.acceptance_criteria,
                "agent_name": self.agent_name,
                "risks": self.risks,
                "version": self.version,
            },
            ensure_ascii=False,
            indent=2,
        )


@dataclass
class ReviewResult:
    decision: str  # "APPROVE" | "REQUEST_CHANGES"
    feedback: str
    proposed_additions: list[str] = field(default_factory=list)


@dataclass
class DeliveryResult:
    task_id: str
    spec_version: int
    content: str
    tool_calls_count: int
    tokens_used: int


@dataclass
class ScoreReport:
    task_id: str
    score: float
    passed: bool
    criteria_results: list[dict]
    issues: list[str]
    recommendations: list[str]

    def summary(self, threshold: float = 0.7) -> str:
        icon = "✅" if self.passed else "❌"
        lines = [
            f"### {icon} QA Score: {self.score:.0%}",
            f"Threshold: {threshold:.0%} | {'PASSOU' if self.passed else 'FALHOU'}",
        ]
        if self.criteria_results:
            lines.append("\n**Critérios:**")
            for c in self.criteria_results:
                ok = "✅" if c.get("passed") else "❌"
                lines.append(
                    f"- {ok} {c.get('criterion', '')} — {c.get('evidence', '')}"
                )
        if self.issues:
            lines.append("\n**Issues:**")
            for issue in self.issues:
                lines.append(f"- ⚠️ {issue}")
        if self.recommendations:
            lines.append("\n**Recomendações:**")
            for rec in self.recommendations:
                lines.append(f"- 💡 {rec}")
        return "\n".join(lines)
