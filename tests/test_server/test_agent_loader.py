"""Tests for AgentLoader."""

import os

import pytest
from pathlib import Path

from soulbot.server.agent_loader import AgentLoader


@pytest.fixture
def agents_dir(tmp_path):
    """Create a temporary agents directory with sample agents."""
    # Package-style agent
    pkg = tmp_path / "hello_agent"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from .agent import root_agent\n", encoding="utf-8"
    )
    (pkg / "agent.py").write_text(
        """
from soulbot.agents import BaseAgent
from soulbot.events.event import Content, Event, Part

class _HelloAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=Content(role="model", parts=[Part(text="hello")])
        )

root_agent = _HelloAgent(name="hello_agent", description="Says hello")
""",
        encoding="utf-8",
    )

    # Single-file agent
    (tmp_path / "simple_agent.py").write_text(
        """
from soulbot.agents import BaseAgent
from soulbot.events.event import Content, Event, Part

class _SimpleAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=Content(role="model", parts=[Part(text="simple")])
        )

root_agent = _SimpleAgent(name="simple_agent")
""",
        encoding="utf-8",
    )

    # agent.py style (no __init__.py)
    bare = tmp_path / "bare_agent"
    bare.mkdir()
    (bare / "agent.py").write_text(
        """
from soulbot.agents import BaseAgent
from soulbot.events.event import Content, Event, Part

class _BareAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            content=Content(role="model", parts=[Part(text="bare")])
        )

root_agent = _BareAgent(name="bare_agent")
""",
        encoding="utf-8",
    )

    # Hidden/ignored directory
    hidden = tmp_path / "_internal"
    hidden.mkdir()
    (hidden / "agent.py").write_text("root_agent = None\n", encoding="utf-8")

    return tmp_path


class TestAgentLoader:
    def test_list_agents(self, agents_dir):
        loader = AgentLoader(agents_dir)
        names = loader.list_agents()
        assert "hello_agent" in names
        assert "simple_agent" in names
        assert "bare_agent" in names
        assert "_internal" not in names

    def test_load_package_agent(self, agents_dir):
        loader = AgentLoader(agents_dir)
        agent = loader.load_agent("hello_agent")
        assert agent.name == "hello_agent"
        assert agent.description == "Says hello"

    def test_load_single_file_agent(self, agents_dir):
        loader = AgentLoader(agents_dir)
        agent = loader.load_agent("simple_agent")
        assert agent.name == "simple_agent"

    def test_load_bare_agent(self, agents_dir):
        loader = AgentLoader(agents_dir)
        agent = loader.load_agent("bare_agent")
        assert agent.name == "bare_agent"

    def test_load_nonexistent(self, agents_dir):
        loader = AgentLoader(agents_dir)
        with pytest.raises(FileNotFoundError):
            loader.load_agent("nonexistent")

    def test_invalid_agents_dir(self):
        with pytest.raises(FileNotFoundError):
            AgentLoader("/nonexistent/path/to/agents")

    def test_missing_root_agent(self, tmp_path):
        (tmp_path / "bad_agent.py").write_text(
            "x = 42\n", encoding="utf-8"
        )
        loader = AgentLoader(tmp_path)
        with pytest.raises(AttributeError, match="root_agent"):
            loader.load_agent("bad_agent")

    def test_root_agent_wrong_type(self, tmp_path):
        (tmp_path / "wrong_type.py").write_text(
            'root_agent = "not an agent"\n', encoding="utf-8"
        )
        loader = AgentLoader(tmp_path)
        with pytest.raises(TypeError, match="BaseAgent"):
            loader.load_agent("wrong_type")


# ---------------------------------------------------------------------------
# Hierarchical env tests
# ---------------------------------------------------------------------------


class TestAgentEnv:
    """Tests for the hierarchical .env caching system."""

    def test_root_env_cached_at_init(self, tmp_path):
        """Root .env is parsed and cached during __init__."""
        (tmp_path / ".env").write_text(
            "KEY_A=root_a\nKEY_B=root_b\n", encoding="utf-8"
        )
        loader = AgentLoader(tmp_path)
        assert loader._root_env == {"KEY_A": "root_a", "KEY_B": "root_b"}

    def test_no_root_env(self, tmp_path):
        """No root .env → _root_env is empty dict."""
        loader = AgentLoader(tmp_path)
        assert loader._root_env == {}

    def test_agent_env_inherits_root(self, tmp_path):
        """Agent without .env inherits all root values."""
        (tmp_path / ".env").write_text(
            "MODEL=sonnet\nCLI=true\n", encoding="utf-8"
        )
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env = loader.get_agent_env("my_agent")
        assert env == {"MODEL": "sonnet", "CLI": "true"}

    def test_agent_env_overrides_root(self, tmp_path):
        """Agent .env fully overrides root values for matching keys."""
        (tmp_path / ".env").write_text(
            "MODEL=sonnet\nCLI=true\n", encoding="utf-8"
        )
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")
        (agent_dir / ".env").write_text(
            "MODEL=opus\nCLI=false\n", encoding="utf-8"
        )

        loader = AgentLoader(tmp_path)
        env = loader.get_agent_env("my_agent")
        assert env["MODEL"] == "opus"
        assert env["CLI"] == "false"

    def test_agent_env_partial_override(self, tmp_path):
        """Agent .env overrides some keys; missing keys come from root."""
        (tmp_path / ".env").write_text(
            "MODEL=sonnet\nCLI=true\nTOKEN=root_tok\n", encoding="utf-8"
        )
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")
        (agent_dir / ".env").write_text("TOKEN=agent_tok\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env = loader.get_agent_env("my_agent")
        assert env["TOKEN"] == "agent_tok"   # overridden
        assert env["MODEL"] == "sonnet"      # inherited from root
        assert env["CLI"] == "true"          # inherited from root

    def test_agent_env_cached(self, tmp_path):
        """Multiple calls return the same cached dict object."""
        (tmp_path / ".env").write_text("K=V\n", encoding="utf-8")
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env1 = loader.get_agent_env("my_agent")
        env2 = loader.get_agent_env("my_agent")
        assert env1 is env2  # same object, not re-parsed

    def test_agent_env_no_root_env(self, tmp_path):
        """No root .env → agent gets only its own values."""
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")
        (agent_dir / ".env").write_text("MY_KEY=my_val\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env = loader.get_agent_env("my_agent")
        assert env == {"MY_KEY": "my_val"}

    def test_agent_env_isolation(self, tmp_path):
        """Agent A's env does not leak into Agent B's env."""
        (tmp_path / ".env").write_text("SHARED=root\n", encoding="utf-8")

        for name, token in [("agent_a", "tok_a"), ("agent_b", "tok_b")]:
            d = tmp_path / name
            d.mkdir()
            (d / "agent.py").write_text("x = 1\n", encoding="utf-8")
            (d / ".env").write_text(f"TOKEN={token}\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env_a = loader.get_agent_env("agent_a")
        env_b = loader.get_agent_env("agent_b")

        assert env_a["TOKEN"] == "tok_a"
        assert env_b["TOKEN"] == "tok_b"
        assert env_a["SHARED"] == "root"
        assert env_b["SHARED"] == "root"

    def test_load_agent_env_applies_to_os(self, tmp_path, monkeypatch):
        """_load_agent_env writes the merged env into os.environ."""
        (tmp_path / ".env").write_text(
            "ROOT_KEY=root_val\n", encoding="utf-8"
        )
        agent_dir = tmp_path / "my_agent"
        agent_dir.mkdir()
        (agent_dir / "agent.py").write_text("x = 1\n", encoding="utf-8")
        (agent_dir / ".env").write_text(
            "AGENT_KEY=agent_val\n", encoding="utf-8"
        )

        # Clean env to avoid interference
        monkeypatch.delenv("ROOT_KEY", raising=False)
        monkeypatch.delenv("AGENT_KEY", raising=False)

        loader = AgentLoader(tmp_path)
        loader._load_agent_env("my_agent")

        assert os.environ["ROOT_KEY"] == "root_val"
        assert os.environ["AGENT_KEY"] == "agent_val"

    def test_single_file_agent_uses_root(self, tmp_path):
        """Single-file agent (no directory) inherits root env."""
        (tmp_path / ".env").write_text("K=V\n", encoding="utf-8")
        (tmp_path / "solo.py").write_text("x = 1\n", encoding="utf-8")

        loader = AgentLoader(tmp_path)
        env = loader.get_agent_env("solo")
        assert env == {"K": "V"}

    def test_parse_env_missing_file(self, tmp_path):
        """_parse_env returns {} for non-existent file."""
        result = AgentLoader._parse_env(tmp_path / "nonexistent.env")
        assert result == {}
