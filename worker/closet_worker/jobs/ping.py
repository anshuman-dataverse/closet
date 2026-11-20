"""`ping`: proves the round trip app -> queue -> Mac -> app."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from closet_worker import __version__


def run(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "pong": True,
        "echo": str(payload.get("nonce", ""))[:64],
        "worker_version": __version__,
        "at": datetime.now(UTC).isoformat(),
    }
