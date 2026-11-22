from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from closet_worker.config import Settings
from closet_worker.scheduler import DAILY, Scheduler, daily_due

NIGHTLY = DAILY[0]
ALL = {"train_ranker", "backup", "price_check"}


def test_not_due_before_slot() -> None:
    assert not daily_due(NIGHTLY, datetime(2026, 11, 20, 1, 59), None)


def test_due_after_slot_once_per_day() -> None:
    now = datetime(2026, 11, 20, 2, 0)
    assert daily_due(NIGHTLY, now, None)
    assert not daily_due(NIGHTLY, now, date(2026, 11, 20))


def test_catch_up_on_wake(tmp_path: Path) -> None:
    # Mac slept through 02:00 and 09:00; on wake at 11:30 both run once.
    s = Scheduler(tmp_path / "s.json")
    s.last_daily = {"nightly": date(2026, 11, 19), "morning": date(2026, 11, 19)}
    kinds = s.due_kinds(datetime(2026, 11, 20, 11, 30), ALL)
    assert sorted(kinds) == ["backup", "price_check", "train_ranker"]
    assert s.due_kinds(datetime(2026, 11, 20, 11, 31), ALL) == []


def test_state_persists(tmp_path: Path) -> None:
    p = tmp_path / "s.json"
    Scheduler(p).due_kinds(datetime(2026, 11, 20, 3, 0), ALL)
    assert Scheduler(p).last_daily["nightly"] == date(2026, 11, 20)


def test_unbuilt_kinds_skipped(tmp_path: Path) -> None:
    s = Scheduler(tmp_path / "s.json")
    assert s.due_kinds(datetime(2026, 11, 20, 10, 0), set()) == []


def test_requeue_every_ten_minutes(tmp_path: Path) -> None:
    s = Scheduler(tmp_path / "s.json")
    t = datetime(2026, 11, 20, 12, 0)
    assert s.requeue_due(t)
    assert not s.requeue_due(t + timedelta(minutes=9))
    assert s.requeue_due(t + timedelta(minutes=10))


def test_fake_worker_keeps_its_own_schedule_file(settings: Settings) -> None:
    from closet_worker.main import Worker
    from closet_worker.scheduler import STATE_PATH

    from .conftest import MemoryQueue

    assert (
        Worker(settings, MemoryQueue(), fake=True).scheduler.state_path.name
        == "scheduler-fake.json"
    )
    assert Worker(settings, MemoryQueue(), fake=False).scheduler.state_path == STATE_PATH
