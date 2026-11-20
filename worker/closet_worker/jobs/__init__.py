"""Job handlers: one module per kind. A handler takes the job payload and returns a result dict.

Handlers must be idempotent: running a job again overwrites its own results.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import ping

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class TransientError(Exception):
    """A failure worth retrying (network blip, store timeout)."""


class NotImplementedYet(Exception):
    """The kind exists in the schema but its phase hasn't been built."""


@dataclass(frozen=True)
class Spec:
    handler: Handler | None
    timeout_s: float


def _todo(kind: str) -> Spec:
    return Spec(handler=None, timeout_s=60)


# Every kind allowed by the jobs.kind check constraint.
REGISTRY: dict[str, Spec] = {
    "ping": Spec(handler=ping.run, timeout_s=10),
    "tag_item": _todo("tag_item"),
    "embed_wish": _todo("embed_wish"),
    "analyze_profile": _todo("analyze_profile"),
    "suggest_outfits": _todo("suggest_outfits"),
    "check_wish": _todo("check_wish"),
    "find_gaps": _todo("find_gaps"),
    "run_hunt": _todo("run_hunt"),
    "price_check": _todo("price_check"),
    "train_ranker": _todo("train_ranker"),
    "backup": _todo("backup"),
}

TIMEOUTS_S: dict[str, float] = {
    "tag_item": 120,
    "analyze_profile": 180,
    "run_hunt": 300,
    "train_ranker": 540,
    "backup": 540,
}


def spec_for(kind: str) -> Spec:
    base = REGISTRY.get(kind)
    if base is None:
        raise KeyError(kind)
    return Spec(handler=base.handler, timeout_s=TIMEOUTS_S.get(kind, base.timeout_s))


def implemented() -> set[str]:
    return {k for k, v in REGISTRY.items() if v.handler is not None}
