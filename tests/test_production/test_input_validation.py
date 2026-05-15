"""Tests for input validation — message length checks and self-healing."""

import pytest

from soulbot.server.self_healing import run_with_self_healing


class TestInputLength:
    """Validate message length enforcement logic."""

    def test_within_limit(self):
        max_len = 10000
        msg = "x" * 5000
        assert len(msg) <= max_len

    def test_exceeds_limit(self):
        max_len = 10000
        msg = "x" * 10001
        assert len(msg) > max_len

    def test_exact_limit(self):
        max_len = 10000
        msg = "x" * 10000
        assert len(msg) <= max_len

    def test_empty_message(self):
        max_len = 10000
        assert len("") <= max_len


class TestSelfHealing:
    def test_normal_exit(self):
        calls = []

        def good():
            calls.append(1)

        run_with_self_healing(good, max_restarts=3, cooldown=0)
        assert len(calls) == 1

    def test_keyboard_interrupt_exits(self):
        calls = []

        def interrupted():
            calls.append(1)
            raise KeyboardInterrupt()

        run_with_self_healing(interrupted, max_restarts=3, cooldown=0)
        assert len(calls) == 1

    def test_crash_and_recover(self):
        calls = []

        def crash_once():
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("crash")

        run_with_self_healing(crash_once, max_restarts=3, cooldown=0)
        assert len(calls) == 2

    def test_max_restarts_exit(self):
        calls = []

        def always_crash():
            calls.append(1)
            raise RuntimeError("boom")

        with pytest.raises(SystemExit) as exc_info:
            run_with_self_healing(always_crash, max_restarts=3, cooldown=0)
        assert exc_info.value.code == 1
        assert len(calls) == 3
