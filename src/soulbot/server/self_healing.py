"""Self-healing restart wrapper for long-running server processes."""

from __future__ import annotations

import logging
import sys
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_RESTARTS: int = 3
RESTART_COOLDOWN: int = 30  # seconds


def run_with_self_healing(
    func: Callable[..., Any],
    *args: Any,
    max_restarts: int = MAX_RESTARTS,
    cooldown: int = RESTART_COOLDOWN,
    **kwargs: Any,
) -> None:
    """Run *func* with automatic restart on crashes.

    - ``KeyboardInterrupt`` causes immediate exit (user intent).
    - Other exceptions trigger a restart after *cooldown* seconds.
    - After *max_restarts* consecutive failures, the process exits.

    Args:
        func: The entry-point callable (e.g. ``uvicorn.run``).
        max_restarts: Maximum restart attempts before giving up.
        cooldown: Seconds to wait between restarts.
    """
    for attempt in range(1, max_restarts + 1):
        try:
            func(*args, **kwargs)
            break  # clean exit
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
            break
        except Exception as exc:
            logger.error("Crash #%d: %s", attempt, exc)
            if attempt < max_restarts:
                logger.info("Restarting in %ds...", cooldown)
                time.sleep(cooldown)
            else:
                logger.critical("Max restarts (%d) reached. Exiting.", max_restarts)
                sys.exit(1)
