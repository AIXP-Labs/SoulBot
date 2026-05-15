"""Heartbeat registration — seed CronTrigger for agents with heartbeat config."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .schedule_service import ScheduleService

logger = logging.getLogger(__name__)

_CATCH_UP_THRESHOLD = timedelta(hours=25)
"""Catch-up if last_run exceeds this threshold.
25h (not 24h) to avoid false positives from DST transitions."""


def register_heartbeats(
    agents: dict[str, Any],
    schedule_service: ScheduleService,
) -> tuple[int, list[str]]:
    """Scan agents for heartbeat config and register seed CronTriggers.

    Each agent with a ``heartbeat`` dict attribute gets a daily seed
    CronTrigger that kicks off the recursive OnceTrigger chain.

    Args:
        agents: ``{name: agent_instance}`` dict.
        schedule_service: The schedule service to register entries with.

    Returns:
        ``(registered_count, catch_up_ids)`` — number of new seeds registered,
        and list of entry IDs that need catch-up firing (missed seed).
        The caller must invoke ``schedule_service._on_fired(entry_id=id)``
        for each catch-up ID in an async context.
    """
    registered = 0
    catch_up_ids: list[str] = []

    for name, agent in agents.items():
        hb = getattr(agent, "heartbeat", None)
        if not hb or not isinstance(hb, dict):
            continue

        cron_expr = hb.get("cron", "0 0 * * *")
        entry_id = f"hb_{name}"

        # Check if already registered (active entry exists)
        existing = schedule_service._entries.get(entry_id)
        if existing and existing.status == "active":
            # Check catch-up: missed seed → queue for async firing
            if _should_catch_up(existing):
                logger.info(
                    "Heartbeat catch-up needed: %s missed last seed",
                    entry_id,
                )
                catch_up_ids.append(entry_id)
            else:
                logger.debug("Heartbeat %s already active, skipping", entry_id)
            continue

        # Parse cron expression into trigger config
        try:
            trigger_config = _cron_expr_to_config(cron_expr)
        except ValueError as exc:
            logger.warning("Heartbeat registration failed for %s: %s", name, exc)
            continue

        try:
            schedule_service.add(
                trigger=trigger_config,
                task={"message": "heartbeat wakeup", "id": entry_id},
                origin_channel="heartbeat",
                from_agent=name,
                to_agent=name,
            )
            registered += 1
            logger.info("Heartbeat registered: %s (cron=%s)", entry_id, cron_expr)
        except ValueError:
            # Already exists (e.g. restored from DB)
            logger.debug("Heartbeat %s already exists", entry_id)

    return registered, catch_up_ids


def _should_catch_up(entry: Any) -> bool:
    """Check if a heartbeat seed was missed and needs catch-up.

    Returns True if the entry's last_run is more than 25 hours ago
    (i.e. missed at least one daily seed).
    """
    if not entry.last_run:
        return True  # Never ran → catch up

    try:
        last = datetime.fromisoformat(entry.last_run)
        return datetime.now() - last > _CATCH_UP_THRESHOLD
    except (ValueError, TypeError):
        return True


def _cron_expr_to_config(expr: str) -> dict:
    """Convert a 5-field cron expression to a trigger config dict.

    ``"0 0 * * *"`` → ``{"type": "cron", "hour": 0, "minute": 0}``
    """
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expr}")

    minute, hour, day, month, dow = parts

    config: dict[str, Any] = {"type": "cron"}

    if minute != "*":
        config["minute"] = int(minute)
    if hour != "*":
        config["hour"] = int(hour)
    if day != "*":
        raise ValueError(
            f"CronTrigger does not support day-of-month field: {expr}. "
            "Use '* * * * *' format with only minute/hour/day_of_week."
        )
    if month != "*":
        raise ValueError(
            f"CronTrigger does not support month field: {expr}. "
            "Use '* * * * *' format with only minute/hour/day_of_week."
        )
    if dow != "*":
        config["day_of_week"] = dow  # keep str — CronTrigger expects str | None

    return config
