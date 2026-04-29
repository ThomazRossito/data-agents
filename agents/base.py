"""Base agent class — executa loop agentico via GitHub Copilot API."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from config.settings import settings

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent.parent / "skills" / "skills"


@dataclass
class AgentConfig:
    name: str
    tier: str
    system_prompt: str
    skills: list[str] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    kb_domains: list[str] = field(default_factory=list)
    model: str | None = None  # override do tier; quando None, usa settings.tier_model_map[tier]


@dataclass
class AgentResult:
    content: str
    tool_calls_count: int
    tokens_used: int


class BaseAgent:
    # Cache compartilhado entre todas as instâncias — leitura de disco por skill, não por agente
    _CLASS_SKILL_CACHE: dict[str, str] = {}

    def __init__(self, config: AgentConfig):
        self.config = config
        # Frontmatter `model:` vence `tier_model_map`; tier é o fallback.
        self.model = config.model or settings.model_for_tier(config.tier)
        self.max_turns = settings.turns_for_tier(config.tier)

    def _load_skill(self, skill_name: str) -> str:
        if skill_name in BaseAgent._CLASS_SKILL_CACHE:
            return BaseAgent._CLASS_SKILL_CACHE[skill_name]
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            content = skill_path.read_text()
            BaseAgent._CLASS_SKILL_CACHE[skill_name] = content
            return content
        logger.warning("Skill '%s' não encontrada em %s", skill_name, SKILLS_DIR)
        return ""

    def _build_system(self) -> str:
        parts = [self.config.system_prompt]
        for skill in self.config.skills:
            content = self._load_skill(skill)
            if content:
                parts.append(f"\n\n---\n## Skill: {skill}\n{content}")
        return "\n".join(parts)

    def run(self, task: str, context: str = "", json_mode: bool = False) -> AgentResult:
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self._build_system()},
        ]
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": task})

        total_tokens = 0
        total_tool_calls = 0

        for turn in range(self.max_turns):
            kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
            if self.config.tools:
                kwargs["tools"] = self.config.tools
                kwargs["tool_choice"] = "auto"
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = settings.copilot_client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            total_tokens += response.usage.total_tokens if response.usage else 0

            if msg.tool_calls:
                total_tool_calls += len(msg.tool_calls)
                messages.append(msg)
                for tc in msg.tool_calls:
                    result = self._dispatch_tool(tc.function.name, tc.function.arguments)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })
            else:
                return AgentResult(
                    content=msg.content or "",
                    tool_calls_count=total_tool_calls,
                    tokens_used=total_tokens,
                )

        return AgentResult(
            content=messages[-1].get("content", "Max turns reached."),
            tool_calls_count=total_tool_calls,
            tokens_used=total_tokens,
        )

    def _dispatch_tool(self, name: str, arguments: str) -> str:
        """Roteia tool calls para agents/tools (databricks, fabric)."""
        from agents.tools import dispatch_tool
        args_parsed = json.loads(arguments)
        logger.debug("Tool call: %s(%s)", name, args_parsed)
        return dispatch_tool(name, args_parsed)
