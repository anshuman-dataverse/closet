"""Backup pieces that don't need a database: connection settings, photo sync, pruning."""

from __future__ import annotations

from pathlib import Path

import pytest

from closet_worker.jobs import backup
from closet_worker.jobs.tag_item import BadJob


def test_pg_env_keeps_the_password_off_the_command_line() -> None:
    env = backup.pg_env(
        "postgresql://postgres.abc:p%40ss@aws-0.pooler.supabase.com:6543/postgres?sslmode=require"
    )
    assert env == {
        "PGHOST": "aws-0.pooler.supabase.com",
        "PGPORT": "6543",
        "PGUSER": "postgres.abc",
        "PGPASSWORD": "p@ss",
        "PGDATABASE": "postgres",
        "PGSSLMODE": "require",
    }
    with pytest.raises(BadJob, match="DATABASE_URL"):
        backup.pg_env("mysql://x")


class Files:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.downloads: list[str] = []

    def list_files(self) -> list[tuple[str, int]]:
        return [(p, len(b)) for p, b in self.files.items()]

    def download(self, path: str) -> bytes:
        self.downloads.append(path)
        return self.files[path]


def test_sync_copies_only_new_or_changed_and_never_escapes(tmp_path: Path) -> None:
    store = Files({"u/items/a/1.jpg": b"aaa", "u/items/a/1_thumb.jpg": b"b", "../evil.jpg": b"x"})
    r = backup.sync_files(store, tmp_path / "files")
    assert (r.total, r.new) == (2, 2) and not (tmp_path / "evil.jpg").exists()
    assert (tmp_path / "files/u/items/a/1.jpg").read_bytes() == b"aaa"
    store.downloads.clear()
    assert backup.sync_files(store, tmp_path / "files").new == 0 and store.downloads == []
    store.files["u/items/a/1.jpg"] = b"changed!"
    assert backup.sync_files(store, tmp_path / "files").new == 1


def test_prune_keeps_the_newest(tmp_path: Path) -> None:
    for d in range(1, 18):
        (tmp_path / f"2026-11-{d:02d}T020000Z").mkdir()
    removed = backup.prune(tmp_path, keep=14)
    assert removed == ["2026-11-01T020000Z", "2026-11-02T020000Z", "2026-11-03T020000Z"]
    assert len(list(tmp_path.iterdir())) == 14


def test_copy_models_skips_what_isnt_installed(tmp_path: Path) -> None:
    (tmp_path / "heads").mkdir()
    (tmp_path / "heads" / "heads.json").write_text("{}")
    got = backup.copy_models(
        {"heads": tmp_path / "heads", "compat": tmp_path / "none"}, tmp_path / "out"
    )
    assert got == ["heads"] and (tmp_path / "out/heads/heads.json").exists()
