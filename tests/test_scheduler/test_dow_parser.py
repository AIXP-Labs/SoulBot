"""Tests for CronTrigger day-of-week parser."""

import pytest

from soulbot.scheduler.triggers import CronTrigger


class TestDayOfWeekParser:
    def test_single_name(self):
        result = CronTrigger._parse_day_of_week("mon")
        assert result == {0}

    def test_single_name_uppercase(self):
        result = CronTrigger._parse_day_of_week("MON")
        assert result == {0}

    def test_range_names(self):
        result = CronTrigger._parse_day_of_week("mon-fri")
        assert result == {0, 1, 2, 3, 4}

    def test_range_numbers(self):
        result = CronTrigger._parse_day_of_week("0-4")
        assert result == {0, 1, 2, 3, 4}

    def test_comma_separated(self):
        result = CronTrigger._parse_day_of_week("mon,wed,fri")
        assert result == {0, 2, 4}

    def test_single_number(self):
        result = CronTrigger._parse_day_of_week("6")
        assert result == {6}

    def test_mixed_range_and_single(self):
        result = CronTrigger._parse_day_of_week("mon-wed,fri")
        assert result == {0, 1, 2, 4}

    def test_weekend(self):
        result = CronTrigger._parse_day_of_week("sat,sun")
        assert result == {5, 6}

    def test_all_days(self):
        result = CronTrigger._parse_day_of_week("mon-sun")
        assert result == {0, 1, 2, 3, 4, 5, 6}

    def test_spaces_trimmed(self):
        result = CronTrigger._parse_day_of_week(" mon , fri ")
        assert result == {0, 4}

    def test_invalid_name_ignored(self):
        result = CronTrigger._parse_day_of_week("xyz")
        assert result == set()

    def test_trigger_uses_dow_set(self):
        trigger = CronTrigger(day_of_week="tue,thu")
        assert trigger._dow_set == {1, 3}
