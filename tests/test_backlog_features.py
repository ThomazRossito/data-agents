"""
Testes para as 4 features do backlog:
1. Structured output (json_mode) em BaseAgent.run()
2. Class-level skill cache em BaseAgent
3. fail_fast em execute_workflow
4. run_query_routed + run_all_routed no evals runner
"""
from __future__ import annotations

from unittest.mock import MagicMock

from agents.base import AgentConfig, AgentResult, BaseAgent
from workflow.dag import WorkflowDef, WorkflowStep
from workflow.executor import execute_workflow

# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_agent(name: str, content: str = "ok", tokens: int = 5) -> BaseAgent:
    agent = MagicMock(spec=BaseAgent)
    agent.config = AgentConfig(name=name, tier="T2", system_prompt="mock")
    agent.run.return_value = AgentResult(content=content, tool_calls_count=0, tokens_used=tokens)
    return agent


def _make_step(agent_name: str, key: str, desc: str = "step") -> WorkflowStep:
    return WorkflowStep(agent_name=agent_name, description=desc, output_key=key)


def _make_workflow(steps: list[WorkflowStep]) -> WorkflowDef:
    return WorkflowDef(id="WF-T", name="Teste", steps=steps, trigger_description="t")


# ── 1. json_mode em BaseAgent.run() ─────────────────────────────────────────

class TestJsonMode:
    def _make_real_agent(self) -> BaseAgent:
        cfg = AgentConfig(name="test_agent", tier="T3", system_prompt="sys", skills=[])
        return BaseAgent(cfg)

    def test_json_mode_adds_response_format(self, monkeypatch):
        """Quando json_mode=True, response_format deve ser passado para a API."""
        agent = self._make_real_agent()

        captured_kwargs: dict = {}

        fake_response = MagicMock()
        fake_response.choices[0].message.tool_calls = None
        fake_response.choices[0].message.content = '{"result": "ok"}'
        fake_response.usage.total_tokens = 10

        def fake_create(**kwargs):
            captured_kwargs.update(kwargs)
            return fake_response

        monkeypatch.setattr(
            "config.settings.settings.copilot_client.chat.completions.create",
            fake_create,
        )

        agent.run("tarefa", json_mode=True)

        assert "response_format" in captured_kwargs
        assert captured_kwargs["response_format"] == {"type": "json_object"}

    def test_json_mode_false_no_response_format(self, monkeypatch):
        """Quando json_mode=False (padrão), response_format não deve aparecer."""
        agent = self._make_real_agent()
        captured_kwargs: dict = {}

        fake_response = MagicMock()
        fake_response.choices[0].message.tool_calls = None
        fake_response.choices[0].message.content = "texto"
        fake_response.usage.total_tokens = 5

        def fake_create(**kwargs):
            captured_kwargs.update(kwargs)
            return fake_response

        monkeypatch.setattr(
            "config.settings.settings.copilot_client.chat.completions.create",
            fake_create,
        )

        agent.run("tarefa")

        assert "response_format" not in captured_kwargs


# ── 2. Class-level skill cache ───────────────────────────────────────────────

class TestClassLevelSkillCache:
    def setup_method(self):
        # Limpar o cache entre testes
        BaseAgent._CLASS_SKILL_CACHE.clear()

    def test_class_cache_shared_between_instances(self, tmp_path, monkeypatch):
        """Duas instâncias diferentes devem compartilhar o mesmo cache."""
        monkeypatch.setattr("agents.base.SKILLS_DIR", tmp_path)
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("conteúdo da skill")

        cfg = AgentConfig(name="a", tier="T3", system_prompt="s", skills=["my_skill"])
        agent1 = BaseAgent(cfg)
        agent2 = BaseAgent(cfg)

        # Primeira leitura via agent1 — deve ler do disco
        content1 = agent1._load_skill("my_skill")
        assert content1 == "conteúdo da skill"
        assert "my_skill" in BaseAgent._CLASS_SKILL_CACHE

        # Segunda leitura via agent2 — deve vir do cache (sem IO)
        content2 = agent2._load_skill("my_skill")
        assert content2 == content1

    def test_class_cache_not_duplicated_on_retry(self, tmp_path, monkeypatch):
        """A mesma instância não deve recarregar skill já cacheada."""
        monkeypatch.setattr("agents.base.SKILLS_DIR", tmp_path)
        skill_dir = tmp_path / "sk2"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("v1")

        cfg = AgentConfig(name="b", tier="T3", system_prompt="s", skills=["sk2"])
        agent = BaseAgent(cfg)
        agent._load_skill("sk2")

        # Alterar arquivo no disco — não deve afetar resultado (está cacheado)
        skill_file.write_text("v2")
        assert agent._load_skill("sk2") == "v1"

    def test_missing_skill_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("agents.base.SKILLS_DIR", tmp_path)
        cfg = AgentConfig(name="c", tier="T3", system_prompt="s")
        agent = BaseAgent(cfg)
        result = agent._load_skill("nao_existe")
        assert result == ""


# ── 3. fail_fast em execute_workflow ────────────────────────────────────────

class TestFailFast:
    def test_fail_fast_stops_on_first_error(self, tmp_path, monkeypatch):
        """fail_fast=True: retorna resultado parcial na primeira exception."""
        monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

        step1 = _make_step("ok_agent", "s1")
        step2 = _make_step("bad_agent", "s2")
        step3 = _make_step("ok_agent", "s3")
        wf = _make_workflow([step1, step2, step3])

        ok_agent = _make_agent("ok_agent", "resultado ok")
        bad_agent = _make_agent("bad_agent")
        bad_agent.run.side_effect = RuntimeError("falhou!")
        fallback = _make_agent("fallback")

        result = execute_workflow(
            wf, "task", {"ok_agent": ok_agent, "bad_agent": bad_agent}, fallback,
            fail_fast=True,
        )

        assert "fail_fast=True" in result.content or "falhou!" in result.content
        # Etapa 3 não deve ter sido chamada
        assert ok_agent.run.call_count == 1

    def test_fail_fast_false_continues_on_error(self, tmp_path, monkeypatch):
        """fail_fast=False: continua após exception, registra erro no step."""
        monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

        step1 = _make_step("ok_agent", "s1")
        step2 = _make_step("bad_agent", "s2")
        step3 = _make_step("ok_agent", "s3")
        wf = _make_workflow([step1, step2, step3])

        ok_agent = _make_agent("ok_agent", "ok")
        bad_agent = _make_agent("bad_agent")
        bad_agent.run.side_effect = RuntimeError("crash!")
        fallback = _make_agent("fallback")

        result = execute_workflow(
            wf, "task", {"ok_agent": ok_agent, "bad_agent": bad_agent}, fallback,
            fail_fast=False,
        )

        # ok_agent chamado nas etapas 1 e 3
        assert ok_agent.run.call_count == 2
        assert "crash!" in result.content or "ERRO" in result.content

    def test_no_error_behavior_unchanged(self, tmp_path, monkeypatch):
        """Sem erros, fail_fast não altera o comportamento existente."""
        monkeypatch.setattr("workflow.executor.OUTPUT_DIR", tmp_path)

        steps = [_make_step("a", f"s{i}") for i in range(3)]
        wf = _make_workflow(steps)
        agent = _make_agent("a", "ok")
        fallback = _make_agent("fallback")

        result = execute_workflow(wf, "task", {"a": agent}, fallback, fail_fast=True)

        assert agent.run.call_count == 3
        assert isinstance(result, AgentResult)


# ── 4. run_query_routed + --use-supervisor no CLI de evals ──────────────────

class TestEvalsRouted:
    def _make_supervisor_mock(self, content: str = "resposta") -> MagicMock:
        sup = MagicMock()
        sup.route.return_value = AgentResult(
            content=content, tool_calls_count=0, tokens_used=20
        )
        return sup

    def test_run_query_routed_passes(self):
        from evals.runner import Query, Rubric, run_query_routed

        query = Query(
            id="q1",
            domain="conceptual",
            prompt="explique delta",
            rubric=Rubric(must_include=["resposta"], min_length=5),
        )
        sup = self._make_supervisor_mock("essa é a resposta")
        result = run_query_routed(query, sup)

        assert result.passed
        assert result.cost_tokens == 20
        sup.route.assert_called_once_with("explique delta")

    def test_run_query_routed_fails_rubric(self):
        from evals.runner import Query, Rubric, run_query_routed

        query = Query(
            id="q2",
            domain="sql",
            prompt="o que é CTE?",
            rubric=Rubric(must_include=["common table expression"]),
        )
        sup = self._make_supervisor_mock("uma junção de tabelas")
        result = run_query_routed(query, sup)

        assert not result.passed
        assert result.score < 1.0

    def test_run_query_routed_exception(self):
        from evals.runner import Query, Rubric, run_query_routed

        query = Query(id="q3", domain="x", prompt="p", rubric=Rubric())
        sup = MagicMock()
        sup.route.side_effect = RuntimeError("boom")
        result = run_query_routed(query, sup)

        assert result.score == 0.0
        assert any("RuntimeError" in f for f in result.failures)

    def test_run_all_routed(self):
        from evals.runner import Query, Rubric, run_all_routed

        queries = [
            Query(id=f"q{i}", domain="d", prompt="p", rubric=Rubric(min_length=1))
            for i in range(3)
        ]
        sup = self._make_supervisor_mock("ok")
        results = run_all_routed(queries, sup)

        assert len(results) == 3
        assert sup.route.call_count == 3

    def test_main_use_supervisor_flag_dry_run(self):
        """--use-supervisor + --dry-run retorna 0 sem instanciar Supervisor."""
        from evals.runner import main
        # dry-run retorna antes de instanciar Supervisor; só valida YAML
        ret = main(["--use-supervisor", "--dry-run"])
        assert ret == 0

    def test_main_default_uses_geral_agent(self, monkeypatch):
        """Sem --use-supervisor, usa agente geral (dry-run)."""
        from evals.runner import main
        ret = main(["--dry-run"])
        assert ret == 0
