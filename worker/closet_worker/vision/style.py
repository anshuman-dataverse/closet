"""Style profile: palette lookup and neutral, templated text from measurements (SPEC 5.2 steps 5–8)."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

from .body import fit_notes
from .skin import contrast as contrast_of
from .skin import depth as depth_of
from .skin import thresholds
from .skin import undertone as undertone_of

VOCAB = Path(__file__).parent.parent / "vocab"
VERSION = 1


@cache
def palettes() -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = yaml.safe_load((VOCAB / "palettes.yaml").read_text())
    return data


@cache
def face_tips() -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = yaml.safe_load((VOCAB / "face_tips.yaml").read_text())
    return data


@cache
def color_hex() -> dict[str, str]:
    data: dict[str, str] = yaml.safe_load((VOCAB / "colors.yaml").read_text())
    return {k: str(v).lower() for k, v in data.items()}


def _sw(name: str) -> dict[str, str]:
    return {"name": name[:1].upper() + name[1:], "hex": color_hex()[name]}


def _lightness(hx: str) -> float:
    r, g, b_ = (int(hx[i : i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b_


def _list(names: list[str]) -> str:
    n = [x for x in names]
    return n[0] if len(n) == 1 else ", ".join(n[:-1]) + " and " + n[-1]


def borderline_notes(m: dict[str, Any], t: dict[str, Any], o: dict[str, str | None]) -> list[str]:
    """Honest notes when a read sits near a cutoff, so you know where the Change control matters."""
    edge = float(t.get("borderline", 3))
    u, out = t["undertone"], []
    hue = float(m.get("hue", 0))
    if not o.get("undertone"):
        if abs(hue - u["cool_max_hue"]) <= edge:
            out.append(
                "Your undertone read sits between cool and neutral. If neutral feels truer, change it below."
            )
        elif abs(hue - u["warm_min_hue"]) <= edge:
            out.append(
                "Your undertone read sits between neutral and warm. If warm feels truer, change it below."
            )
    spread = float(m.get("hue_spread") or 0)
    if not o.get("undertone") and spread > float(t.get("photos_disagree_hue", 12)):
        out.append(
            f"Your face photos disagree by {spread:.0f}° on undertone, so the light changed between "
            "them. Retake them in the same daylight, facing the window."
        )
    d = t["depth"]
    ita = float(m.get("ita", 0))
    if (
        not o.get("depth")
        and min(abs(ita - d["light_min_ita"]), abs(ita - d["deep_max_ita"])) <= edge
    ):
        out.append(
            "Your depth read is close to the next band, so the palette may shift slightly between photos."
        )
    votes = sorted({v for v in m.get("face_shape_votes", []) if v})
    if len(votes) > 1:
        out.append(f"Your face shape reads between {' and '.join(votes)}; tips for both can work.")
    if m.get("hair_L") is not None and not o.get("contrast"):
        delta = abs(float(m["skin_lab"][0]) - float(m["hair_L"]))
        c = t["contrast"]
        if min(abs(delta - c["low_below"]), abs(delta - c["high_above"])) <= edge:
            out.append(
                "Your contrast read is close to the next band. Change it below if it feels off."
            )
    return out


def build(
    measurements: dict[str, Any], overrides: dict[str, str | None] | None = None
) -> dict[str, Any]:
    """Everything the profile shows, from stored measurements. Overrides win over the computed read."""
    t = thresholds()
    o = overrides or {}
    sl = measurements["skin_lab"]
    lab = (float(sl[0]), float(sl[1]), float(sl[2]))
    computed = {
        "undertone": undertone_of(lab, t),
        "depth": depth_of(lab, t),
        "contrast": contrast_of(lab[0], measurements.get("hair_L"), t) or "medium",
    }
    eff = {
        "undertone": o.get("undertone") or computed["undertone"],
        "depth": o.get("depth") or computed["depth"],
        "contrast": o.get("contrast") or computed["contrast"],
    }
    pal = palettes()[f"{eff['undertone']}/{eff['depth']}/{eff['contrast']}"]
    best = [_sw(n) for n in pal["best"]]
    neutrals = [_sw(n) for n in pal["neutrals"]]
    careful = [{**_sw(c["name"]), "why": c["why"]} for c in pal["careful"]]
    b, nn = [x["name"].lower() for x in best], [x["name"].lower() for x in neutrals]

    shape = measurements.get("face_shape")
    tips = face_tips().get(shape) if shape else None
    face = (
        {"shape": shape, "why": tips["why"], "frames": tips["frames"], "hair": tips["hair"]}
        if tips
        else {
            "shape": None,
            "note": "Face the camera straight on in your close-up for frame and hair tips.",
        }
    )
    notes = borderline_notes(measurements, t, o)
    summary = (
        f"{eff['undertone'].capitalize()} undertone, {eff['depth']} depth and {eff['contrast']} contrast. "
        f"{_list(b[:3]).capitalize()} sit well near your face; {_list(nn[:3])} are easy neutrals."
    )
    dark = sorted(b, key=lambda n: _lightness(color_hex()[n]))  # party: the two deepest best colors
    occasion = {
        "office": f"{nn[0].capitalize()} or {nn[1]} layers over crisp shirts, with {b[0]} as the accent.",
        "college": f"Overshirts and knits in {b[0]} or {b[1]} with dark denim or {nn[0]} trousers.",
        "party": f"Deeper {dark[0]} or {dark[1]} with one statement piece; {nn[0]} keeps the rest calm.",
        "home": f"Soft knits in {nn[0]} and {nn[1] if len(nn) > 1 else nn[0]}.",
    }
    return {
        "version": VERSION,
        "computed": computed,
        "effective": eff,
        "summary": summary,
        "best": best,
        "neutrals": neutrals,
        "careful": careful,
        "fit_notes": fit_notes(measurements.get("body_ratios"), t),
        "occasion_tips": occasion,
        "face": face,
        "confidence_note": measurements.get("lighting_note"),
        "borderline": notes,
        "measurements": measurements,
        "thresholds": t,
        "note": "An estimate from your photos. You can change it.",
    }
