"""Backup then restore against local Supabase: delete a user completely, bring everything back."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pytest
from pydantic import SecretStr

from closet_worker.config import Settings
from closet_worker.jobs import backup
from closet_worker.jobs.context import JobContext
from closet_worker.restore import RestoreError, run_restore
from closet_worker.store import SupabaseItemStore

from .test_queue_integration import LOCAL_SERVICE_KEY, URL, _up

LOCAL_DB = "postgresql://postgres:postgres@127.0.0.1:55422/postgres"
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _up(), reason="local Supabase not running"),
    pytest.mark.skipif(
        not any(Path(d, "pg_dump").exists() for d in backup.PG_BIN_DIRS)
        and not shutil.which("pg_dump"),
        reason="pg_dump not installed (brew install libpq)",
    ),
]


def test_backup_and_restore_round_trip(tmp_path: Path) -> None:
    from supabase import create_client

    db = create_client(URL, LOCAL_SERVICE_KEY)
    user = db.auth.admin.create_user(
        {"email": f"bk-{uuid.uuid4().hex[:8]}@example.test", "email_confirm": True}
    ).user
    owner = user.id
    try:
        store = SupabaseItemStore(db, owner)
        db.table("profiles").update({"wears": "menswear", "monthly_budget_cents": 12345}).eq(
            "user_id", owner
        ).execute()
        item = (
            db.table("items")
            .insert(
                {
                    "user_id": owner,
                    "name": "Wide jeans",
                    "category": "Bottoms",
                    "fit": "wide",
                    "photo_path": f"{owner}/items/x/a.jpg",
                }
            )
            .execute()
            .data[0]
        )
        db.table("wear_logs").insert(
            {"user_id": owner, "worn_on": "2026-11-20", "occasion": "office"}
        ).execute()
        photo = b"\xff\xd8\xff" + bytes(range(256)) * 40
        db.storage.from_("wardrobe").upload(
            f"{owner}/items/{item['id']}/a.jpg", photo, {"content-type": "image/jpeg"}
        )

        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            supabase_url=URL,
            supabase_service_role_key=LOCAL_SERVICE_KEY,  # type: ignore[arg-type]
            owner_user_id=uuid.UUID(owner),
            database_url=SecretStr(LOCAL_DB),
            backup_dir=tmp_path / "ClosetBackups",
            compat_model_dir=tmp_path / "compat",
            heads_dir=tmp_path / "heads",
            fit_gate_path=tmp_path / "fit.json",
        )
        r = backup.run({}, JobContext(settings=settings, items=store))
        assert r["rows"]["items"] == 1 and r["rows"]["wear_logs"] == 1 and r["files_total"] == 1
        stamp = settings.backup_dir / "db" / r["stamp"]
        assert (stamp / "public.items.csv").stat().st_mode & 0o777 == 0o600
        assert (
            settings.backup_dir / "files" / owner / "items" / item["id"] / "a.jpg"
        ).read_bytes() == photo
        again = backup.run({}, JobContext(settings=settings, items=store))
        assert again["files_new"] == 0  # photos already backed up aren't downloaded again

        # Lose everything: the photo, then the user (cascades to every row).
        db.storage.from_("wardrobe").remove([f"{owner}/items/{item['id']}/a.jpg"])
        db.auth.admin.delete_user(owner)
        assert store.count_rows(("items",)) == {"items": 0}

        out = run_restore(stamp, settings.backup_dir / "files", LOCAL_DB, db)
        assert out["mismatch"] == [] and out["files"] == 1
        back = db.table("items").select("name, fit").eq("user_id", owner).execute().data
        assert back == [{"name": "Wide jeans", "fit": "wide"}]
        prof = (
            db.table("profiles")
            .select("wears, monthly_budget_cents")
            .eq("user_id", owner)
            .single()
            .execute()
            .data
        )
        assert prof == {
            "wears": "menswear",
            "monthly_budget_cents": 12345,
        }  # restored, not a fresh default row
        assert db.storage.from_("wardrobe").download(f"{owner}/items/{item['id']}/a.jpg") == photo
        assert db.auth.admin.get_user_by_id(owner).user.email == user.email

        with pytest.raises(RestoreError, match="already has"):
            run_restore(stamp, settings.backup_dir / "files", LOCAL_DB, db)
        manifest = json.loads((stamp / "manifest.json").read_text())
        (stamp / "public.items.csv").write_bytes(b"corrupt")
        with pytest.raises(RestoreError, match="checksum"):
            run_restore(stamp, settings.backup_dir / "files", LOCAL_DB, db)
        assert manifest["owner"] == owner
    finally:
        try:
            db.storage.from_("wardrobe").remove(
                [p for p, _ in SupabaseItemStore(db, owner).list_storage()]
            )
            db.auth.admin.delete_user(owner)
        except Exception:
            pass
