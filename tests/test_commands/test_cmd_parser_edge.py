"""Tests for command parser — edge cases."""

import pytest

from soulbot.commands.parser import parse_commands, _find_json_end


class TestEscapedQuotes:
    def test_escaped_quotes_in_value(self):
        text = r'<!--SOULBOT_CMD:{"service":"fs","action":"write","content":"He said \"hello\""}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1
        assert 'He said "hello"' in cmds[0].params["content"]

    def test_backslash_in_path(self):
        text = r'<!--SOULBOT_CMD:{"service":"fs","action":"read","path":"C:\\Users\\test"}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1
        assert "Users" in cmds[0].params["path"]


class TestMissingFields:
    def test_missing_service(self):
        text = '<!--SOULBOT_CMD:{"action":"run"}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0

    def test_missing_action(self):
        text = '<!--SOULBOT_CMD:{"service":"test"}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0

    def test_empty_json(self):
        text = "<!--SOULBOT_CMD:{}-->"
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0


class TestMalformed:
    def test_invalid_json(self):
        text = "<!--SOULBOT_CMD:{invalid json}-->"
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 0
        assert "SOULBOT_CMD" not in cleaned  # cleanup regex removes it

    def test_unclosed_brace(self):
        text = '<!--SOULBOT_CMD:{"service":"test","action":"run"'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0

    def test_no_suffix(self):
        text = '<!--SOULBOT_CMD:{"service":"test","action":"run"}'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0

    def test_prefix_only(self):
        text = "<!--SOULBOT_CMD: some garbage"
        cmds, _ = parse_commands(text)
        assert len(cmds) == 0

    def test_no_json_after_prefix(self):
        text = "<!--SOULBOT_CMD: not json -->"
        cmds, cleaned = parse_commands(text)
        assert len(cmds) == 0


class TestWhitespace:
    def test_whitespace_after_prefix(self):
        text = '<!--SOULBOT_CMD: {"service":"test","action":"run"}-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1

    def test_newline_in_command(self):
        text = '<!--SOULBOT_CMD:\n{"service":"test","action":"run"}\n-->'
        cmds, _ = parse_commands(text)
        assert len(cmds) == 1


class TestFindJsonEnd:
    def test_simple(self):
        assert _find_json_end('{"a":1}', 0) == 7

    def test_nested(self):
        assert _find_json_end('{"a":{"b":2}}', 0) == 13

    def test_string_with_braces(self):
        assert _find_json_end('{"a":"{not nested}"}', 0) == 20

    def test_no_closing(self):
        assert _find_json_end('{"a":1', 0) == -1

    def test_empty_object(self):
        assert _find_json_end('{}', 0) == 2


class TestCleanedText:
    def test_multiline_cleanup(self):
        text = "Before\n\n\n\n<!--SOULBOT_CMD:{\"service\":\"s\",\"action\":\"a\"}-->\n\n\n\nAfter"
        _, cleaned = parse_commands(text)
        assert "\n\n\n" not in cleaned
        assert "Before" in cleaned
        assert "After" in cleaned

    def test_raw_preserved_in_command(self):
        raw_text = '<!--SOULBOT_CMD:{"service":"s","action":"a","x":1}-->'
        cmds, _ = parse_commands(f"text {raw_text} more")
        assert cmds[0].raw == raw_text
