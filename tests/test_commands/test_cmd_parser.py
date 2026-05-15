"""Tests for command parser — basic extraction."""

import pytest

from soulbot.commands.parser import parse_commands, ParsedCommand, CMD_PREFIX, CMD_SUFFIX


class TestSingleCommand:
    def test_basic_command(self):
        text = 'Hello <!--SOULBOT_CMD:{"service":"schedule","action":"add","cron":"0 9 * * *"}-->'
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].service == "schedule"
        assert cmds[0].action == "add"
        assert cmds[0].params["cron"] == "0 9 * * *"
        assert "SOULBOT_CMD" not in cleaned
        assert "Hello" in cleaned

    def test_command_with_surrounding_text(self):
        text = (
            "I've set up the reminder.\n"
            '<!--SOULBOT_CMD:{"service":"notify","action":"send","message":"done"}-->\n'
            "Let me know if you need anything else."
        )
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].service == "notify"
        assert "set up the reminder" in cleaned
        assert "anything else" in cleaned

    def test_command_only(self):
        text = '<!--SOULBOT_CMD:{"service":"fs","action":"write","path":"test.md","content":"hello"}-->'
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].service == "fs"
        assert cmds[0].action == "write"
        assert cmds[0].params["path"] == "test.md"


class TestMultipleCommands:
    def test_two_commands(self):
        text = (
            '<!--SOULBOT_CMD:{"service":"s1","action":"a1"}-->'
            " middle "
            '<!--SOULBOT_CMD:{"service":"s2","action":"a2"}-->'
        )
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 2
        assert cmds[0].service == "s1"
        assert cmds[1].service == "s2"
        assert "middle" in cleaned

    def test_three_commands(self):
        text = (
            '<!--SOULBOT_CMD:{"service":"a","action":"x"}-->\n'
            '<!--SOULBOT_CMD:{"service":"b","action":"y"}-->\n'
            '<!--SOULBOT_CMD:{"service":"c","action":"z"}-->'
        )
        cmds, _ = parse_commands(text)
        assert len(cmds) == 3
        assert [c.service for c in cmds] == ["a", "b", "c"]


class TestNestedJSON:
    def test_nested_object(self):
        text = '<!--SOULBOT_CMD:{"service":"config","action":"set","data":{"key":"val","nested":{"deep":true}}}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].params["data"]["nested"]["deep"] is True

    def test_json_with_array(self):
        text = '<!--SOULBOT_CMD:{"service":"batch","action":"run","items":[1,2,3]}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].params["items"] == [1, 2, 3]


class TestMermaidSafety:
    def test_mermaid_arrow_not_confused(self):
        """Mermaid --> in JSON string should not close the command prematurely."""
        text = '<!--SOULBOT_CMD:{"service":"aisop","action":"set","workflow":"A --> B --> C"}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1
        assert cmds[0].params["workflow"] == "A --> B --> C"

    def test_mermaid_in_surrounding_text(self):
        text = (
            "Here's the flow: A --> B --> C\n"
            '<!--SOULBOT_CMD:{"service":"test","action":"run"}-->\n'
            "Done."
        )
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 1
        assert "A --> B --> C" in cleaned


class TestNoCommands:
    def test_plain_text(self):
        text = "Just regular text without any commands."
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 0
        assert cleaned == text

    def test_empty_string(self):
        cmds, cleaned = parse_commands("")
        assert len(cmds) == 0
        assert cleaned == ""

    def test_html_comment_not_command(self):
        text = "<!-- This is a regular HTML comment -->"
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 0


class TestConstants:
    def test_prefix(self):
        assert CMD_PREFIX == "<!--SOULBOT_CMD:"

    def test_suffix(self):
        assert CMD_SUFFIX == "-->"
