"""Colab results as one zip: `manifest.json` + files, each with a SHA-256 (`closet-worker import`).

Kinds and where they go on the Mac:
- `compat`: the outfit model head (colab/outfit_compat.ipynb) → COMPAT_MODEL_DIR. Installing a
  new model removes the old gate, so it stays off until `compat-eval` measures it again.
- `fit_gate`: which fits the tagging eval measured as reliable (eval/tagging.py) → FIT_GATE_PATH.
- `heads`: trained garment heads (colab/garment_heads.ipynb) → HEADS_DIR. Each head carries its
  own gate from your labeled photos; vision/heads.py re-checks it.

Import refuses anything it doesn't expect: unknown kinds or names, paths, a missing or
mismatched checksum, or very large files. Nothing in a zip is ever run.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

VERSION = 1
MAX_BYTES = 600 * 1024 * 1024
KINDS: dict[str, frozenset[str]] = {
    "compat": frozenset({"compat_head.safetensors", "compat_config.json", "MODEL_CARD.md"}),
    "fit_gate": frozenset({"fit_gate.json", "report.json"}),
    "heads": frozenset({"heads.safetensors", "heads.json", "MODEL_CARD.md"}),
}
REQUIRED: dict[str, frozenset[str]] = {
    "compat": frozenset({"compat_head.safetensors", "compat_config.json"}),
    "fit_gate": frozenset({"fit_gate.json"}),
    "heads": frozenset({"heads.safetensors", "heads.json"}),
}


class BundleError(Exception):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bundle(kind: str, files: dict[str, Path], out: Path) -> Path:
    if kind not in KINDS or not set(files) <= KINDS[kind]:
        raise BundleError(f"unknown kind or file names for {kind}")
    manifest = {
        "kind": kind,
        "version": VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "files": {n: sha256_bytes(p.read_bytes()) for n, p in sorted(files.items())},
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        for n, p in sorted(files.items()):
            z.write(p, n)
    return out


@dataclass(frozen=True)
class Bundle:
    kind: str
    created_at: str
    files: dict[str, bytes]


def read_bundle(path: Path) -> Bundle:
    try:
        z = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as e:
        raise BundleError(f"{path.name} isn’t a zip file") from e
    with z:
        infos = {i.filename: i for i in z.infolist() if not i.is_dir()}
        if "manifest.json" not in infos:
            raise BundleError("no manifest.json: this isn’t a Closet results zip")
        try:
            m = json.loads(z.read("manifest.json"))
        except ValueError as e:
            raise BundleError("manifest.json isn’t valid JSON") from e
        kind = m.get("kind")
        if kind not in KINDS or m.get("version") != VERSION:
            raise BundleError(f"unknown results kind {kind!r} (version {m.get('version')!r})")
        want: dict[str, str] = m.get("files") or {}
        extra = set(infos) - {"manifest.json"} - set(want)
        bad = [n for n in [*want, *extra] if n not in KINDS[kind]]
        if bad or extra:
            raise BundleError(f"unexpected files in the zip: {sorted(set(bad) | extra)}")
        if missing := REQUIRED[kind] - set(want):
            raise BundleError(f"missing from the zip: {sorted(missing)}")
        files: dict[str, bytes] = {}
        for n, digest in want.items():
            if n not in infos:
                raise BundleError(f"{n} is listed but not in the zip")
            if infos[n].file_size > MAX_BYTES:
                raise BundleError(f"{n} is too large")
            data = z.read(n)
            if sha256_bytes(data) != digest:
                raise BundleError(f"{n} doesn’t match its checksum: download the zip again")
            files[n] = data
    return Bundle(kind, str(m.get("created_at") or ""), files)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def install(
    b: Bundle, compat_dir: Path, fit_gate_path: Path, heads_dir: Path | None = None
) -> list[Path]:
    """Write the files where the worker reads them. Returns what was written."""
    written: list[Path] = []
    if b.kind == "compat":
        # A new model hasn't been measured on your outfits: close the gate first.
        (compat_dir / "gate.json").unlink(missing_ok=True)
        # The config (with the weights' checksum) goes last, so a half-copied install never loads.
        for n in sorted(b.files, key=lambda n: n == "compat_config.json"):
            _write_atomic(compat_dir / n, b.files[n])
            written.append(compat_dir / n)
    elif b.kind == "heads":
        if heads_dir is None:
            raise BundleError("no folder set for garment heads")
        # heads.json carries the weights' checksum and the gate, so it goes last.
        for n in sorted(b.files, key=lambda n: n == "heads.json"):
            _write_atomic(heads_dir / n, b.files[n])
            written.append(heads_dir / n)
    elif b.kind == "fit_gate":
        _write_atomic(fit_gate_path, b.files["fit_gate.json"])
        written.append(fit_gate_path)
        if "report.json" in b.files:
            _write_atomic(fit_gate_path.with_name("report.json"), b.files["report.json"])
            written.append(fit_gate_path.with_name("report.json"))
    return written
