"""Tests that example agents can be loaded correctly.

Examples are organized under:
- simple/  — Soul_Agent (AISOP runtime with AIAP package routing)
"""

import pytest
from pathlib import Path

from soulbot.server.agent_loader import AgentLoader
from soulbot.agents import LlmAgent


EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
SIMPLE_DIR = EXAMPLES_DIR / "simple"


@pytest.fixture
def simple_loader():
    if not SIMPLE_DIR.is_dir():
        pytest.skip("simple example not found")
    return AgentLoader(SIMPLE_DIR)


class TestSimpleExample:
    def test_list_agents(self, simple_loader):
        names = simple_loader.list_agents()
        assert "Soul_Agent" in names

    def test_load_soul_Agent(self, simple_loader):
        # Exact case matters: NTFS tolerates "soul_Agent" but Linux does not.
        agent = simple_loader.load_agent("Soul_Agent")
        assert agent.name == "Soul_Agent"
        assert isinstance(agent, LlmAgent)
        assert agent.model is not None
