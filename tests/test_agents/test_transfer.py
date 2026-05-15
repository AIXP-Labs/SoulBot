"""Tests for Agent Transfer and AgentTool."""

import pytest

from soulbot.agents import InvocationContext, LlmAgent, RunConfig
from soulbot.events.event import Content, Event, FunctionCall, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmRequest, LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService, Session
from soulbot.tools import AgentTool, TransferToAgentTool


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class MockLlm(BaseLlm):
    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls):
        return [r"mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"mock-.*", MockLlm)
    yield
    ModelRegistry.reset()


@pytest.fixture
def service():
    return InMemorySessionService()


# ---------------------------------------------------------------------------
# TransferToAgentTool
# ---------------------------------------------------------------------------


class TestTransferToAgentTool:
    def test_declaration(self):
        tool = TransferToAgentTool([
            {"name": "billing", "description": "Handle billing"},
            {"name": "tech", "description": "Technical support"},
        ])
        decl = tool.get_declaration()
        assert decl["name"] == "transfer_to_agent"
        assert "billing" in decl["parameters"]["properties"]["agent_name"]["enum"]
        assert "tech" in decl["parameters"]["properties"]["agent_name"]["enum"]

    @pytest.mark.asyncio
    async def test_run_valid_transfer(self):
        from soulbot.agents.context import Context
        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.sessions import Session

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        session = Session(app_name="test", user_id="u1")
        inv_ctx = InvocationContext(session=session, agent=Stub(name="root"))
        tool_ctx = Context(invocation_context=inv_ctx, agent_name="root")

        tool = TransferToAgentTool([{"name": "billing", "description": "billing"}])
        result = await tool.run_async(
            args={"agent_name": "billing"}, tool_context=tool_ctx
        )

        assert result["status"] == "transferring"
        assert tool_ctx.actions.transfer_to_agent == "billing"

    @pytest.mark.asyncio
    async def test_run_invalid_agent(self):
        from soulbot.agents.context import Context
        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.agents.base_agent import BaseAgent
        from soulbot.sessions import Session

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        session = Session(app_name="test", user_id="u1")
        inv_ctx = InvocationContext(session=session, agent=Stub(name="root"))
        tool_ctx = Context(invocation_context=inv_ctx, agent_name="root")

        tool = TransferToAgentTool([{"name": "billing", "description": "billing"}])
        result = await tool.run_async(
            args={"agent_name": "unknown"}, tool_context=tool_ctx
        )

        assert "error" in result


# ---------------------------------------------------------------------------
# Agent Transfer end-to-end via LlmAgent
# ---------------------------------------------------------------------------


class TestAgentTransfer:
    @pytest.mark.asyncio
    async def test_auto_inject_transfer_tool(self):
        """LlmAgent with sub_agents should auto-inject TransferToAgentTool."""
        child = LlmAgent(name="child", model="mock-v1", description="Child agent")
        parent = LlmAgent(name="parent", model="mock-v1", sub_agents=[child])

        tools = parent._resolve_tools()
        transfer_tools = [t for t in tools if isinstance(t, TransferToAgentTool)]
        assert len(transfer_tools) == 1
        assert transfer_tools[0].agent_names[0]["name"] == "child"

    @pytest.mark.asyncio
    async def test_no_transfer_tool_without_sub_agents(self):
        """LlmAgent without sub_agents should NOT inject TransferToAgentTool."""
        agent = LlmAgent(name="solo", model="mock-v1")
        tools = agent._resolve_tools()
        assert not any(isinstance(t, TransferToAgentTool) for t in tools)

    @pytest.mark.asyncio
    async def test_transfer_end_to_end(self, service):
        """Full transfer: parent delegates to child via TransferToAgentTool."""
        # Parent: first calls transfer_to_agent, then child responds
        MockLlm.set_responses([
            # Parent's response: call transfer_to_agent
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[
                        Part(
                            function_call=FunctionCall(
                                name="transfer_to_agent",
                                args={"agent_name": "specialist"},
                                id="tc-1",
                            )
                        )
                    ],
                )
            ),
            # Specialist's response (after transfer)
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(text="I'm the specialist, here to help!")],
                )
            ),
        ])

        specialist = LlmAgent(
            name="specialist",
            model="mock-v1",
            description="Handles specialized queries",
        )
        router = LlmAgent(
            name="router",
            model="mock-v1",
            instruction="Route queries to the right specialist",
            sub_agents=[specialist],
        )
        runner = Runner(agent=router, app_name="test", session_service=service)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s1", message="I need specialist help"
        ):
            events.append(event)

        # Should have: transfer call event, transfer response event, specialist text
        non_partial = [e for e in events if not e.partial]
        assert any(
            e.content
            and e.content.parts
            and any(p.text and "specialist" in p.text for p in e.content.parts)
            for e in non_partial
        )


# ---------------------------------------------------------------------------
# AgentTool
# ---------------------------------------------------------------------------


class TestAgentTool:
    def test_declaration(self):
        from soulbot.agents.base_agent import BaseAgent

        class Stub(BaseAgent):
            async def _run_async_impl(self, ctx):
                yield Event(author=self.name)

        agent = Stub(name="helper", description="Helps with things")
        tool = AgentTool(agent)

        decl = tool.get_declaration()
        assert decl["name"] == "helper"
        assert "request" in decl["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_agent_tool_execution(self, service):
        """AgentTool should run the wrapped agent and return its text."""
        MockLlm.set_responses([
            # Parent calls agent_tool
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[
                        Part(
                            function_call=FunctionCall(
                                name="sub_agent",
                                args={"request": "What is 2+2?"},
                                id="at-1",
                            )
                        )
                    ],
                )
            ),
            # Sub-agent responds (through AgentTool)
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(text="The answer is 4")],
                )
            ),
            # Parent final response after seeing tool result
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(text="According to sub_agent, the answer is 4")],
                )
            ),
        ])

        sub = LlmAgent(name="sub_agent", model="mock-v1", description="Math helper")
        tool = AgentTool(sub)

        parent = LlmAgent(
            name="parent",
            model="mock-v1",
            tools=[tool],
        )
        runner = Runner(agent=parent, app_name="test", session_service=service)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s1", message="What is 2+2?"
        ):
            events.append(event)

        non_partial = [e for e in events if not e.partial]
        # Last event should be the parent's final answer
        final_texts = [
            p.text
            for e in non_partial
            if e.content
            for p in e.content.parts
            if p.text
        ]
        assert any("4" in t for t in final_texts)
