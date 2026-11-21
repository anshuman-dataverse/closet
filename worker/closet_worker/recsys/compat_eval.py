"""`closet-worker compat-eval`: does the outfit model beat rules alone on your own picks?

For each outfit you wore, saved or liked from the ideas, rebuild that day's candidates (same
occasion, weather and note, wear history from before that day) and check whether it lands in the
top 3, ranked by rules alone and by rules + the outfit model. The gate opens only when the model
wins on at least MIN_EVENTS of your picks (SPEC 5.11).

This favors rules: you picked from ideas that rules ranked, so rules start ahead. The model
has to beat that, which keeps the gate conservative.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .candidates import Outfit
from .compat import GATE_FILE, MIN_EVENTS, SKIP_CATEGORIES, CompatScorer, Gate, decide_gate
from .engine import ranked_candidates
from .model import Context, History, Piece
from .select import pick_diverse

POSITIVE = frozenset({"worn", "saved", "liked"})


@dataclass(frozen=True)
class EvalResult:
    n: int  # picks that rules or the model could have ranked (they were candidates)
    skipped: int  # picks whose pieces are gone or that aren't candidates any more
    hits_rules: int
    hits_compat: int

    @property
    def hit_rules(self) -> float:
        return self.hits_rules / self.n if self.n else 0.0

    @property
    def hit_compat(self) -> float:
        return self.hits_compat / self.n if self.n else 0.0


def _main(ids: Any, by_id: dict[str, Piece]) -> frozenset[str] | None:
    ps = [by_id.get(str(i)) for i in ids or []]
    if not ps or any(p is None for p in ps):
        return None
    return frozenset(p.id for p in ps if p is not None and p.category not in SKIP_CATEGORIES)


def _day(ev: dict[str, Any]) -> date:
    d = (ev.get("context") or {}).get("date")
    if d:
        return date.fromisoformat(str(d))
    return datetime.fromisoformat(str(ev["created_at"]).replace("Z", "+00:00")).date()


def _top3(
    pieces: list[Piece],
    c: Context,
    h: History,
    profile: dict[str, Any] | None,
    scorer: CompatScorer | None,
) -> tuple[set[frozenset[str]], set[frozenset[str]]]:
    """(the top-3 picks as main-piece sets, every candidate as main-piece sets)."""
    _, ranked = ranked_candidates(pieces, c, h, profile, scorer)
    return {_ids(o) for o, _ in pick_diverse(ranked, 3)}, {_ids(o) for o, _ in ranked}


def _ids(o: Outfit) -> frozenset[str]:
    return frozenset(p.id for p in o if p.category not in SKIP_CATEGORIES)


def evaluate(
    pieces: list[Piece],
    events: list[dict[str, Any]],
    wear_logs: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    scorer: CompatScorer,
) -> EvalResult:
    by_id = {p.id: p for p in pieces}
    seen: set[tuple[frozenset[str], date]] = set()
    n = skipped = hr = hc = 0
    for ev in events:
        if ev.get("action") not in POSITIVE:
            continue
        target = _main(ev.get("item_ids"), by_id)
        day = _day(ev)
        if not target or (target, day) in seen:
            skipped += target is None
            continue
        seen.add((target, day))
        cx = ev.get("context") or {}
        c = Context.from_payload(
            {
                "occasion": ev.get("occasion"),
                "date": day.isoformat(),
                "weather": cx.get("weather"),
                "note": cx.get("note") or "",
            }
        )
        h = History.from_logs([w for w in wear_logs if str(w["worn_on"]) < day.isoformat()])
        top_r, all_r = _top3(pieces, c, h, profile, None)
        if target not in all_r:
            skipped += 1
            continue
        top_c, _ = _top3(pieces, c, h, profile, scorer)
        n += 1
        hr += target in top_r
        hc += target in top_c
    return EvalResult(n, skipped, hr, hc)


def write_gate(folder: Path, r: EvalResult) -> Gate:
    g = decide_gate(
        r.n, round(r.hit_rules, 4), round(r.hit_compat, 4), datetime.now(UTC).isoformat()
    )
    folder.mkdir(parents=True, exist_ok=True)
    (folder / GATE_FILE).write_text(json.dumps(g.to_json(), indent=2) + "\n")
    return g


def summary(r: EvalResult, g: Gate) -> str:
    lines = [
        f"Logged picks checked: {r.n} (skipped {r.skipped}: pieces gone or not a candidate now).",
        f"Top-3 hit rate, rules alone:       {r.hit_rules:.0%} ({r.hits_rules}/{r.n})",
        f"Top-3 hit rate, rules + the model: {r.hit_compat:.0%} ({r.hits_compat}/{r.n})",
    ]
    if g.open:
        lines.append("The outfit model is on: it ranked your picks higher than rules alone.")
    elif r.n < MIN_EVENTS:
        lines.append(
            f"The outfit model stays off: it needs {MIN_EVENTS} logged picks, "
            f"{MIN_EVENTS - r.n} more to go."
        )
    else:
        lines.append("The outfit model stays off: it didn’t beat rules alone on your picks.")
    return "\n".join(lines)
