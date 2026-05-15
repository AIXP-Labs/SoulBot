"""Trigger types for the CronScheduler."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BaseTrigger(ABC):
    """Base class for schedule triggers."""

    @abstractmethod
    def next_fire_time(self, now: datetime) -> datetime | None:
        """Calculate the next fire time from *now*.

        Returns ``None`` if the trigger will never fire again.
        """
        ...

    def mark_fired(self, fire_time: float) -> None:
        """Notify the trigger that it has been executed.

        Subclasses override this to update internal state (e.g. last-fire
        timestamp) instead of having the scheduler mutate private attributes.
        """


@dataclass
class IntervalTrigger(BaseTrigger):
    """Fire at fixed intervals.

    At least one of *seconds*, *minutes*, or *hours* must be positive.
    """

    seconds: int = 0
    minutes: int = 0
    hours: int = 0
    _interval: float = field(init=False, repr=False)
    _last_fire: float | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self._interval = self.seconds + self.minutes * 60 + self.hours * 3600
        if self._interval <= 0:
            raise ValueError("Interval must be positive")

    @property
    def interval(self) -> float:
        return self._interval

    def next_fire_time(self, now: datetime) -> datetime:
        if self._last_fire is None:
            return now  # fire immediately the first time
        return datetime.fromtimestamp(self._last_fire + self._interval)

    def mark_fired(self, fire_time: float) -> None:
        self._last_fire = fire_time


@dataclass
class CronTrigger(BaseTrigger):
    """Fire at specific times (minute-level precision).

    Attributes:
        minute: 0–59 or None (any minute).
        hour: 0–23 or None (any hour).
        day_of_week: e.g. ``"mon"``, ``"mon-fri"``, ``"0-4"``,
            ``"mon,wed,fri"`` or None (any day).
    """

    minute: int | None = None
    hour: int | None = None
    day_of_week: str | None = None
    _dow_set: set[int] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if self.day_of_week:
            self._dow_set = self._parse_day_of_week(self.day_of_week)

    def next_fire_time(self, now: datetime) -> datetime | None:
        """Search minute-by-minute from *now + 1 min*, up to 7 days.

        Returns ``None`` if no matching time is found within the window,
        which causes the scheduler to mark the job as completed.
        """
        candidate = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        limit = now + timedelta(days=7)

        while candidate < limit:
            if self._matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        logger.warning(
            "CronTrigger: no match found within 7-day window "
            "(minute=%s, hour=%s, dow=%s). Check your cron configuration.",
            self.minute,
            self.hour,
            self.day_of_week,
        )
        return None

    def _matches(self, dt: datetime) -> bool:
        if self.minute is not None and dt.minute != self.minute:
            return False
        if self.hour is not None and dt.hour != self.hour:
            return False
        if self._dow_set is not None and dt.weekday() not in self._dow_set:
            return False
        return True

    @staticmethod
    def _parse_day_of_week(spec: str) -> set[int]:
        """Parse day-of-week specification.

        Supports: ``"mon"``, ``"mon-fri"``, ``"0-4"``, ``"mon,wed,fri"``
        Monday = 0, Sunday = 6.
        """
        day_map = {
            "mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6,
        }
        result: set[int] = set()
        for part in spec.lower().split(","):
            part = part.strip()
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = day_map.get(start_s, int(start_s) if start_s.isdigit() else -1)
                end = day_map.get(end_s, int(end_s) if end_s.isdigit() else -1)
                if start >= 0 and end >= 0:
                    result.update(range(start, end + 1))
            elif part in day_map:
                result.add(day_map[part])
            elif part.isdigit():
                result.add(int(part))
        return result


@dataclass
class OnceTrigger(BaseTrigger):
    """Fire exactly once.

    Specify either *delay* (seconds from now) or *run_at* (absolute time).
    """

    delay: float | None = None
    run_at: datetime | None = None
    _fired: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        if self.delay is None and self.run_at is None:
            raise ValueError("Must specify either delay or run_at")

    @property
    def fired(self) -> bool:
        return self._fired

    def next_fire_time(self, now: datetime) -> datetime | None:
        if self._fired:
            return None
        if self.run_at:
            return self.run_at
        return now + timedelta(seconds=self.delay)

    def mark_fired(self, fire_time: float) -> None:
        self._fired = True
