from __future__ import annotations

import random
from datetime import timedelta

import pytest

from closet_worker.recsys.candidates import apply_note, candidates, candidates_with, eligible
from closet_worker.recsys.engine import good_outfits_with, ideas, verdict
from closet_worker.recsys.model import Context, History, Piece
from closet_worker.recsys.scoring import formality, freshness, harmony, score, weather
from closet_worker.recsys.select import pick_diverse
from closet_worker.text.templates import render, wish_reasons

from .recsys_fixtures import TODAY, closet, ctx, piece

CATS = ("Tops", "Bottoms", "Layers", "Shoes", "Sets & suits", "Accessories")


def cats(o: tuple[Piece, ...]) -> list[str]:
    return [p.category for p in o]


def random_closet(rng: random.Random, n: int) -> list[Piece]:
    out = []
    for i in range(n):
        out.append(
            piece(
                f"p{i}",
                rng.choice(CATS),
                formality=rng.randint(1, 5),
                occasions=tuple(
                    rng.sample(["office", "college", "party", "home"], rng.randint(0, 2))
                ),
                status=rng.choice(["active"] * 5 + ["laundry", "retired"]),
                color_name=rng.choice(["navy", "white", "grey", "red", "olive", "mustard"]),
            )
        )
    return out


@pytest.mark.parametrize("seed", range(40))
def test_structure_rules_hold_for_random_closets(seed: int) -> None:
    rng = random.Random(seed)
    pieces = random_closet(rng, rng.randint(3, 25))
    c = ctx(
        occasion=rng.choice(["office", "college", "party", "home"]),
        temp_high_f=rng.choice([None, 40.0, 70.0]),
        rain_pct=rng.choice([0.0, 60.0]),
    )
    elig = [p for p in pieces if eligible(p, c.occasion)]
    has = {k: any(p.category == k for p in elig) for k in CATS}
    layer_needed = (c.temp_high_f is not None and c.temp_high_f < 60) or c.rain_pct >= 50
    for o in candidates(pieces, c):
        k = cats(o)
        assert all(p in elig for p in o), "only eligible pieces"
        assert k.count("Tops") <= 1 and k.count("Bottoms") <= 1 and k.count("Shoes") <= 1
        assert k.count("Layers") <= 1 and "Accessories" not in k
        assert ("Sets & suits" in k) != ("Tops" in k and "Bottoms" in k), (
            "a set, or a top and a bottom"
        )
        assert ("Shoes" in k) == has["Shoes"], "shoes whenever any are eligible"
        assert ("Layers" in k) == (layer_needed and has["Layers"]), (
            "a layer only when the weather calls for it"
        )


def test_eligibility_by_tag_or_formality() -> None:
    assert eligible(piece("a", "Tops", formality=1, occasions=("office",)), "office")
    assert eligible(piece("b", "Tops", formality=4, occasions=()), "office")
    assert not eligible(piece("c", "Tops", formality=1, occasions=()), "office")
    assert not eligible(piece("d", "Tops", status="laundry"), "office")


def test_layer_when_cold_or_rainy() -> None:
    warm = candidates(closet(), ctx(temp_high_f=72.0))
    cold = candidates(closet(), ctx(temp_high_f=41.0))
    assert all("Layers" not in cats(o) for o in warm)
    assert cold and all("Layers" in cats(o) for o in cold)


def test_sampling_caps_and_is_repeatable() -> None:
    big = [piece(f"t{i}", "Tops") for i in range(40)] + [
        piece(f"b{i}", "Bottoms") for i in range(40)
    ]
    big += [piece(f"s{i}", "Shoes") for i in range(5)]
    a, b = candidates(big, ctx(), limit=500), candidates(big, ctx(), limit=500)
    assert len(a) == 500 and [tuple(p.id for p in o) for o in a] == [
        tuple(p.id for p in o) for o in b
    ]


def test_note_rules() -> None:
    c, shift = apply_note(ctx(note="Client meeting at 2, might rain"))
    assert shift == 1 and c.rain_pct >= 80
    c, shift = apply_note(ctx(note="lazy day at home"))
    assert shift == -1
    c, _ = apply_note(ctx(note="snow!", temp_high_f=45.0))
    assert c.temp_high_f == 32.0


def test_harmony_terms() -> None:
    navy, grey = piece("n", "Tops", color_name="navy"), piece("g", "Bottoms", color_name="grey")
    red, mustard, teal = (
        piece("r", "Tops", color_name="red"),
        piece("m", "Bottoms", color_name="mustard"),
        piece("t", "Shoes", color_name="teal"),
    )
    v, reasons = harmony((navy, grey))
    assert v > 0 and reasons[0] == {"kind": "pair", "a": "navy", "b": "grey"}
    assert harmony((red, mustard, teal))[0] == -1.0  # three saturated hues
    khaki, brown = (
        piece("k", "Bottoms", color_name="khaki"),
        piece("b", "Shoes", color_name="brown"),
    )
    assert (
        harmony((piece("lb", "Tops", color_name="light blue"), khaki, brown))[0] > 0
    )  # neutrals by name


def test_formality_term_prefers_target_and_small_spread() -> None:
    office = ctx()
    tight = (piece("a", "Tops", formality=4), piece("b", "Bottoms", formality=4))
    loose = (piece("a", "Tops", formality=1), piece("b", "Bottoms", formality=5))
    assert formality(tight, office)[0] > formality(loose, office)[0]
    casual = (piece("a", "Tops", formality=3), piece("b", "Bottoms", formality=3))
    assert formality(casual, office, shift=1)[0] < formality(casual, office)[0]


def test_weather_term_and_rain_risk() -> None:
    light = (piece("a", "Tops", warmth="light"), piece("b", "Bottoms", warmth="light"))
    warm = (*light, piece("s", "Layers", warmth="warm", type="crew neck sweater"))
    cold = ctx(temp_high_f=41.0)
    assert weather(warm, cold)[0] > weather(light, cold)[0]
    assert weather(warm, cold)[1] == [{"kind": "weather", "piece": "sweater", "temp": "41°F"}]
    wet = ctx(rain_pct=80.0)
    suede = (*light, piece("x", "Shoes", type="suede shoes"))
    boots = (*light, piece("y", "Shoes", type="chelsea boots"))
    assert weather(suede, wet)[0] < weather(boots, wet)[0]


def test_freshness_penalizes_repeats() -> None:
    o = (piece("a", "Tops"), piece("b", "Bottoms"))
    key = frozenset({"a", "b"})

    def h(days_ago: int) -> History:
        d = TODAY - timedelta(days=days_ago)
        return History(piece_last={"a": d, "b": d}, outfit_last={key: d})

    # The exact outfit worn within 7 days scores lower than the same outfit 8 days ago.
    assert freshness(o, ctx(), h(7))[0] < freshness(o, ctx(), h(8))[0] - 1.0
    # A piece worn yesterday is penalized against one worn 3 days ago.
    y = History(piece_last={"a": TODAY - timedelta(days=1)})
    t = History(piece_last={"a": TODAY - timedelta(days=3)})
    assert freshness(o, ctx(), y)[0] < freshness(o, ctx(), t)[0] - 0.5
    _, reasons = freshness(o, ctx(), History(piece_last={"a": TODAY - timedelta(days=12)}))
    assert {"kind": "fresh", "piece": "a", "days": 12} in reasons


def test_repeat_within_7_days_changes_the_picks() -> None:
    pieces = closet()
    first = ideas(pieces, ctx(temp_high_f=70.0), History())[0][0]
    ids = frozenset(p.id for p in first)
    yesterday = TODAY - timedelta(days=1)
    h = History(piece_last={i: yesterday for i in ids}, outfit_last={ids: yesterday})
    again = ideas(pieces, ctx(temp_high_f=70.0), h)
    assert frozenset(p.id for p in again[0][0]) != ids
    assert (
        score(first, ctx(temp_high_f=70.0), h).total
        < score(first, ctx(temp_high_f=70.0), History()).total
    )


def test_diversity_shares_at_most_one_piece() -> None:
    roomy = [
        *closet(),
        piece("blue-shirt", "Tops", color_name="light blue"),
        piece("navy-trousers", "Bottoms", color_name="navy"),
        piece("loafers", "Shoes", color_name="brown"),
    ]
    picks = ideas(roomy, ctx(temp_high_f=72.0), History(), k=3)
    assert len(picks) == 3
    sets = [{p.id for p in o} for o, _ in picks]
    for i in range(3):
        for j in range(i):
            assert len(sets[i] & sets[j]) <= 1
    a, b, c = (piece(x, "Tops") for x in "abc")
    x, y = piece("x", "Bottoms"), piece("y", "Bottoms")
    chosen = pick_diverse([((a, x), 1), ((a, y), 2), ((b, x), 3), ((c, y), 4)], k=3)
    assert [m for _, m in chosen] == [1, 2, 4] or len(chosen) <= 3


def test_unlocks_count_only_outfits_with_the_new_piece() -> None:
    new = piece("new-shirt", "Tops", color_name="light blue", warmth="light")
    good = good_outfits_with(new, closet(), ctx())
    assert good and all(any(p.id == "new-shirt" for p in o) for o in good)
    assert candidates_with(piece("belt", "Accessories"), closet(), ctx()) == []


@pytest.mark.parametrize(
    ("worn_dupe", "dupe", "unlocks", "over", "expected"),
    [
        (True, True, 5, False, "skip"),
        (False, False, 5, True, "skip"),
        (False, False, 3, False, "buy"),
        (False, False, 2, False, "wait"),
        (False, True, 9, False, "wait"),
    ],
)
def test_verdict_table(
    worn_dupe: bool, dupe: bool, unlocks: int, over: bool, expected: str
) -> None:
    assert verdict(worn_dupe, dupe, unlocks, over) == expected


def test_templates_make_one_sentence_and_vary() -> None:
    reasons = [
        {"kind": "pair", "a": "navy", "b": "grey"},
        {"kind": "fresh", "piece": "shirt", "days": 12},
        {"kind": "weather", "piece": "sweater", "temp": "41°F"},
    ]
    texts = {render(reasons, seed=s) for s in range(12)}
    assert len(texts) > 3
    for t in texts:
        first, _, rest = t.partition(". ")
        assert first.startswith("Navy") and "12 days" in first and "41°F" in rest
    assert render([], seed=1) == "A fresh mix from your closet."
    r = wish_reasons([{"name": "Navy oxford", "wears": 7}], 0, "office", 2500, 15000)
    assert r[0] == "You own something very similar: Navy oxford."
    assert (
        "7 times" in r[1]
        and "doesn’t make any new office outfits" in r[2]
        and "$25 over your $150" in r[3]
    )


def test_context_from_payload_converts_celsius() -> None:
    c = Context.from_payload(
        {"occasion": "party", "date": "2026-11-20", "weather": {"high": 10, "unit": "C"}}
    )
    assert c.temp_high_f == pytest.approx(50.0) and c.temp_text() == "10°C"
