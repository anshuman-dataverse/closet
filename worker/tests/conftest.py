from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from closet_worker.config import Settings
from closet_worker.queue import Job

OWNER = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    # Isolate from any real worker/.env and installed model files on this Mac.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        supabase_url="http://127.0.0.1:55421",
        supabase_service_role_key="test",  # type: ignore[arg-type]
        owner_user_id=OWNER,  # type: ignore[arg-type]
        compat_model_dir=tmp_path / "compat",
        fit_gate_path=tmp_path / "fit" / "gate.json",
    )


class MemoryQueue:
    """In-memory Queue for unit tests."""

    def __init__(self, jobs: list[Job] | None = None) -> None:
        self.jobs = list(jobs or [])
        self.done: dict[str, dict[str, Any]] = {}
        self.failed: dict[str, str] = {}
        self.beats: list[dict[str, bool]] = []
        self.enqueued: list[str] = []
        self.requeues = 0

    def claim(self) -> Job | None:
        return self.jobs.pop(0) if self.jobs else None

    def complete(self, job: Job, result: dict[str, Any]) -> None:
        self.done[job.id] = result

    def fail(self, job: Job, error: str) -> None:
        self.failed[job.id] = error

    def heartbeat(self, version: str, capabilities: dict[str, Any]) -> None:
        self.beats.append(capabilities)

    def requeue_stale(self) -> int:
        self.requeues += 1
        return 0

    def enqueue(self, kind: str, payload: dict[str, Any] | None = None) -> None:
        self.enqueued.append(kind)


def job(kind: str, payload: dict[str, Any] | None = None, id: str = "j1") -> Job:
    return Job(id=id, kind=kind, payload=payload or {}, user_id=OWNER)
