"""Tests for Context and InvocationContext."""

import pytest

from soulbot.agents import (
    CallbackContext,
    Context,
    InvocationContext,
    ReadonlyContext,
    RunConfig,
    ToolContext,
)
from soulbot.sessions import Session


class TestRunConfig:
    def test_defaults(self):
        rc = RunConfig()
        assert rc.max_llm_calls == 50
        assert rc.streaming is False
        assert rc.response_modality == "text"

    def test_custom(self):
        rc = RunConfig(max_llm_calls=10, streaming=True)
        assert rc.max_llm_calls == 10
        assert rc.streaming is True


class TestInvocationContext:
    def _make_ctx(self, **kwargs):
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.events import Event

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        agent = kwargs.pop("agent", Stub(name="test"))
        session = kwargs.pop("session", Session(app_name="app", user_id="u1"))
        return InvocationContext(session=session, agent=agent, **kwargs)

    def test_defaults(self):
        ctx = self._make_ctx()
        assert ctx.invocation_id.startswith("e-")
        assert ctx.branch is None
        assert ctx.end_invocation is False
        assert ctx.llm_call_count == 0
        assert ctx.run_config.max_llm_calls == 50

    def test_increment_llm_call_count(self):
        ctx = self._make_ctx()
        ctx.run_config = RunConfig(max_llm_calls=3)
        ctx.increment_llm_call_count()  # 1
        ctx.increment_llm_call_count()  # 2
        ctx.increment_llm_call_count()  # 3
        with pytest.raises(RuntimeError, match="Exceeded max LLM calls"):
            ctx.increment_llm_call_count()  # 4 -> exceeds 3

    def test_branch(self):
        ctx = self._make_ctx(branch="parallel.sub1")
        assert ctx.branch == "parallel.sub1"


class TestReadonlyContext:
    def test_properties(self):
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.events import Event

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        session = Session(app_name="app", user_id="u1")
        agent = Stub(name="myagent")
        inv_ctx = InvocationContext(session=session, agent=agent)

        ro = ReadonlyContext(invocation_context=inv_ctx, agent_name="myagent")
        assert ro.agent_name == "myagent"
        assert ro.session is session
        assert ro.invocation_id == inv_ctx.invocation_id


class TestContext:
    def _make_context(self):
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.events import Event

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        session = Session(app_name="app", user_id="u1")
        agent = Stub(name="agent")
        inv_ctx = InvocationContext(session=session, agent=agent)
        return Context(invocation_context=inv_ctx, agent_name="agent")

    def test_state_access(self):
        ctx = self._make_context()
        ctx.state["key"] = "value"
        assert ctx.state["key"] == "value"

    def test_actions(self):
        ctx = self._make_context()
        assert ctx.actions.state_delta == {}
        ctx.actions.transfer_to_agent = "other"
        assert ctx.actions.transfer_to_agent == "other"

    def test_commit_state_delta(self):
        ctx = self._make_context()
        ctx.state["a"] = 1
        ctx.state["b"] = 2
        delta = ctx.commit_state_delta()
        assert delta == {"a": 1, "b": 2}
        assert ctx.actions.state_delta == {"a": 1, "b": 2}

    def test_function_call_id(self):
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.events import Event

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        session = Session(app_name="app", user_id="u1")
        inv_ctx = InvocationContext(session=session, agent=Stub(name="a"))
        ctx = Context(
            invocation_context=inv_ctx,
            agent_name="a",
            function_call_id="fc-123",
        )
        assert ctx.function_call_id == "fc-123"

    def test_type_aliases(self):
        assert CallbackContext is Context
        assert ToolContext is Context
