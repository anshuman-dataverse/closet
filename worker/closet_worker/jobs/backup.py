"""`backup` (SPEC 10): nightly, or "Back up now". Everything lands in BACKUP_DIR on this Mac.

    BACKUP_DIR/
      db/<UTC stamp>/<schema.table>.csv   your rows only (one snapshot), computed columns left out
      db/<UTC stamp>/manifest.json        columns, row counts (checked) and SHA-256 per file
      files/<storage path>           every photo in the wardrobe bucket (new ones only each run)
      models/                        installed outfit model, fit gate, garment heads

Only the owner's rows are backed up (each person in a shared project gets their own backup). The
14 newest database backups are kept. A file whose rows don't match the snapshot's count fails
the job, so a broken backup is never reported as done. Restore: `closet-worker restore` (README).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .context import JobContext
from .tag_item import BadJob

KEEP = 14
PG_BIN_DIRS = ("/opt/homebrew/opt/libpq/bin", "/usr/local/opt/libpq/bin", "/usr/bin")
TABLES = (
    "profiles",
    "items",
    "item_embeddings",
    "outfits",
    "outfit_items",
    "wear_logs",
    "wear_log_items",
    "wishlist_items",
    "style_photos",
    "suggestion_events",
)


def pg_tool(name: str) -> str:
    """pg_dump / pg_restore from Homebrew's libpq, or PATH."""
    for d in PG_BIN_DIRS:
        p = Path(d) / name
        if p.exists():
            return str(p)
    found = shutil.which(name)
    if not found:
        raise BadJob(f"{name} isn’t installed. Run: brew install libpq")
    return found


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def private_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def pg_env(db_url: str) -> dict[str, str]:
    """postgresql://user:pass@host:port/db?sslmode=… as PG* variables, so the password never
    appears on a command line (where `ps` would show it)."""
    from urllib.parse import parse_qs, unquote, urlparse

    u = urlparse(db_url)
    if u.scheme not in ("postgres", "postgresql") or not u.hostname:
        raise BadJob("DATABASE_URL must look like postgresql://user:password@host:5432/postgres")
    env = {
        "PGHOST": u.hostname,
        "PGPORT": str(u.port or 5432),
        "PGUSER": unquote(u.username or "postgres"),
        "PGPASSWORD": unquote(u.password or ""),
        "PGDATABASE": (u.path or "/postgres").lstrip("/") or "postgres",
    }
    mode = parse_qs(u.query).get("sslmode")
    if mode:
        env["PGSSLMODE"] = mode[0]
    return env


def run_pg(args: list[str], db_url: str) -> None:
    env = {**os.environ, **pg_env(db_url)}
    r = subprocess.run(args, env=env, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(f"{Path(args[0]).name} failed: {msg[-1] if msg else r.returncode}")


# Which rows are yours: public tables by user_id, auth.users by id, auth.identities by user_id.
COLUMNS_SQL = """
select c.table_schema || '.' || c.table_name,
       string_agg(quote_ident(c.column_name), ',' order by c.ordinal_position)
from information_schema.columns c
join information_schema.tables t
  on t.table_schema = c.table_schema and t.table_name = c.table_name
where c.is_generated = 'NEVER'
  and t.table_type = 'BASE TABLE'
  and ((c.table_schema = 'public' and c.table_name in (
          select table_name from information_schema.columns
          where table_schema = 'public' and column_name = 'user_id'))
       or (c.table_schema = 'auth' and c.table_name in ('users', 'identities')))
group by 1 order by 1
"""


def owner_column(table: str) -> str:
    return "id" if table == "auth.users" else "user_id"


def psql_out(sql_args: list[str], db_url: str) -> str:
    env = {**os.environ, **pg_env(db_url)}
    r = subprocess.run(
        [pg_tool("psql"), "--no-psqlrc", "-At", "-v", "ON_ERROR_STOP=1", *sql_args],
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if r.returncode != 0:
        lines = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(f"psql failed: {' | '.join(lines[-3:]) if lines else r.returncode}")
    return r.stdout


def dump_database(db_url: str, owner: str, out: Path) -> dict[str, Any]:
    """Your rows only, from one consistent snapshot, as CSV per table (computed columns left
    out). Row counts come from the same snapshot, and each file is checked against them."""
    import csv
    import uuid

    owner = str(uuid.UUID(owner))  # validated: it goes into SQL below
    tables: dict[str, str] = {}
    for line in psql_out(["-c", COLUMNS_SQL], db_url).splitlines():
        name, cols = line.split("|", 1)
        tables[name] = cols
    script = ["BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;"]
    for t, cols in tables.items():
        f = out / f"{t}.csv"
        where = f"{owner_column(t)} = '{owner}'"
        script.append(
            f"\\copy (select {cols} from {t} where {where}) to '{f}' with (format csv, header true)"
        )
        script.append(f"select '{t}', count(*) from {t} where {where};")
    script.append("COMMIT;")
    sql = out / ".backup.sql"
    sql.write_text("\n".join(script) + "\n")
    counts: dict[str, int] = {}
    try:
        for line in psql_out(["-f", str(sql)], db_url).splitlines():
            if "|" in line:
                name, num = line.split("|")
                counts[name] = int(num)
    finally:
        sql.unlink(missing_ok=True)
    info: dict[str, Any] = {}
    for t, cols in tables.items():
        f = out / f"{t}.csv"
        f.chmod(0o600)
        with f.open(newline="") as fh:
            rows = sum(1 for _ in csv.reader(fh)) - 1
        if rows != counts.get(t):
            raise RuntimeError(f"{t}: wrote {rows} rows but the database had {counts.get(t)}")
        info[t] = {
            "rows": rows,
            "columns": cols,
            "sha256": sha256_file(f),
            "bytes": f.stat().st_size,
        }
    if counts.get("auth.users") != 1:
        raise RuntimeError("your sign-in record wasn’t found: check OWNER_USER_ID")
    return info


class FileStore(Protocol):
    def list_files(self) -> list[tuple[str, int]]: ...  # (path, size) for every object
    def download(self, path: str) -> bytes: ...


@dataclass
class SyncResult:
    total: int
    new: int
    bytes_new: int
    bytes_total: int


def sync_files(store: FileStore, dest: Path) -> SyncResult:
    """Copy objects missing locally (or with a different size). Never deletes local copies."""
    total = new = bytes_new = bytes_total = 0
    root = dest.resolve()
    for path, size in store.list_files():
        target = (dest / path).resolve()
        if root not in target.parents:  # a path that would escape the backup folder
            continue
        total += 1
        bytes_total += size
        if target.exists() and target.stat().st_size == size:
            continue
        data = store.download(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(f".{target.name}.part")
        tmp.write_bytes(data)
        tmp.chmod(0o600)
        os.replace(tmp, target)
        new += 1
        bytes_new += len(data)
    return SyncResult(total, new, bytes_new, bytes_total)


def copy_models(sources: dict[str, Path], dest: Path) -> list[str]:
    copied = []
    for name, src in sources.items():
        if src.exists():
            target = dest / name
            if src.is_dir():
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)
            copied.append(name)
    return copied


def prune(db_dir: Path, keep: int = KEEP) -> list[str]:
    stamps = sorted((p for p in db_dir.iterdir() if p.is_dir()), key=lambda p: p.name)
    removed = []
    for p in stamps[:-keep] if len(stamps) > keep else []:
        shutil.rmtree(p)
        removed.append(p.name)
    return removed


def run(payload: dict[str, Any], ctx: JobContext | None) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    s = ctx.settings
    if s.database_url is None:
        raise BadJob("Set DATABASE_URL in worker/.env (Supabase → Connect → direct connection).")
    root = private_dir(s.backup_dir)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    out = private_dir(private_dir(root / "db") / stamp)
    try:
        dumps = dump_database(s.database_url.get_secret_value(), ctx.items.owner, out)
    except Exception:
        shutil.rmtree(out, ignore_errors=True)  # never leave a half backup behind
        raise
    files = sync_files(StorageFiles(ctx), private_dir(root / "files"))
    models = copy_models(
        {"compat": s.compat_model_dir, "heads": s.heads_dir, "fit/gate.json": s.fit_gate_path},
        private_dir(root / "models"),
    )
    counts = ctx.items.count_rows(TABLES)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "owner": ctx.items.owner,
        "dumps": dumps,
        "rows": counts,
        "files": files.__dict__,
        "models": models,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out / "manifest.json").chmod(0o600)
    removed = prune(root / "db")
    return {
        "stamp": stamp,
        "db_bytes": sum(d["bytes"] for d in dumps.values()),
        "tables": len(dumps),
        "files_total": files.total,
        "files_new": files.new,
        "files_bytes": files.bytes_total,
        "rows": counts,
        "pruned": removed,
    }


class StorageFiles:
    """Every object under the owner's folder in the wardrobe bucket."""

    def __init__(self, ctx: JobContext) -> None:
        assert ctx.items is not None
        self.items = ctx.items

    def list_files(self) -> list[tuple[str, int]]:
        return self.items.list_storage()

    def download(self, path: str) -> bytes:
        return self.items.download(path)
