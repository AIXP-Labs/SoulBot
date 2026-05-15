"""Tests for command protocol integration — parse + execute end-to-end."""

import pytest

from soulbot.commands.parser import parse_commands
from soulbot.commands.executor import CommandExecutor


class MathService:
    def add(self, a: int, b: int) -> int:
        return a + b


class NotifyService:
    def __init__(self):
        self.sent = []

    async def send(self, channel: str, message: str) -> dict:
        self.sent.append({"channel": channel, "message": message})
        return {"sent": True}


class TestEndToEnd:
    async def test_parse_and_execute(self):
        text = (
            "The result is 7.\n"
            '<!--SOULBOT_CMD:{"service":"math","action":"add","a":3,"b":4}-->'
        )
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 1
        assert "The result is 7." in cleaned

        executor = CommandExecutor()
        executor.register_service("math", MathService())
        results = await executor.execute_all(cmds)

        assert results[0]["success"] is True
        assert results[0]["data"] == 7

    async def test_multiple_services(self):
        text = (
            '<!--SOULBOT_CMD:{"service":"math","action":"add","a":1,"b":2}-->\n'
            '<!--SOULBOT_CMD:{"service":"notify","action":"send","channel":"slack","message":"done"}-->'
        )
        cmds, _ = parse_commands(text)
        assert len(cmds) == 2

        notify = NotifyService()
        executor = CommandExecutor()
        executor.register_service("math", MathService())
        executor.register_service("notify", notify)
        results = await executor.execute_all(cmds)

        assert results[0]["data"] == 3
        assert results[1]["data"]["sent"] is True
        assert notify.sent[0]["channel"] == "slack"

    async def test_no_commands_noop(self):
        text = "Just regular text, no commands here."
        cmds, cleaned = parse_commands(text)

        executor = CommandExecutor()
        results = await executor.execute_all(cmds)

        assert len(results) == 0
        assert cleaned == text

    async def test_partial_failure(self):
        text = (
            '<!--SOULBOT_CMD:{"service":"math","action":"add","a":1,"b":2}-->\n'
            '<!--SOULBOT_CMD:{"service":"unknown","action":"do"}-->\n'
            '<!--SOULBOT_CMD:{"service":"math","action":"add","a":10,"b":20}-->'
        )
        cmds, _ = parse_commands(text)
        assert len(cmds) == 3

        executor = CommandExecutor()
        executor.register_service("math", MathService())
        results = await executor.execute_all(cmds)

        assert results[0]["success"] is True
        assert results[0]["data"] == 3
        assert results[1]["success"] is False
        assert results[2]["success"] is True
        assert results[2]["data"] == 30

    async def test_complex_llm_output(self):
        """Simulate realistic LLM output with commands embedded."""
        text = (
            "I've analyzed your request and here are the results:\n\n"
            "1. Your calculation: 5 + 3 = 8\n"
            '<!--SOULBOT_CMD:{"service":"math","action":"add","a":5,"b":3}-->\n\n'
            "2. I've also sent a notification:\n"
            '<!--SOULBOT_CMD:{"service":"notify","action":"send","channel":"email","message":"Calculation complete"}-->\n\n'
            "Let me know if you need anything else!"
        )
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 2
        assert "analyzed your request" in cleaned
        assert "need anything else" in cleaned
        assert "SOULBOT_CMD" not in cleaned
