"""The job queue, backed by Supabase. Every query is scoped to OWNER_USER_ID."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel
from supabase import Client, create_client

from .config import Settings


class Job(BaseModel):
    id: str
    kind: str
    payload: dict[str, Any] = {}
    attempts: int = 0
    priority: int = 0
    user_id: str


class Queue(Protocol):
    def claim(self) -> Job | None: ...
    def complete(self, job: Job, result: dict[str, Any]) -> None: ...
    def fail(self, job: Job, error: str) -> None: ...
    def heartbeat(self, version: str, capabilities: dict[str, Any]) -> None: ...
    def requeue_stale(self) -> int: ...
    def enqueue(self, kind: str, payload: dict[str, Any] | None = None) -> None: ...


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SupabaseQueue:
    def __init__(self, settings: Settings, client: Client | None = None) -> None:
        self.s = settings
        self.db = client or create_client(
            settings.supabase_url, settings.supabase_service_role_key.get_secret_value()
        )

    def claim(self) -> Job | None:
        res = self.db.rpc(
            "claim_job", {"p_worker": self.s.worker_id, "p_user": self.s.owner}
        ).execute()
        rows = res.data if isinstance(res.data, list) else []
        return Job.model_validate(rows[0]) if rows else None

    def _finish(self, job: Job, fields: dict[str, Any]) -> None:
        (
            self.db.table("jobs")
            .update({**fields, "finished_at": now_iso()})
            .eq("id", job.id)
            .eq("user_id", self.s.owner)
            .execute()
        )

    def complete(self, job: Job, result: dict[str, Any]) -> None:
        self._finish(job, {"status": "done", "result": result, "error": None})

    def fail(self, job: Job, error: str) -> None:
        self._finish(job, {"status": "failed", "error": error[:500]})

    def heartbeat(self, version: str, capabilities: dict[str, Any]) -> None:
        self.db.table("workers").upsert(
            {
                "id": self.s.worker_id,
                "user_id": self.s.owner,
                "last_seen_at": now_iso(),
                "version": version,
                "capabilities": capabilities,
            }
        ).execute()

    def requeue_stale(self) -> int:
        res = self.db.rpc("requeue_stale_jobs", {}).execute()
        return res.data if isinstance(res.data, int) else 0

    def enqueue(self, kind: str, payload: dict[str, Any] | None = None) -> None:
        self.db.table("jobs").insert(
            {"kind": kind, "payload": payload or {}, "user_id": self.s.owner}
        ).execute()
