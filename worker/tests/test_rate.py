"""Check my outfit (recsys/rate.py): verdicts and their explanations."""

from __future__ import annotations

from datetime import timedelta

from closet_worker.recsys.model import History
from closet_worker.recsys.rate import rate

from .recsys_fixtures import TODAY, ctx, piece

PROFILE = {
    "best": [{"name": "Light blue", "hex": "#9ec5e6"}, {"name": "Navy", "hex": "#1f2a48"}],
    "neutrals": [{"name": "Charcoal", "hex": "#36454f"}, {"name": "White", "hex": "#ffffff"}],
    "careful": [{"name": "Mustard", "hex": "#d4a017"}],
}
SHIRT = piece(
    "shirt",
    "Tops",
    name="Light blue oxford shirt",
    type="oxford shirt",
    color_name="light blue",
    formality=3,
    fit="regular",
)
CHINOS = piece(
    "chinos",
    "Bottoms",
    name="Navy chinos",
    type="chinos",
    color_name="navy",
    formality=3,
    fit="slim",
)
LOAFERS = piece(
    "loafers", "Shoes", name="Brown loafers", type="loafers", color_name="brown", formality=4
)


def by(r):  # type: ignore[no-untyped-def]
    return {c.key: c for c in r.checks}


def test_a_strong_office_outfit_explains_every_check() -> None:
    r = rate([SHIRT, CHINOS, LOAFERS], ctx(), History(), PROFILE)
    assert r.verdict == "strong" and r.headline.startswith("Strong: it passes every check.")
    c = by(r)
    assert c["structure"].ok and c["formality"].ok and c["fit"].ok
    assert "light blue, one of your best colors" in c["palette"].detail
    assert c["harmony"].ok and c["weather"].ok is None  # no forecast: not checked, and it says so


def test_rethink_when_a_core_check_misses() -> None:
    mustard = piece(
        "m", "Tops", name="Mustard polo", type="polo shirt", color_name="mustard", formality=2
    )
    r = rate([mustard, CHINOS, LOAFERS], ctx(), History(), PROFILE)
    assert r.verdict == "rethink" and "use carefully" in by(r)["palette"].detail
    hoodie = piece(
        "h",
        "Layers",
        name="Grey hoodie",
        type="hoodie",
        color_name="grey",
        formality=1,
        fit="oversized",
    )
    joggers = piece(
        "j",
        "Bottoms",
        name="Grey joggers",
        type="joggers",
        color_name="grey",
        formality=1,
        fit="relaxed",
    )
    r2 = rate([hoodie, joggers, LOAFERS], ctx(), History(), PROFILE)
    assert by(r2)["fit"].ok is False and "loose over loose" in by(r2)["fit"].detail
    assert by(r2)["formality"].ok is False
    assert rate([SHIRT, CHINOS], ctx(), History(), PROFILE).checks[0].detail == "Add shoes."


def test_works_when_only_a_minor_check_misses() -> None:
    h = History(piece_last={"shirt": TODAY - timedelta(days=1)})
    r = rate([SHIRT, CHINOS, LOAFERS], ctx(), h, PROFILE)
    assert r.verdict == "works" and "wore the light blue oxford shirt yesterday" in r.headline


def test_weather_is_checked_when_there_is_a_forecast() -> None:
    suede = piece(
        "s", "Shoes", name="Tan suede shoes", type="suede shoes", color_name="tan", formality=3
    )
    r = rate([SHIRT, CHINOS, suede], ctx(rain_pct=80.0), History(), PROFILE)
    assert by(r)["weather"].ok is False and "rain" in by(r)["weather"].detail


def test_without_a_profile_the_palette_check_says_how_to_enable_it() -> None:
    c = by(rate([SHIRT, CHINOS, LOAFERS], ctx(), History(), None))["palette"]
    assert c.ok is None and c.detail.startswith("Analyze your style photos")
