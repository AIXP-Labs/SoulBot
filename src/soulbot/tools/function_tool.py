"""FunctionTool — automatically wraps a Python function as a tool."""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable, Optional, Union, get_args, get_origin

import pydantic
from pydantic import BaseModel

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON Schema helpers
# ---------------------------------------------------------------------------

_PY_TYPE_TO_JSON: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _type_to_json_schema(annotation: Any) -> dict:
    """Convert a Python type annotation to a JSON Schema property dict."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}

    # Handle Optional[T] → Union[T, None]
    origin = get_origin(annotation)
    if origin is Union:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            return _type_to_json_schema(args[0])
        return {}

    # Primitive types
    if annotation in _PY_TYPE_TO_JSON:
        return {"type": _PY_TYPE_TO_JSON[annotation]}

    # list / list[T]
    if annotation is list or origin is list:
        schema: dict = {"type": "array"}
        args = get_args(annotation)
        if args:
            schema["items"] = _type_to_json_schema(args[0])
        return schema

    # dict / dict[str, T]
    if annotation is dict or origin is dict:
        return {"type": "object"}

    # Pydantic models
    if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
        return annotation.model_json_schema()

    return {}


def _build_parameters_schema(func: Callable, ignore_params: set[str]) -> dict:
    """Build a JSON Schema 'parameters' object from a function signature."""
    sig = inspect.signature(func)
    properties: dict[str, dict] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ignore_params:
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        prop = _type_to_json_schema(param.annotation)

        # Extract description from docstring param lines (simple parser)
        # For now, just use the type info
        properties[name] = prop

        # Required if no default
        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema: dict = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _parse_docstring_params(docstring: str | None) -> dict[str, str]:
    """Extract parameter descriptions from Google/Sphinx-style docstrings.

    Handles:
    - Google style (``Args:`` section with indented ``name: desc``)
    - Sphinx style (``:param name: desc``)
    - Multi-line continuation for both styles
    - Skips ``Returns:``, ``Raises:``, ``Yields:`` and other non-param sections
    """
    if not docstring:
        return {}

    descriptions: dict[str, str] = {}
    lines = inspect.cleandoc(docstring).split("\n")

    _STOP_SECTIONS = {"returns:", "raises:", "yields:", "examples:", "note:", "notes:"}
    in_args = False
    current_param: str | None = None
    args_indent: int | None = None  # indentation of param lines inside Args

    for line in lines:
        stripped = line.strip()

        # --- Sphinx style: :param name: description ---
        if stripped.startswith(":param "):
            rest = stripped[7:]
            if ":" in rest:
                pname, desc = rest.split(":", 1)
                pname = pname.strip()
                descriptions[pname] = desc.strip()
                current_param = pname
                in_args = False
            continue

        # --- Section headers ---
        if stripped.endswith(":") and not stripped.startswith(" "):
            lower = stripped.lower()
            if lower == "args:" or lower == "arguments:" or lower == "parameters:":
                in_args = True
                current_param = None
                args_indent = None
                continue
            if lower in _STOP_SECTIONS:
                in_args = False
                current_param = None
                continue

        if not in_args:
            # Multi-line continuation for Sphinx params
            if current_param and stripped:
                descriptions[current_param] += " " + stripped
            else:
                current_param = None
            continue

        # --- Inside Args section ---
        if not stripped:
            current_param = None
            continue

        # Determine indentation
        content_indent = len(line) - len(line.lstrip())

        # First param line sets the reference indent
        if args_indent is None and ":" in stripped:
            args_indent = content_indent

        # Continuation line (more indented than param lines)
        if args_indent is not None and content_indent > args_indent and current_param:
            descriptions[current_param] += " " + stripped
            continue

        # New param line: ``name: desc`` or ``name (type): desc``
        if ":" in stripped:
            head, _, desc = stripped.partition(":")
            candidate = head.strip()
            # Strip type annotation in parentheses: ``name (int)``
            if "(" in candidate:
                candidate = candidate.split("(")[0].strip()
            if candidate.isidentifier() and len(candidate) < 40:
                descriptions[candidate] = desc.strip()
                current_param = candidate
                args_indent = content_indent
            else:
                current_param = None
        else:
            current_param = None

    # Clean up: strip trailing whitespace from all values
    return {k: v.strip() for k, v in descriptions.items() if v.strip()}


# ---------------------------------------------------------------------------
# FunctionTool
# ---------------------------------------------------------------------------


class FunctionTool(BaseTool):
    """A tool that wraps a Python function.

    Automatically extracts:
    - **name** from ``func.__name__``
    - **description** from the docstring
    - **parameters schema** from type hints
    """

    def __init__(self, func: Callable[..., Any]) -> None:
        name = getattr(func, "__name__", func.__class__.__name__)
        doc = inspect.cleandoc(func.__doc__ or "") if func.__doc__ else ""
        # Use first line of docstring as description
        description = doc.split("\n")[0] if doc else ""

        super().__init__(name=name, description=description)
        self.func = func
        self._ignore_params = {"tool_context"}

    def get_declaration(self) -> Optional[dict]:
        """Build an OpenAI-compatible function declaration."""
        schema = _build_parameters_schema(self.func, self._ignore_params)

        # Enrich with docstring param descriptions
        param_docs = _parse_docstring_params(self.func.__doc__)
        for pname, desc in param_docs.items():
            if pname in schema.get("properties", {}):
                schema["properties"][pname]["description"] = desc

        return {
            "name": self.name,
            "description": self.description,
            "parameters": schema,
        }

    async def run_async(self, *, args: dict[str, Any], tool_context: Any) -> Any:
        """Execute the wrapped function."""
        args_to_call = self._preprocess_args(args)

        sig = inspect.signature(self.func)
        valid_params = set(sig.parameters)

        # Inject tool_context if the function accepts it
        if "tool_context" in valid_params:
            args_to_call["tool_context"] = tool_context

        # Filter to only valid params
        args_to_call = {k: v for k, v in args_to_call.items() if k in valid_params}

        # Check mandatory args
        missing = [
            name
            for name, param in sig.parameters.items()
            if param.default is inspect.Parameter.empty
            and param.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
            and name not in args_to_call
        ]
        if missing:
            return {"error": f"Missing required parameters: {', '.join(missing)}"}

        # Invoke (handle sync and async)
        result = self.func(**args_to_call)
        if inspect.iscoroutine(result):
            result = await result
        return result

    def _preprocess_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Convert dict args to Pydantic models where expected."""
        sig = inspect.signature(self.func)
        converted = args.copy()
        for pname, param in sig.parameters.items():
            if pname not in args or param.annotation is inspect.Parameter.empty:
                continue
            target = param.annotation
            # Unwrap Optional[T]
            if get_origin(target) is Union:
                non_none = [a for a in get_args(target) if a is not type(None)]
                if len(non_none) == 1:
                    target = non_none[0]
            if (
                inspect.isclass(target)
                and issubclass(target, pydantic.BaseModel)
                and isinstance(args[pname], dict)
            ):
                try:
                    converted[pname] = target.model_validate(args[pname])
                except pydantic.ValidationError as exc:
                    logger.warning(
                        "Tool '%s' param '%s' Pydantic validation failed "
                        "(%d error(s)). Falling back to raw dict.",
                        self.name,
                        pname,
                        exc.error_count(),
                    )
        return converted
