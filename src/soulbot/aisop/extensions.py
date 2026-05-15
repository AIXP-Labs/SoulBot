"""AISOP/AISIP shared function-layer extension parsing.

Both protocols store extension fields at the **functions** layer (not flow/node layer).
This module provides unified parsing for both AISOP and AISIP.

7 RESERVED_KEYS — Runtime parses these before step execution:
  on_error, retry_policy, context_filter, output_mapping, map, join, constraints
"""

from __future__ import annotations

from typing import Any


# ── RESERVED_KEYS ──────────────────────────────────────────────

RESERVED_KEYS = frozenset({
    "on_error",
    "retry_policy",
    "context_filter",
    "output_mapping",
    "map",
    "join",
    "constraints",
})  # 7 keys, including constraints


class AisopExtensions:
    """AISOP/AISIP shared function-layer extension parser.

    Usage::

        steps, exts = AisopExtensions.extract(function_body)
        # steps = {"step1": "...", "step2": "..."}
        # exts  = {"on_error": {...}, "constraints": [...]}
    """

    RESERVED_KEYS = RESERVED_KEYS

    @classmethod
    def extract(cls, function_body: dict) -> tuple[dict, dict]:
        """Separate steps and extensions from a function body.

        Works identically for AISOP and AISIP — both keep extensions
        in the functions layer alongside steps.

        Returns:
            (steps, extensions) — steps dict and extensions dict.
        """
        steps = {k: v for k, v in function_body.items()
                 if k not in cls.RESERVED_KEYS}
        extensions = {k: v for k, v in function_body.items()
                      if k in cls.RESERVED_KEYS}
        return steps, extensions

    @staticmethod
    def apply_context_filter(context: dict, spec: dict) -> dict:
        """Trim context before entering a node.

        Args:
            context: Current execution context.
            spec: Filter spec with ``include`` or ``exclude`` list.

        Returns:
            Filtered context dict.
        """
        if "include" in spec:
            return {k: v for k, v in context.items() if k in spec["include"]}
        if "exclude" in spec:
            return {k: v for k, v in context.items() if k not in spec["exclude"]}
        return context

    @staticmethod
    def should_retry(attempt: int, policy: dict) -> tuple[bool, str]:
        """Determine whether to retry based on policy.

        Args:
            attempt: Current attempt number (0-based).
            policy: Retry policy dict with ``max_attempts`` and optional
                ``correction_prompt``.

        Returns:
            (should_retry, correction_prompt) tuple.
        """
        if attempt < policy.get("max_attempts", 2):
            return True, policy.get("correction_prompt", "")
        return False, ""

    @staticmethod
    def resolve_error_target(error_type: str, on_error: dict) -> str | None:
        """Match error type to a fallback target node.

        Args:
            error_type: The error type string (e.g. ``"timeout"``).
            on_error: Mapping of error types to target node names.

        Returns:
            Target node name, or ``None`` if no match found.
        """
        if error_type in on_error:
            return on_error[error_type]
        for key in ("timeout", "model_refusal", "tool_error"):
            if key in error_type.lower() and key in on_error:
                return on_error[key]
        return on_error.get("default")

    @staticmethod
    def resolve_map(state: dict, map_spec: dict) -> list[Any]:
        """Resolve map items from state using ``items_path``.

        Args:
            state: Current execution state dict.
            map_spec: Map spec with ``items_path`` (dot-separated path).

        Returns:
            List of items to iterate over.
        """
        path = map_spec.get("items_path", "")
        obj: Any = state
        for part in path.split("."):
            if isinstance(obj, dict):
                obj = obj.get(part, [])
            else:
                return []
        return obj if isinstance(obj, list) else [obj]


# ── Node Type Inference ────────────────────────────────────────

def infer_node_type(node: dict) -> str:
    """Infer AISIP node type from structure — no ``type`` field needed.

    Inference rules (order matters — first match wins):

    ============================  ===========
    Structure                     Type
    ============================  ===========
    ``{}`` or ``None``            ``end``
    ``{"branches": {...}}``       ``decision``
    ``{"wait_for": [...]}``       ``join``
    ``{"delegate_to": "..."}``    ``delegate``
    ``{"next": ["a","b",...]}``   ``fork`` (2+ targets)
    ``{"next": ["a"]}``          ``process``
    (fallback)                    ``end``
    ============================  ===========

    Args:
        node: An AISIP node dict.

    Returns:
        Inferred type string.
    """
    if not node or node == {}:
        return "end"
    if "branches" in node:
        return "decision"
    if "wait_for" in node:
        return "join"
    if "delegate_to" in node:
        return "delegate"
    if "next" in node and len(node["next"]) >= 2:
        return "fork"
    if "next" in node:
        return "process"
    return "end"
