"""Tests for AISOP schema models."""

import pytest

from soulbot.aisop.schema import AisopBlueprint, AisopTool


class TestAisopTool:
    def test_minimal(self):
        tool = AisopTool(name="search")
        assert tool.name == "search"
        assert tool.description == ""
        assert tool.parameters == {}

    def test_full(self):
        tool = AisopTool(
            name="check_status",
            description="Check system status",
            parameters={"system_name": "string"},
        )
        assert tool.name == "check_status"
        assert tool.description == "Check system status"
        assert tool.parameters["system_name"] == "string"


class TestAisopBlueprint:
    def test_minimal(self):
        bp = AisopBlueprint(name="test")
        assert bp.name == "test"
        assert bp.version == "1.0"
        assert bp.description == ""
        assert bp.workflow == ""
        assert bp.functions == {}
        assert bp.tools == []
        assert bp.system_directive == ""
        assert bp.metadata == {}

    def test_full(self):
        bp = AisopBlueprint(
            name="support",
            version="2.0",
            description="Customer support",
            workflow="graph TD\n  A --> B",
            functions={"A": "Receive query", "B": "Respond"},
            tools=[AisopTool(name="search", description="Search KB")],
            system_directive="Be polite",
            metadata={"author": "test"},
        )
        assert bp.name == "support"
        assert bp.version == "2.0"
        assert len(bp.tools) == 1
        assert bp.tools[0].name == "search"
        assert bp.functions["A"] == "Receive query"
        assert bp.metadata["author"] == "test"

    def test_from_dict(self):
        data = {
            "name": "hello",
            "workflow": "graph TD\n  A --> B",
            "functions": {"A": "Start", "B": "End"},
        }
        bp = AisopBlueprint(**data)
        assert bp.name == "hello"
        assert "A --> B" in bp.workflow

    def test_model_dump(self):
        bp = AisopBlueprint(name="test", version="1.0")
        dumped = bp.model_dump()
        assert dumped["name"] == "test"
        assert dumped["version"] == "1.0"
        assert isinstance(dumped["functions"], dict)
        assert isinstance(dumped["tools"], list)

    def test_tools_from_dicts(self):
        bp = AisopBlueprint(
            name="test",
            tools=[
                {"name": "t1", "description": "Tool 1"},
                {"name": "t2", "description": "Tool 2", "parameters": {"x": "int"}},
            ],
        )
        assert len(bp.tools) == 2
        assert bp.tools[0].name == "t1"
        assert bp.tools[1].parameters["x"] == "int"
