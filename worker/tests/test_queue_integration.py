"""Round trip against the local Supabase stack (`supabase start`). Skipped when it's not running."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import httpx
import pytest

from closet_worker.config import Settings
from closet_worker.main import process
from closet_worker.queue import SupabaseQueue

URL = os.environ.get("CLOSET_TEST_SUPABASE_URL", "http://127.0.0.1:55421")
# The fixed, public demo service key every local Supabase stack uses.
LOCAL_SERVICE_KEY = os.environ.get(
    "CLOSET_TEST_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vf"
    "cm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",
)


def _up() -> bool:
    try:
        return httpx.get(
            f"{URL}/auth/v1/health", timeout=1, headers={"apikey": LOCAL_SERVICE_KEY}
        ).is_success
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _up(), reason="local Supabase not running"),
]


@pytest.fixture
def q() -> Iterator[SupabaseQueue]:
    base = SupabaseQueue(
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            supabase_url=URL,
            supabase_service_role_key=LOCAL_SERVICE_KEY,  # type: ignore[arg-type]
            owner_user_id=uuid.uuid4(),
            worker_id=f"test-{uuid.uuid4().hex[:6]}",
        )
    )
    email = f"worker-test-{uuid.uuid4().hex[:8]}@example.test"
    user = base.db.auth.admin.create_user({"email": email, "email_confirm": True}).user
    s = base.s.model_copy(update={"owner_user_id": uuid.UUID(user.id)})
    queue = SupabaseQueue(s, base.db)
    yield queue
    base.db.auth.admin.delete_user(user.id)  # cascades to every row


def test_ping_round_trip(q: SupabaseQueue) -> None:
    q.heartbeat("test", {"searxng": False, "ollama": False, "openai": False})
    q.enqueue("ping", {"nonce": "n1"})
    job = q.claim()
    assert job is not None and job.kind == "ping" and job.attempts == 1
    assert q.claim() is None  # skip-locked: nothing else to claim for this owner
    process(q, job, fake=False)
    row = q.db.table("jobs").select("status,result").eq("id", job.id).single().execute().data
    assert row["status"] == "done"
    assert row["result"]["echo"] == "n1"
    w = q.db.table("workers").select("user_id").eq("id", q.s.worker_id).single().execute().data
    assert w["user_id"] == q.s.owner


def test_claim_only_owner_jobs(q: SupabaseQueue) -> None:
    other = q.db.auth.admin.create_user(
        {"email": f"other-{uuid.uuid4().hex[:8]}@example.test", "email_confirm": True}
    ).user
    try:
        q.db.table("jobs").insert({"kind": "ping", "user_id": other.id}).execute()
        assert q.claim() is None
    finally:
        q.db.auth.admin.delete_user(other.id)


def test_compat_reads_embeddings_and_events(q: SupabaseQueue) -> None:
    from closet_worker.recsys.compat import EMBEDDER, status
    from closet_worker.store import SupabaseItemStore

    store = SupabaseItemStore(q.db, q.s.owner)
    item = (
        q.db.table("items")
        .insert({"user_id": q.s.owner, "name": "Navy chinos", "category": "Bottoms"})
        .execute()
        .data[0]
    )
    vec = [0.0] * 512
    vec[3] = 1.0
    store.upsert_embedding(item["id"], EMBEDDER, vec)
    got = store.list_embeddings(EMBEDDER)
    assert list(got) == [item["id"]] and got[item["id"]][3] == 1.0 and len(got[item["id"]]) == 512
    assert store.list_embeddings("other-model") == {}
    store.insert_events(
        [{"occasion": "office", "item_ids": [item["id"]], "context": {}, "action": "worn"}]
    )
    evs = store.list_suggestion_events()
    assert [e["action"] for e in evs] == ["worn"] and evs[0]["item_ids"] == [item["id"]]
    # The heartbeat accepts the nested outfit model status.
    q.heartbeat("test", {"searxng": False, "compat": status(q.s.compat_model_dir)})
    w = q.db.table("workers").select("capabilities").eq("id", q.s.worker_id).single().execute()
    assert w.data["capabilities"]["compat"]["need"] == 30
