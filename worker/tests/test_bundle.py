"""Colab results zips (bundle.py): write, verify, refuse, install."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from closet_worker.bundle import BundleError, install, read_bundle, sha256_bytes, write_bundle


def files(tmp: Path, **content: bytes) -> dict[str, Path]:
    out = {}
    for name, data in content.items():
        p = tmp / name.replace("__", ".")
        p.write_bytes(data)
        out[p.name] = p
    return out


def raw_zip(path: Path, manifest: object, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("manifest.json", json.dumps(manifest))
        for n, d in entries.items():
            z.writestr(n, d)
    return path


def test_round_trip_and_install_fit_gate(tmp_path: Path) -> None:
    src = files(tmp_path, fit_gate__json=b'{"per_fit": {}}', report__json=b"{}")
    z = write_bundle("fit_gate", src, tmp_path / "out" / "r.zip")
    b = read_bundle(z)
    assert b.kind == "fit_gate" and set(b.files) == {"fit_gate.json", "report.json"}
    gate = tmp_path / "mac" / "fit" / "gate.json"
    written = install(b, tmp_path / "mac" / "compat", gate)
    assert gate.read_bytes() == b'{"per_fit": {}}' and len(written) == 2


def test_new_compat_model_closes_the_old_gate(tmp_path: Path) -> None:
    compat = tmp_path / "compat"
    compat.mkdir()
    (compat / "gate.json").write_text('{"open": true}')
    src = files(tmp_path, compat_head__safetensors=b"w", compat_config__json=b"{}")
    b = read_bundle(write_bundle("compat", src, tmp_path / "c.zip"))
    install(b, compat, tmp_path / "fit.json")
    assert not (compat / "gate.json").exists()
    assert (compat / "compat_head.safetensors").read_bytes() == b"w"


@pytest.mark.parametrize(
    ("manifest", "entries", "msg"),
    [
        ({"kind": "evil", "version": 1, "files": {}}, {}, "unknown results kind"),
        (
            {"kind": "fit_gate", "version": 1, "files": {"fit_gate.json": sha256_bytes(b"x")}},
            {"fit_gate.json": b"y"},
            "checksum",
        ),
        (
            {"kind": "fit_gate", "version": 1, "files": {"../x.json": sha256_bytes(b"x")}},
            {"../x.json": b"x"},
            "unexpected files",
        ),
        (
            {"kind": "fit_gate", "version": 1, "files": {"fit_gate.json": sha256_bytes(b"x")}},
            {"fit_gate.json": b"x", "run.sh": b"rm -rf /"},
            "unexpected files",
        ),
        ({"kind": "compat", "version": 1, "files": {}}, {}, "missing from the zip"),
        (
            {"kind": "fit_gate", "version": 1, "files": {"fit_gate.json": sha256_bytes(b"x")}},
            {},
            "listed but not in the zip",
        ),
    ],
)
def test_refuses_bad_zips(
    tmp_path: Path, manifest: object, entries: dict[str, bytes], msg: str
) -> None:
    with pytest.raises(BundleError, match=msg):
        read_bundle(raw_zip(tmp_path / "bad.zip", manifest, entries))


def test_not_a_zip(tmp_path: Path) -> None:
    (tmp_path / "x.zip").write_text("nope")
    with pytest.raises(BundleError, match="isn’t a zip"):
        read_bundle(tmp_path / "x.zip")
    with zipfile.ZipFile(tmp_path / "y.zip", "w") as z:
        z.writestr("a.txt", "a")
    with pytest.raises(BundleError, match="no manifest"):
        read_bundle(tmp_path / "y.zip")
