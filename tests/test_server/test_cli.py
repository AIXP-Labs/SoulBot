"""Tests for CLI commands."""

import pytest
from pathlib import Path
from click.testing import CliRunner

from soulbot.cli import main


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "SoulBot" in result.output

    def test_create_agent(self, runner, tmp_path):
        result = runner.invoke(main, ["create", "my_agent", "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Created agent project" in result.output

        agent_dir = tmp_path / "my_agent"
        assert agent_dir.is_dir()
        assert (agent_dir / "agent.py").is_file()
        assert (agent_dir / ".env").is_file()

        # Check agent.py content
        content = (agent_dir / "agent.py").read_text(encoding="utf-8")
        assert "root_agent" in content
        assert "LlmAgent" in content

    def test_create_agent_already_exists(self, runner, tmp_path):
        (tmp_path / "existing").mkdir()
        result = runner.invoke(main, ["create", "existing", "--output-dir", str(tmp_path)])
        assert result.exit_code != 0

    def test_run_missing_agent(self, runner, tmp_path):
        result = runner.invoke(main, ["run", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0

    def test_web_help(self, runner):
        result = runner.invoke(main, ["web", "--help"])
        assert result.exit_code == 0
        assert "agents-dir" in result.output

    def test_api_server_help(self, runner):
        result = runner.invoke(main, ["api-server", "--help"])
        assert result.exit_code == 0
        assert "agents-dir" in result.output
