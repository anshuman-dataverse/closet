"""`closet-worker restore`: put a backup back into a Supabase project.

The target needs Closet's schema already (fresh project: `supabase db push`; local:
`supabase db reset`) and must not already hold this owner's rows. Steps:

1. Check every dump against the SHA-256 in its manifest.
2. Load the sign-in record, then every table, in one transaction with triggers off
   (session_replication_role=replica) so the "new user → profile" trigger can't add duplicates.
3. Upload the photos from BACKUP_DIR/files back to the wardrobe bucket.
4. Compare row counts with the manifest and report any difference.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jobs.backup import TABLES, psql_out, sha256_file

BUCKET = "wardrobe"


class RestoreError(Exception):
    pass


@dataclass
class Plan:
    db_dir: Path
    manifest: dict[str, Any]


def check(db_dir: Path) -> Plan:
    mf = db_dir / "manifest.json"
    if not mf.exists():
        raise RestoreError(f"no manifest.json in {db_dir}: not a Closet backup")
    manifest = json.loads(mf.read_text())
    for table, info in manifest["dumps"].items():
        p = db_dir / f"{table}.csv"
        if not p.exists():
            raise RestoreError(f"{p.name} is missing from {db_dir}")
        if sha256_file(p) != info["sha256"]:
            raise RestoreError(f"{p.name} doesn’t match its checksum: this backup is damaged")
    return Plan(db_dir, manifest)


def restore_db(plan: Plan, db_url: str) -> None:
    """One transaction: triggers off (so "new user → profile" can't add a duplicate), sign-in
    record first, then every table. Any error rolls everything back."""
    lines = ["BEGIN;", "SET LOCAL session_replication_role = replica;"]
    dumps = plan.manifest["dumps"]
    for t in sorted(dumps, key=lambda t: (not t.startswith("auth."), t)):
        f = plan.db_dir / f"{t}.csv"
        lines.append(
            f"\\copy {t} ({dumps[t]['columns']}) from '{f}' with (format csv, header true)"
        )
    lines.append("COMMIT;")
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False) as fh:
        fh.write("\n".join(lines) + "\n")
        script = Path(fh.name)
    try:
        psql_out(["-f", str(script)], db_url)
    except RuntimeError as e:
        raise RestoreError(f"nothing was restored: {e}") from e
    finally:
        script.unlink(missing_ok=True)


def restore_files(files_dir: Path, owner: str, db: Any) -> int:
    """Upload every backed-up photo under the owner's folder. Existing files are replaced."""
    root = files_dir / owner
    if not root.exists():
        return 0
    bucket = db.storage.from_(BUCKET)
    n = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        path = p.relative_to(files_dir).as_posix()
        kind = "image/webp" if p.suffix == ".webp" else "image/jpeg"
        bucket.upload(path, p.read_bytes(), {"content-type": kind, "upsert": "true"})
        n += 1
    return n


def compare_counts(plan: Plan, now: dict[str, int]) -> list[str]:
    want = plan.manifest.get("rows") or {}
    return [f"{t}: backup {want[t]}, restored {now.get(t)}" for t in want if now.get(t) != want[t]]


def owner_exists(db_url: str, owner: str) -> bool:
    import uuid

    o = str(uuid.UUID(owner))
    out = psql_out(["-c", f"select count(*) from auth.users where id = '{o}'"], db_url).strip()
    return out != "0"


def run_restore(db_dir: Path, files_dir: Path, db_url: str, db: Any) -> dict[str, Any]:
    from .store import SupabaseItemStore

    plan = check(db_dir)
    owner = str(plan.manifest["owner"])
    if owner_exists(db_url, owner):
        raise RestoreError(
            "the target already has this person’s account; restore only where it doesn’t exist"
        )
    restore_db(plan, db_url)
    uploaded = restore_files(files_dir, owner, db)
    counts = SupabaseItemStore(db, owner).count_rows(TABLES)
    return {
        "owner": owner,
        "files": uploaded,
        "rows": counts,
        "mismatch": compare_counts(plan, counts),
    }
