"""Tests for scheduler triggers — Interval, Cron, Once."""

import pytest
from datetime import datetime, timedelta

from soulbot.scheduler.triggers import (
    BaseTrigger,
    IntervalTrigger,
    CronTrigger,
    OnceTrigger,
)


class TestIntervalTrigger:
    def test_first_fire_is_immediate(self):
        trigger = IntervalTrigger(seconds=30)
        now = datetime(2026, 1, 1, 12, 0, 0)
        assert trigger.next_fire_time(now) == now

    def test_subsequent_fire_uses_interval(self):
        trigger = IntervalTrigger(seconds=60)
        trigger._last_fire = datetime(2026, 1, 1, 12, 0, 0).timestamp()
        result = trigger.next_fire_time(datetime(2026, 1, 1, 12, 0, 30))
        expected = datetime.fromtimestamp(trigger._last_fire + 60)
        assert result == expected

    def test_minutes_and_hours(self):
        trigger = IntervalTrigger(minutes=5, hours=1)
        assert trigger.interval == 3900  # 1h5m = 3900s

    def test_zero_interval_raises(self):
        with pytest.raises(ValueError, match="positive"):
            IntervalTrigger(seconds=0, minutes=0, hours=0)

    def test_negative_interval_raises(self):
        with pytest.raises(ValueError, match="positive"):
            IntervalTrigger(seconds=-10)

    def test_interval_property(self):
        trigger = IntervalTrigger(seconds=10, minutes=2)
        assert trigger.interval == 130


class TestCronTrigger:
    def test_minute_match(self):
        trigger = CronTrigger(minute=30)
        now = datetime(2026, 1, 1, 12, 0, 0)
        result = trigger.next_fire_time(now)
        assert result.minute == 30

    def test_hour_match(self):
        trigger = CronTrigger(hour=15)
        now = datetime(2026, 1, 1, 12, 0, 0)
        result = trigger.next_fire_time(now)
        assert result.hour == 15

    def test_minute_and_hour_match(self):
        trigger = CronTrigger(minute=0, hour=9)
        now = datetime(2026, 1, 1, 8, 59, 0)
        result = trigger.next_fire_time(now)
        assert result.hour == 9
        assert result.minute == 0

    def test_next_day_rollover(self):
        trigger = CronTrigger(minute=0, hour=8)
        now = datetime(2026, 1, 1, 9, 0, 0)
        result = trigger.next_fire_time(now)
        assert result.day == 2
        assert result.hour == 8

    def test_wildcard_fires_next_minute(self):
        trigger = CronTrigger()  # all wildcards
        now = datetime(2026, 1, 1, 12, 30, 0)
        result = trigger.next_fire_time(now)
        assert result == now.replace(second=0, microsecond=0) + timedelta(minutes=1)

    def test_day_of_week_filter(self):
        trigger = CronTrigger(minute=0, hour=9, day_of_week="mon")
        # 2026-01-05 is a Monday
        now = datetime(2026, 1, 4, 10, 0, 0)  # Sunday
        result = trigger.next_fire_time(now)
        assert result.weekday() == 0  # Monday

    def test_safety_fallback(self):
        """If no match in 7 days, returns None (job will be marked completed)."""
        trigger = CronTrigger(minute=0, hour=25)  # impossible hour
        now = datetime(2026, 1, 1, 0, 0, 0)
        result = trigger.next_fire_time(now)
        assert result is None


class TestOnceTrigger:
    def test_delay_fire(self):
        trigger = OnceTrigger(delay=10.0)
        now = datetime(2026, 1, 1, 12, 0, 0)
        result = trigger.next_fire_time(now)
        assert result == now + timedelta(seconds=10)

    def test_run_at_fire(self):
        target = datetime(2026, 6, 1, 0, 0, 0)
        trigger = OnceTrigger(run_at=target)
        result = trigger.next_fire_time(datetime(2026, 1, 1))
        assert result == target

    def test_no_repeat_after_fired(self):
        trigger = OnceTrigger(delay=5.0)
        trigger._fired = True
        assert trigger.next_fire_time(datetime(2026, 1, 1)) is None

    def test_fired_property(self):
        trigger = OnceTrigger(delay=1.0)
        assert trigger.fired is False
        trigger._fired = True
        assert trigger.fired is True

    def test_missing_args_raises(self):
        with pytest.raises(ValueError, match="delay or run_at"):
            OnceTrigger()


class TestBaseTrigger:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            BaseTrigger()
