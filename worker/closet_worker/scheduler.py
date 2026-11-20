"""Clock-driven tasks. Runs only while the Mac is awake and catches up on wake.

- every 10 minutes: requeue_stale_jobs
- 09:00 daily: price_check
- 02:00 nightly (or the next wake): train_ranker, backup

Last-run dates persist in ~/.closet/scheduler.json so a sleep across 02:00 still triggers on wake.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

STATE_PATH = Path("~/.closet/scheduler.json").expanduser()


@dataclass(frozen=True)
class Daily:
    name: str
    at: time
    kinds: tuple[str, ...]


DAILY: tuple[Daily, ...] = (
    Daily("nightly", time(2, 0), ("train_ranker", "backup")),
    Daily("morning", time(9, 0), ("price_check",)),
)
REQUEUE_EVERY = timedelta(minutes=10)


def daily_due(task: Daily, now: datetime, last_run: date | None) -> bool:
    """Due if today's slot has passed and it hasn't run today (catch-up after sleep)."""
    return now.time() >= task.at and (last_run is None or last_run < now.date())


class Scheduler:
    def __init__(self, state_path: Path = STATE_PATH) -> None:
        self.state_path = state_path
        self.last_requeue: datetime | None = None
        self.last_daily: dict[str, date] = self._load()

    def _load(self) -> dict[str, date]:
        try:
            raw = json.loads(self.state_path.read_text())
            return {k: date.fromisoformat(v) for k, v in raw.items()}
        except (OSError, ValueError, AttributeError):
            return {}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({k: v.isoformat() for k, v in self.last_daily.items()})
        )

    def requeue_due(self, now: datetime) -> bool:
        if self.last_requeue is None or now - self.last_requeue >= REQUEUE_EVERY:
            self.last_requeue = now
            return True
        return False

    def due_kinds(self, now: datetime, implemented: set[str]) -> list[str]:
        """Job kinds to enqueue now. Kinds whose handler isn't built yet are skipped."""
        out: list[str] = []
        changed = False
        for task in DAILY:
            if daily_due(task, now, self.last_daily.get(task.name)):
                self.last_daily[task.name] = now.date()
                changed = True
                out += [k for k in task.kinds if k in implemented]
        if changed:
            self._save()
        return out
