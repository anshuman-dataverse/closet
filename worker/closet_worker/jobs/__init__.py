"""Job handlers: one module per kind. A handler takes the job payload and returns a result dict.

Handlers must be idempotent: running a job again overwrites its own results.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import analyze_profile, check_wish, find_gaps, ping, read_label, suggest_outfits, tag_item
from .context import JobContext

Handler = Callable[[dict[str, Any], JobContext | None], dict[str, Any]]


class TransientError(Exception):
    """A failure worth retrying (network blip, store timeout)."""


BadJob = tag_item.BadJob


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
    "tag_item": Spec(handler=tag_item.run, timeout_s=180),
    "read_label": Spec(handler=read_label.run, timeout_s=60),
    "embed_wish": Spec(handler=check_wish.run_embed, timeout_s=120),
    "analyze_profile": Spec(handler=analyze_profile.run, timeout_s=180),
    "suggest_outfits": Spec(handler=suggest_outfits.run, timeout_s=60),
    "check_wish": Spec(handler=check_wish.run, timeout_s=180),
    "find_gaps": Spec(handler=find_gaps.run, timeout_s=120),
    "run_hunt": _todo("run_hunt"),
    "price_check": _todo("price_check"),
    "train_ranker": _todo("train_ranker"),
    "backup": _todo("backup"),
}

TIMEOUTS_S: dict[str, float] = {
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
