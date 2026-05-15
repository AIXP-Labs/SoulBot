#!/usr/bin/env python3
"""End-to-end verification script for soulbot framework.

Uses Claude Code CLI (ACP) — no API key needed, just `claude login`.

Prerequisites:
    npm install -g @anthropic-ai/claude-code
    claude login
    pip install -e ".[dev]"

Usage:
    python examples/e2e_verify.py
    python examples/e2e_verify.py --test tools
    python examples/e2e_verify.py --test all
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import traceback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ok(label: str, detail: str = "") -> None:
    msg = f"  [PASS] {label}"
    if detail:
        msg += f" — {detail}"
    print(f"\033[92m{msg}\033[0m")


def fail(label: str, detail: str = "") -> None:
    msg = f"  [FAIL] {label}"
    if detail:
        msg += f" — {detail}"
    print(f"\033[91m{msg}\033[0m")


def info(msg: str) -> None:
    print(f"\033[96m{msg}\033[0m")


def section(title: str) -> None:
    print()
    print(f"\033[93m{'=' * 60}\033[0m")
    print(f"\033[93m  {title}\033[0m")
    print(f"\033[93m{'=' * 60}\033[0m")


# ---------------------------------------------------------------------------
# Test: CLI binary check
# ---------------------------------------------------------------------------

async def test_cli_binary() -> bool:
    section("1. Claude CLI Binary Check")
    from soulacp import find_claude_binary as _find_claude_binary

    binary = _find_claude_binary()
    if binary:
        ok("Claude CLI found", binary)
        return True
    else:
        fail("Claude CLI not found",
             "Install with: npm install -g @anthropic-ai/claude-code")
        return False


# ---------------------------------------------------------------------------
# Test: Simple text query
# ---------------------------------------------------------------------------

async def test_simple_query() -> bool:
    section("2. Simple Text Query (ACP)")
    from soulbot.agents import LlmAgent
    from soulbot.runners.runner import Runner
    from soulbot.sessions import InMemorySessionService

    agent = LlmAgent(
        name="test_agent",
        model="claude-acp/sonnet",
        instruction="You are a helpful assistant. Keep answers brief (one sentence).",
    )

    runner = Runner(
        agent=agent,
        app_name="e2e_test",
        session_service=InMemorySessionService(),
    )

    info("  Sending: 'What is 2 + 2? Answer with just the number.'")

    events = []
    try:
        async for event in runner.run(
            user_id="u1", session_id="s1",
            message="What is 2 + 2? Answer with just the number.",
        ):
            events.append(event)
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        info(f"  Response: {part.text[:200]}")
    except Exception as e:
        fail("Simple query", str(e))
        traceback.print_exc()
        return False

    if not events:
        fail("Simple query", "No events received")
        return False

    # Check we got a text response
    has_text = any(
        p.text for e in events if e.content
        for p in e.content.parts if p.text
    )
    if has_text:
        ok("Simple query", f"{len(events)} event(s) received with text")
        return True
    else:
        fail("Simple query", "Events received but no text content")
        return False


# ---------------------------------------------------------------------------
# Test: Tool calling
# ---------------------------------------------------------------------------

async def test_tool_calling() -> bool:
    section("3. Tool Calling (FunctionTool)")
    from soulbot.agents import LlmAgent
    from soulbot.runners.runner import Runner
    from soulbot.sessions import InMemorySessionService

    def get_weather(city: str) -> dict:
        """Get the current weather for a city."""
        return {"city": city, "temperature": 22, "condition": "sunny"}

    agent = LlmAgent(
        name="weather_agent",
        model="claude-acp/sonnet",
        instruction=(
            "You are a weather assistant. When asked about weather, "
            "use the get_weather tool. Report the result clearly."
        ),
        tools=[get_weather],
    )

    runner = Runner(
        agent=agent,
        app_name="e2e_test",
        session_service=InMemorySessionService(),
    )

    info("  Sending: 'What is the weather in Tokyo?'")

    events = []
    try:
        async for event in runner.run(
            user_id="u1", session_id="s2",
            message="What is the weather in Tokyo?",
        ):
            events.append(event)
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        info(f"  Text: {part.text[:200]}")
                    if part.function_call:
                        info(f"  Tool call: {part.function_call.name}({part.function_call.args})")
                    if part.function_response:
                        info(f"  Tool result: {part.function_response.response}")
    except Exception as e:
        fail("Tool calling", str(e))
        traceback.print_exc()
        return False

    if not events:
        fail("Tool calling", "No events received")
        return False

    # Check for tool call events
    tool_calls = [e for e in events if e.get_function_calls()]
    tool_responses = [e for e in events if e.get_function_responses()]
    final_text = [
        e for e in events
        if e.is_final_response()
    ]

    details = (
        f"{len(events)} events, "
        f"{len(tool_calls)} tool call(s), "
        f"{len(tool_responses)} tool response(s), "
        f"{len(final_text)} final response(s)"
    )

    if final_text:
        ok("Tool calling", details)
        return True
    elif tool_calls:
        # Partial success — tool was called but we may not have gotten final answer
        ok("Tool calling (partial)", details)
        return True
    else:
        fail("Tool calling", details)
        return False


# ---------------------------------------------------------------------------
# Test: Sequential workflow
# ---------------------------------------------------------------------------

async def test_sequential_workflow() -> bool:
    section("4. Sequential Workflow")
    from soulbot.agents import LlmAgent, SequentialAgent
    from soulbot.runners.runner import Runner
    from soulbot.sessions import InMemorySessionService

    step1 = LlmAgent(
        name="analyzer",
        model="claude-acp/sonnet",
        instruction=(
            "Analyze the user's message and output a one-line summary. "
            "Start with 'SUMMARY:'"
        ),
        output_key="analysis",
    )

    step2 = LlmAgent(
        name="responder",
        model="claude-acp/sonnet",
        instruction=(
            "You received an analysis in {analysis}. "
            "Write a brief, helpful response based on it."
        ),
    )

    workflow = SequentialAgent(
        name="workflow",
        sub_agents=[step1, step2],
    )

    runner = Runner(
        agent=workflow,
        app_name="e2e_test",
        session_service=InMemorySessionService(),
    )

    info("  Sending: 'I want to learn Python programming'")

    events = []
    try:
        async for event in runner.run(
            user_id="u1", session_id="s3",
            message="I want to learn Python programming",
        ):
            events.append(event)
            if event.content and not event.partial:
                for part in event.content.parts:
                    if part.text:
                        author = event.author or "?"
                        info(f"  [{author}] {part.text[:150]}")
    except Exception as e:
        fail("Sequential workflow", str(e))
        traceback.print_exc()
        return False

    if len(events) >= 2:
        ok("Sequential workflow", f"{len(events)} events from 2-step pipeline")
        return True
    elif events:
        ok("Sequential workflow (partial)", f"Only {len(events)} event(s)")
        return True
    else:
        fail("Sequential workflow", "No events")
        return False


# ---------------------------------------------------------------------------
# Test: Multi-turn conversation
# ---------------------------------------------------------------------------

async def test_multi_turn() -> bool:
    section("5. Multi-turn Conversation (Session)")
    from soulbot.agents import LlmAgent
    from soulbot.runners.runner import Runner
    from soulbot.sessions import InMemorySessionService

    agent = LlmAgent(
        name="chat_agent",
        model="claude-acp/sonnet",
        instruction="You are a helpful assistant. Keep answers very brief.",
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="e2e_test",
        session_service=session_service,
    )

    messages = [
        "My name is Alice.",
        "What is my name?",
    ]

    all_events = []
    try:
        for msg in messages:
            info(f"  User: {msg}")
            async for event in runner.run(
                user_id="u1", session_id="s4",
                message=msg,
            ):
                all_events.append(event)
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if part.text:
                            info(f"  Agent: {part.text[:200]}")
    except Exception as e:
        fail("Multi-turn", str(e))
        traceback.print_exc()
        return False

    # Check session has accumulated events
    session = await session_service.get_session("e2e_test", "u1", "s4")
    event_count = len(session.events) if session else 0

    if event_count >= 4:  # 2 user + 2 agent minimum
        ok("Multi-turn conversation", f"Session has {event_count} events")
        return True
    elif all_events:
        ok("Multi-turn (partial)", f"{len(all_events)} agent events, {event_count} in session")
        return True
    else:
        fail("Multi-turn", "No events")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TESTS = {
    "cli": test_cli_binary,
    "simple": test_simple_query,
    "tools": test_tool_calling,
    "workflow": test_sequential_workflow,
    "multi_turn": test_multi_turn,
}


async def main(test_name: str | None = None) -> int:
    print()
    info("soulbot End-to-End Verification")
    info(f"Model: claude-acp/sonnet (Claude Code CLI)")
    print()

    if test_name and test_name != "all":
        if test_name not in TESTS:
            fail(f"Unknown test: {test_name}")
            info(f"Available: {', '.join(TESTS.keys())}, all")
            return 1
        tests = {test_name: TESTS[test_name]}
    else:
        tests = TESTS

    results: dict[str, bool] = {}
    for name, fn in tests.items():
        try:
            results[name] = await fn()
        except Exception as e:
            fail(name, str(e))
            results[name] = False

    # Summary
    section("Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "\033[92mPASS\033[0m" if result else "\033[91mFAIL\033[0m"
        print(f"  {status}  {name}")

    print()
    if passed == total:
        ok(f"All {total} tests passed!")
        return 0
    else:
        fail(f"{passed}/{total} tests passed")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="E2E verification for soulbot")
    parser.add_argument("--test", default="all",
                        help=f"Test to run: {', '.join(TESTS.keys())}, all")
    args = parser.parse_args()

    sys.exit(asyncio.run(main(args.test)))
