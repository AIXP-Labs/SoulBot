"""Tests for BaseTool and FunctionTool."""

import pytest

from soulbot.tools import FunctionTool


class TestFunctionTool:
    def test_from_simple_function(self):
        def greet(name: str) -> str:
            """Greet a person."""
            return f"Hello, {name}!"

        tool = FunctionTool(greet)
        assert tool.name == "greet"
        assert tool.description == "Greet a person."

    def test_schema_generation(self):
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        tool = FunctionTool(add)
        decl = tool.get_declaration()
        assert decl["name"] == "add"
        assert decl["description"] == "Add two numbers."
        params = decl["parameters"]
        assert params["type"] == "object"
        assert "a" in params["properties"]
        assert "b" in params["properties"]
        assert params["properties"]["a"]["type"] == "integer"
        assert params["properties"]["b"]["type"] == "integer"
        assert set(params["required"]) == {"a", "b"}

    def test_schema_optional_param(self):
        def search(query: str, limit: int = 10) -> list:
            """Search for items."""
            return []

        tool = FunctionTool(search)
        decl = tool.get_declaration()
        params = decl["parameters"]
        assert params["required"] == ["query"]
        assert "limit" in params["properties"]

    def test_schema_various_types(self):
        def func(
            name: str,
            count: int,
            ratio: float,
            flag: bool,
            tags: list[str],
            data: dict,
        ):
            """Multi-type function."""
            pass

        tool = FunctionTool(func)
        decl = tool.get_declaration()
        props = decl["parameters"]["properties"]
        assert props["name"]["type"] == "string"
        assert props["count"]["type"] == "integer"
        assert props["ratio"]["type"] == "number"
        assert props["flag"]["type"] == "boolean"
        assert props["tags"]["type"] == "array"
        assert props["data"]["type"] == "object"

    def test_schema_ignores_tool_context(self):
        def my_tool(query: str, tool_context=None):
            """A tool that accepts context."""
            return query

        tool = FunctionTool(my_tool)
        decl = tool.get_declaration()
        assert "tool_context" not in decl["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_run_sync_function(self):
        def multiply(a: int, b: int) -> int:
            """Multiply."""
            return a * b

        tool = FunctionTool(multiply)
        result = await tool.run_async(args={"a": 3, "b": 7}, tool_context=None)
        assert result == 21

    @pytest.mark.asyncio
    async def test_run_async_function(self):
        async def async_add(a: int, b: int) -> int:
            """Async add."""
            return a + b

        tool = FunctionTool(async_add)
        result = await tool.run_async(args={"a": 5, "b": 3}, tool_context=None)
        assert result == 8

    @pytest.mark.asyncio
    async def test_missing_mandatory_arg(self):
        def greet(name: str) -> str:
            """Greet."""
            return f"Hi {name}"

        tool = FunctionTool(greet)
        result = await tool.run_async(args={}, tool_context=None)
        assert isinstance(result, dict)
        assert "error" in result
        assert "name" in result["error"]

    @pytest.mark.asyncio
    async def test_extra_args_filtered(self):
        def echo(msg: str) -> str:
            """Echo."""
            return msg

        tool = FunctionTool(echo)
        result = await tool.run_async(
            args={"msg": "hello", "extra": "ignored"}, tool_context=None
        )
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_tool_context_injection(self):
        def stateful_tool(x: int, tool_context=None) -> dict:
            """Tool that uses context."""
            return {"x": x, "has_ctx": tool_context is not None}

        tool = FunctionTool(stateful_tool)
        result = await tool.run_async(
            args={"x": 42}, tool_context="fake_ctx"
        )
        assert result == {"x": 42, "has_ctx": True}

    def test_auto_wrap_callable(self):
        """Ensure FunctionTool works with callable objects."""
        class MyCallable:
            def __call__(self, x: int) -> int:
                """Double the value."""
                return x * 2

        tool = FunctionTool(MyCallable())
        assert tool.name == "MyCallable"
