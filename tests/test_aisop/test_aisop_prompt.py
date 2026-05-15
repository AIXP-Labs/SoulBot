"""Tests for AisopPromptBuilder."""

import json
import pytest

from soulbot.aisop.schema import AisopBlueprint, AisopTool
from soulbot.aisop.prompt_builder import AisopPromptBuilder


class TestAisopPromptBuilder:
    def setup_method(self):
        self.builder = AisopPromptBuilder()
        self.bp = AisopBlueprint(
            name="test_flow",
            version="1.0",
            description="Test flow",
            workflow="graph TD\n  A --> B",
            functions={"A": "Start", "B": "End"},
        )

    def test_basic_prompt(self):
        prompt = self.builder.build(self.bp)
        assert "[LOADED AISOP: test_flow.aisop.json]" in prompt
        assert "```json" in prompt
        assert '"name": "test_flow"' in prompt
        assert "graph TD" in prompt

    def test_with_base_prompt(self):
        prompt = self.builder.build(self.bp, base_prompt="You are a helpful assistant.")
        assert prompt.startswith("You are a helpful assistant.")

    def test_with_workspace_dir(self):
        prompt = self.builder.build(self.bp, workspace_dir="/app/aisop")
        assert "[WORKSPACE]" in prompt
        assert "/app/aisop" in prompt

    def test_with_schedule(self):
        prompt = self.builder.build(self.bp, enable_schedule=True)
        assert "[SCHEDULE]" in prompt
        assert "scheduling capability" in prompt

    def test_with_directive(self):
        bp = AisopBlueprint(
            name="test",
            system_directive="Always be professional.",
        )
        prompt = self.builder.build(bp)
        assert "[DIRECTIVE]" in prompt
        assert "Always be professional." in prompt

    def test_no_directive_omitted(self):
        prompt = self.builder.build(self.bp)
        assert "[DIRECTIVE]" not in prompt

    def test_full_prompt(self):
        bp = AisopBlueprint(
            name="full",
            workflow="graph TD\n  A-->B-->C",
            functions={"A": "Input", "B": "Process", "C": "Output"},
            tools=[AisopTool(name="search", description="Search")],
            system_directive="Be concise.",
        )
        prompt = self.builder.build(
            bp,
            base_prompt="Base instructions.",
            workspace_dir="/workspace",
            enable_schedule=True,
        )
        assert "Base instructions." in prompt
        assert "[LOADED AISOP: full.aisop.json]" in prompt
        assert "[WORKSPACE]" in prompt
        assert "[SCHEDULE]" in prompt
        assert "[DIRECTIVE]" in prompt
        assert "Be concise." in prompt

    def test_json_contains_all_fields(self):
        prompt = self.builder.build(self.bp)
        # Extract JSON block
        start = prompt.index("```json\n") + len("```json\n")
        end = prompt.index("\n```", start)
        json_str = prompt[start:end]
        data = json.loads(json_str)
        assert data["name"] == "test_flow"
        assert data["version"] == "1.0"
        assert "A" in data["functions"]

    def test_chinese_content(self):
        bp = AisopBlueprint(
            name="中文蓝图",
            description="客服支持流程",
            functions={"A": "分析用户输入"},
            system_directive="始终保持礼貌",
        )
        prompt = self.builder.build(bp)
        assert "中文蓝图" in prompt
        assert "客服支持流程" in prompt
        assert "分析用户输入" in prompt
        assert "始终保持礼貌" in prompt
