"""`--fake` mode: every job kind returns a fixture right away (for e2e tests and UI work)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from closet_worker.jobs import ping

FIXTURES = Path(__file__).parent


def run(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "ping":
        return ping.run(payload)
    path = FIXTURES / f"{kind}.json"
    if path.exists():
        data: dict[str, Any] = json.loads(path.read_text())
        return data
    return {"fake": True, "kind": kind}
