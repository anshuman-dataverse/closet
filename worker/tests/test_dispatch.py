from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from closet_worker import jobs as jobs_mod
from closet_worker.config import Settings
from closet_worker.jobs import REGISTRY, Spec, TransientError
from closet_worker.main import Worker, execute, process
from closet_worker.scheduler import Scheduler

from .conftest import MemoryQueue, job

SCHEMA_KINDS = {
    "ping",
    "tag_item",
    "read_label",
    "embed_wish",
    "analyze_profile",
    "suggest_outfits",
    "check_wish",
    "find_gaps",
    "run_hunt",
    "price_check",
    "train_ranker",
    "backup",
}


def test_registry_matches_schema() -> None:
    assert set(REGISTRY) == SCHEMA_KINDS


def test_ping_round_trip() -> None:
    q = MemoryQueue([job("ping", {"nonce": "abc"})])
    process(q, q.claim(), fake=False)  # type: ignore[arg-type]
    assert q.done["j1"]["pong"] is True
    assert q.done["j1"]["echo"] == "abc"


def test_unbuilt_kind_fails_clearly() -> None:
    q = MemoryQueue()
    process(q, job("train_ranker"), fake=False)  # Phase 6
    assert "isn't built yet" in q.failed["j1"]


def test_fake_mode_returns_fixture_for_every_kind() -> None:
    for kind in SCHEMA_KINDS:
        assert isinstance(execute(job(kind), fake=True), dict)


def test_transient_errors_retry_then_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def flaky(_: dict[str, Any], __: Any = None) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientError("blip")
        return {"ok": True}

    monkeypatch.setitem(REGISTRY, "ping", Spec(handler=flaky, timeout_s=5))
    sleeps: list[float] = []
    assert execute(job("ping"), fake=False, sleep=sleeps.append) == {"ok": True}
    assert sleeps == [1.0, 2.0]


def test_transient_errors_give_up_after_three(monkeypatch: pytest.MonkeyPatch) -> None:
    def always(_: dict[str, Any], __: Any = None) -> dict[str, Any]:
        raise TransientError("store down")

    monkeypatch.setitem(REGISTRY, "ping", Spec(handler=always, timeout_s=5))
    with pytest.raises(TransientError):
        execute(job("ping"), fake=False, sleep=lambda _: None)


def test_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(_: dict[str, Any], __: Any = None) -> dict[str, Any]:
        time.sleep(0.5)
        return {}

    monkeypatch.setitem(REGISTRY, "ping", Spec(handler=slow, timeout_s=0.05))
    monkeypatch.setitem(jobs_mod.TIMEOUTS_S, "ping", 0.05)
    q = MemoryQueue()
    process(q, job("ping"), fake=False)
    assert q.failed["j1"].startswith("Timed out")


def test_tick_runs_one_job_and_requeues(settings: Settings, tmp_path: Path) -> None:
    q = MemoryQueue([job("ping", id="a"), job("ping", id="b")])
    w = Worker(settings, q, fake=True, scheduler=Scheduler(tmp_path / "s.json"))
    assert w.tick() is True
    assert set(q.done) == {"a"}
    assert q.requeues == 1
    w.run(once=True)
    assert set(q.done) == {"a", "b"}
    assert q.beats  # heartbeat sent


def test_rerun_is_idempotent() -> None:
    q = MemoryQueue()
    process(q, job("ping", {"nonce": "x"}), fake=True)
    first = q.done["j1"]["echo"]
    process(q, job("ping", {"nonce": "x"}), fake=True)
    assert q.done["j1"]["echo"] == first


@pytest.mark.parametrize(
    "url",
    [
        "https://rmrjfznkvjdvsfjuegii.supabase.co",
        "http://192.168.1.5:54321",
        "https://localhost.evil.com",
    ],
)
def test_fake_mode_refuses_any_real_database(settings: Settings, url: str) -> None:
    from closet_worker.main import FakeModeRefused, Worker

    real = settings.model_copy(update={"supabase_url": url})
    with pytest.raises(FakeModeRefused, match="only runs against local Supabase"):
        Worker(real, MemoryQueue(), fake=True)
    Worker(real, MemoryQueue(), fake=False)  # the real worker is unaffected


def test_fake_mode_runs_locally(settings: Settings) -> None:
    from closet_worker.main import Worker

    assert Worker(settings, MemoryQueue(), fake=True).fake  # 127.0.0.1 in the test settings
