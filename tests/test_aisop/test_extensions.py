"""Tests for AISOP/AISIP shared extensions and node type inference."""

import pytest

from soulbot.aisop.extensions import (
    RESERVED_KEYS,
    AisopExtensions,
    infer_node_type,
)


class TestReservedKeys:
    def test_count_is_7(self):
        assert len(RESERVED_KEYS) == 7

    def test_contains_all_keys(self):
        expected = {
            "on_error", "retry_policy", "context_filter",
            "output_mapping", "map", "join", "constraints",
        }
        assert RESERVED_KEYS == expected

    def test_constraints_included(self):
        """constraints was missing in earlier versions (6 keys). Must be present."""
        assert "constraints" in RESERVED_KEYS

    def test_is_frozenset(self):
        assert isinstance(RESERVED_KEYS, frozenset)


class TestAisopExtensionsExtract:
    def test_extract_steps_only(self):
        body = {"step1": "do A", "step2": "do B"}
        steps, exts = AisopExtensions.extract(body)
        assert steps == {"step1": "do A", "step2": "do B"}
        assert exts == {}

    def test_extract_with_extensions(self):
        body = {
            "step1": "fetch data",
            "on_error": {"default": "ErrorHandler"},
            "retry_policy": {"max_attempts": 3},
            "constraints": ["data not empty"],
        }
        steps, exts = AisopExtensions.extract(body)
        assert steps == {"step1": "fetch data"}
        assert "on_error" in exts
        assert "retry_policy" in exts
        assert "constraints" in exts
        assert len(exts) == 3

    def test_extract_all_7_keys(self):
        body = {
            "step1": "work",
            "on_error": {"default": "X"},
            "retry_policy": {"max_attempts": 2},
            "context_filter": {"include": ["a"]},
            "output_mapping": "result",
            "map": {"items_path": "s.items", "iterator": "P"},
            "join": {"wait_for": ["P"]},
            "constraints": ["valid"],
        }
        steps, exts = AisopExtensions.extract(body)
        assert len(steps) == 1
        assert len(exts) == 7

    def test_extract_empty_body(self):
        steps, exts = AisopExtensions.extract({})
        assert steps == {}
        assert exts == {}


class TestContextFilter:
    def test_include(self):
        ctx = {"a": 1, "b": 2, "c": 3}
        result = AisopExtensions.apply_context_filter(ctx, {"include": ["a", "c"]})
        assert result == {"a": 1, "c": 3}

    def test_exclude(self):
        ctx = {"a": 1, "b": 2, "c": 3}
        result = AisopExtensions.apply_context_filter(ctx, {"exclude": ["b"]})
        assert result == {"a": 1, "c": 3}

    def test_no_filter(self):
        ctx = {"a": 1}
        result = AisopExtensions.apply_context_filter(ctx, {})
        assert result == {"a": 1}


class TestRetryPolicy:
    def test_should_retry(self):
        ok, prompt = AisopExtensions.should_retry(0, {"max_attempts": 3, "correction_prompt": "try again"})
        assert ok is True
        assert prompt == "try again"

    def test_should_not_retry(self):
        ok, prompt = AisopExtensions.should_retry(3, {"max_attempts": 3})
        assert ok is False
        assert prompt == ""

    def test_default_max_attempts(self):
        ok, _ = AisopExtensions.should_retry(0, {})
        assert ok is True
        ok, _ = AisopExtensions.should_retry(2, {})
        assert ok is False


class TestErrorTarget:
    def test_exact_match(self):
        on_error = {"timeout": "HandlerA", "default": "HandlerB"}
        assert AisopExtensions.resolve_error_target("timeout", on_error) == "HandlerA"

    def test_substring_match(self):
        on_error = {"timeout": "HandlerA", "default": "HandlerB"}
        assert AisopExtensions.resolve_error_target("connection_timeout_error", on_error) == "HandlerA"

    def test_default_fallback(self):
        on_error = {"timeout": "HandlerA", "default": "HandlerB"}
        assert AisopExtensions.resolve_error_target("unknown_error", on_error) == "HandlerB"

    def test_no_match(self):
        on_error = {"timeout": "HandlerA"}
        assert AisopExtensions.resolve_error_target("unknown_error", on_error) is None


class TestResolveMap:
    def test_resolve_items(self):
        state = {"state": {"data_items": [1, 2, 3]}}
        items = AisopExtensions.resolve_map(state, {"items_path": "state.data_items"})
        assert items == [1, 2, 3]

    def test_missing_path(self):
        state = {"state": {}}
        items = AisopExtensions.resolve_map(state, {"items_path": "state.data_items"})
        assert items == []

    def test_single_value_wrapped(self):
        state = {"val": 42}
        items = AisopExtensions.resolve_map(state, {"items_path": "val"})
        assert items == [42]


class TestInferNodeType:
    def test_empty_dict(self):
        assert infer_node_type({}) == "end"

    def test_none(self):
        assert infer_node_type(None) == "end"

    def test_decision(self):
        node = {"branches": {"yes": "A", "no": "B"}}
        assert infer_node_type(node) == "decision"

    def test_join(self):
        node = {"wait_for": ["NodeA", "NodeB"]}
        assert infer_node_type(node) == "join"

    def test_delegate(self):
        node = {"delegate_to": "sub_flow", "next": ["ReturnNode"]}
        assert infer_node_type(node) == "delegate"

    def test_fork(self):
        node = {"next": ["A", "B"]}
        assert infer_node_type(node) == "fork"

    def test_fork_three(self):
        node = {"next": ["A", "B", "C"]}
        assert infer_node_type(node) == "fork"

    def test_process(self):
        node = {"next": ["A"]}
        assert infer_node_type(node) == "process"

    def test_process_with_error(self):
        node = {"next": ["A"], "error": "ErrorNode"}
        assert infer_node_type(node) == "process"

    def test_end_fallback(self):
        node = {"task": "something but no next"}
        assert infer_node_type(node) == "end"

    def test_priority_branches_over_next(self):
        """branches key should win over next key (decision > fork)."""
        node = {"branches": {"yes": "A"}, "next": ["B", "C"]}
        assert infer_node_type(node) == "decision"

    def test_priority_wait_for_over_next(self):
        """wait_for key should win over next key (join > process)."""
        node = {"wait_for": ["A"], "next": ["B"]}
        assert infer_node_type(node) == "join"

    def test_priority_delegate_over_fork(self):
        """delegate_to should win over next with 2+ targets."""
        node = {"delegate_to": "sub", "next": ["A", "B"]}
        assert infer_node_type(node) == "delegate"
