"""Tests for Kahn topological sort in PluginRegistry."""

import pytest

from soulbot.plugins.interface import PluginInterface
from soulbot.plugins.registry import PluginRegistry


def _make_plugin(name: str, deps: list[str] | None = None) -> PluginInterface:
    """Create a plugin instance with given name and dependencies."""
    p = PluginInterface()
    p.name = name
    p.dependencies = deps or []
    return p


class TestTopologicalSort:
    def test_no_dependencies(self):
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a"))
        registry.add_plugin(_make_plugin("b"))
        registry.add_plugin(_make_plugin("c"))

        order = registry._calculate_startup_order()
        assert set(order) == {"a", "b", "c"}

    def test_linear_chain(self):
        """a → b → c: c depends on b, b depends on a."""
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a"))
        registry.add_plugin(_make_plugin("b", ["a"]))
        registry.add_plugin(_make_plugin("c", ["b"]))

        order = registry._calculate_startup_order()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_diamond_dependency(self):
        """
            a
           / \\
          b   c
           \\ /
            d
        d depends on b and c; b and c depend on a.
        """
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a"))
        registry.add_plugin(_make_plugin("b", ["a"]))
        registry.add_plugin(_make_plugin("c", ["a"]))
        registry.add_plugin(_make_plugin("d", ["b", "c"]))

        order = registry._calculate_startup_order()
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_circular_dependency_detected(self):
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a", ["b"]))
        registry.add_plugin(_make_plugin("b", ["a"]))

        with pytest.raises(ValueError, match="Circular dependency"):
            registry._calculate_startup_order()

    def test_unknown_dependency(self):
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a", ["nonexistent"]))

        with pytest.raises(ValueError, match="unknown plugin"):
            registry._calculate_startup_order()

    def test_self_dependency(self):
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a", ["a"]))

        with pytest.raises(ValueError, match="Circular dependency"):
            registry._calculate_startup_order()

    def test_multiple_roots(self):
        """Two independent chains: a→b and c→d."""
        registry = PluginRegistry()
        registry.add_plugin(_make_plugin("a"))
        registry.add_plugin(_make_plugin("b", ["a"]))
        registry.add_plugin(_make_plugin("c"))
        registry.add_plugin(_make_plugin("d", ["c"]))

        order = registry._calculate_startup_order()
        assert order.index("a") < order.index("b")
        assert order.index("c") < order.index("d")
        assert len(order) == 4

    async def test_start_respects_order(self):
        """Verify start_all() calls plugins in topological order."""
        start_order = []

        class OrderedPlugin(PluginInterface):
            async def on_start(self):
                start_order.append(self.name)

        p_a = OrderedPlugin()
        p_a.name = "a"
        p_a.dependencies = []

        p_b = OrderedPlugin()
        p_b.name = "b"
        p_b.dependencies = ["a"]

        p_c = OrderedPlugin()
        p_c.name = "c"
        p_c.dependencies = ["b"]

        registry = PluginRegistry()
        registry.add_plugin(p_a)
        registry.add_plugin(p_b)
        registry.add_plugin(p_c)

        await registry.start_all()
        assert start_order == ["a", "b", "c"]
