"""Tests for AISOP integration with LlmAgent."""

import json
import pytest

from soulbot.aisop.schema import AisopBlueprint
from soulbot.aisop.loader import AisopLoader
from soulbot.aisop.prompt_builder import AisopPromptBuilder
from soulbot.agents.llm_agent import LlmAgent
from soulbot.agents.invocation_context import InvocationContext, RunConfig
from soulbot.events.event import Content, Part
from soulbot.models.llm_request import LlmResponse
from soulbot.sessions.session import Session


class TestAisopIntegration:
    def test_blueprint_as_instruction(self):
        """Build a prompt from blueprint and use it as LlmAgent instruction."""
        bp = AisopBlueprint(
            name="greeter",
            workflow="graph TD\n  A[Greet] --> B[Ask Name] --> C[Respond]",
            functions={
                "A": "Greet the user warmly",
                "B": "Ask for user's name",
                "C": "Respond with personalized greeting",
            },
            system_directive="Always be friendly.",
        )
        prompt = AisopPromptBuilder().build(bp)

        agent = LlmAgent(
            name="greeter_agent",
            model="claude-acp/sonnet",
            instruction=prompt,
        )

        assert "greeter.aisop.json" in agent.instruction
        assert "Always be friendly" in agent.instruction

    async def test_aisop_agent_runs(self):
        """Agent with AISOP instruction can run (using before_model_callback)."""
        bp = AisopBlueprint(
            name="echo",
            workflow="graph TD\n  A[Receive] --> B[Echo]",
            functions={"A": "Receive input", "B": "Echo back"},
        )
        prompt = AisopPromptBuilder().build(bp)

        agent = LlmAgent(
            name="echo_agent",
            model="claude-acp/sonnet",
            instruction=prompt,
            before_model_callback=lambda ctx, req: LlmResponse(
                content=Content(role="model", parts=[Part(text="Echo: hello")]),
            ),
        )

        session = Session(app_name="test", user_id="u", session_id="s")
        ctx = InvocationContext(session=session, agent=agent)

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].content.parts[0].text == "Echo: hello"

    def test_loader_to_agent(self, tmp_path):
        """Full path: file → loader → prompt → agent."""
        data = {
            "name": "helper",
            "workflow": "graph TD\n  A-->B",
            "functions": {"A": "Analyze", "B": "Respond"},
            "system_directive": "Be helpful.",
        }
        path = tmp_path / "helper.aisop.json"
        path.write_text(json.dumps(data), encoding="utf-8")

        loader = AisopLoader(tmp_path)
        bp = loader.load("helper")
        prompt = AisopPromptBuilder().build(bp, base_prompt="You are an AI assistant.")

        agent = LlmAgent(
            name="helper_agent",
            model="claude-acp/sonnet",
            instruction=prompt,
        )

        assert "You are an AI assistant." in agent.instruction
        assert "helper.aisop.json" in agent.instruction
        assert "Be helpful." in agent.instruction

    async def test_aisop_instruction_has_workflow(self):
        """Verify the LLM receives the Mermaid workflow."""
        captured_request = []

        def capture_callback(ctx, req):
            captured_request.append(req)
            return LlmResponse(
                content=Content(role="model", parts=[Part(text="done")]),
            )

        bp = AisopBlueprint(
            name="flow",
            workflow="graph TD\n  START --> PROCESS --> END",
            functions={"START": "Begin", "PROCESS": "Work", "END": "Finish"},
        )
        prompt = AisopPromptBuilder().build(bp)

        agent = LlmAgent(
            name="flow_agent",
            model="claude-acp/sonnet",
            instruction=prompt,
            before_model_callback=capture_callback,
        )

        session = Session(app_name="test", user_id="u", session_id="s")
        ctx = InvocationContext(session=session, agent=agent)

        async for _ in agent.run_async(ctx):
            pass

        assert len(captured_request) == 1
        # The system instruction should contain the workflow
        assert "START --> PROCESS --> END" in captured_request[0].system_instruction
