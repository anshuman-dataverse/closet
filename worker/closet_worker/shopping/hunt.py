"""Free deal hunt (SPEC 5.8): search → product pages on listed stores → parse → keep → rank.

Honesty rules: a listing is kept only when its page states a USD price within budget and says
it's in stock. Nothing is estimated. The summary names stores that blocked reading, so few
results are explained, not hidden. Stores that blocked recently are skipped for a week
(~/.closet/store_health.json) so hunts don't spend requests on them.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from .fetch import Fetcher
from .parse import Listing, parse_listing
from .stores import Store, StoreList, canonical, load_stores

MAX_QUERIES = 10
MAX_PAGES = 25
TOP_N = 5
SKIP_BLOCKED_FOR = timedelta(days=7)
HEALTH_PATH = Path("~/.closet/store_health.json").expanduser()
# What suits you counts most: your colors, your fit, your size; then the photo match, deals and
# reviews. Each part is 0 when there's nothing to go on, so nothing unknown is rewarded.
W = {
    "match": 0.30,
    "palette": 0.25,
    "fit": 0.12,
    "size": 0.10,
    "discount": 0.10,
    "rating": 0.08,
    "favorite": 0.05,
}
# Your fit preference (Settings) → fit words a product may state.
FIT_PREF_WORDS = {
    "slim": ("slim", "skinny", "tailored", "fitted"),
    "regular": ("regular", "classic", "straight", "standard"),
    "relaxed": ("relaxed", "loose", "easy fit", "oversized", "boxy"),
}
SEARCH_DOWN = (
    "Search didn’t answer (SearXNG on your Mac), so nothing was checked. "
    "Try again in a few minutes."
)
PER_STORE = 2  # at most this many picks from one store, for variety
REASON_WORDS = {
    "robots": "don’t allow automated reading",
    "blocked": "blocked automated reading",
    "no_data": "don’t publish product data on the page",
}


@dataclass
class Hunt:
    query: str
    budget_min_cents: int | None
    budget_max_cents: int | None
    occasion: str | None = None
    wears: str | None = None  # menswear | womenswear | both
    favorites: list[str] = field(default_factory=list)
    best_colors: list[str] = field(default_factory=list)
    # Look slots only: the product name must contain one of these words, state no other color,
    # and (for plain pieces) no pattern.
    must_have: tuple[str, ...] = ()
    color: str | None = None
    # About you (from your profile): sold-out sizes and "use carefully" colors are dropped.
    size: str | None = None
    fit_pref: str | None = None
    careful_colors: tuple[str, ...] = ()
    near_face: bool = True  # the hunted piece is worn near the face (tops, layers)


def audience(wears: str | None) -> str:
    return {"menswear": "men", "womenswear": "women"}.get(wears or "", "")


def queries(h: Hunt, stores: list[Store]) -> list[str]:
    """Up to 10: the plain search, a few with your best colors, then site: searches."""
    who = audience(h.wears)
    base = " ".join(x for x in (h.query.strip(), who) if x)
    out = [base]
    if color_in(h.query) is None:  # "white oxford shirt" already says its color
        out += [f"{c} {base}" for c in h.best_colors[:2]]
    out += [f"site:{s.domains[0]} {h.query.strip()}" for s in stores]
    seen: list[str] = []
    for q in out:
        if q not in seen:
            seen.append(q)
    return seen[:MAX_QUERIES]


@cache
def _color_names() -> tuple[str, ...]:
    from closet_worker.vocab import load_vocab

    return tuple(sorted(load_vocab().colors, key=len, reverse=True))


def color_in(text: str) -> str | None:
    """The first color word in a product name or search ("light blue", "navy"), if any."""
    t = f" {text.lower()} "
    for c in _color_names():
        if f" {c} " in t:
            return c
    return None


def load_health(path: Path = HEALTH_PATH) -> dict[str, dict[str, str]]:
    try:
        data: dict[str, dict[str, str]] = json.loads(path.read_text())
        return data
    except (OSError, ValueError):
        return {}


def save_health(health: dict[str, dict[str, str]], path: Path = HEALTH_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health, indent=1, sort_keys=True))


def recently_blocked(health: dict[str, dict[str, str]], store: str, now: datetime) -> str | None:
    h = health.get(store)
    if not h or h.get("status") == "ok":
        return None
    try:
        at = datetime.fromisoformat(h["at"])
    except (KeyError, ValueError):
        return None
    return h["status"] if now - at < SKIP_BLOCKED_FOR else None


KIDS = re.compile(
    r"\b(baby|babies|kids?|toddlers?|infants?|boys?|girls?|teens?|youth|junior)\b", re.I
)
PATTERN = re.compile(
    r"\b(plaid|check(ed)?|gingham|stripe[ds]?|print(ed)?|floral|graphic|logo|camo|tie-?dye)\b", re.I
)


WOMENS = re.compile(r"\b(women'?s?|womens|ladies|maternity)\b", re.I)
MENS = re.compile(r"(?<!wo)\b(men'?s?|mens)\b", re.I)


def for_wears(item: Listing, wears: str | None) -> bool:
    """Menswear hunts skip women's products and the other way round, by the page's own
    audience data or the product name. "Both" (or not set) keeps everything."""
    if wears == "menswear":
        return item.gender != "female" and not WOMENS.search(item.title)
    if wears == "womenswear":
        return item.gender != "male" and not MENS.search(item.title)
    return True


def stated_color(item: Listing) -> str | None:
    """The color the product's name or its own data states, if any."""
    return color_in(item.title) or (color_in(item.color) if item.color else None)


def matches_slot(item: Listing, h: Hunt) -> bool:
    """Look pieces: the right item, in the planned color as stated by the store (an unstated
    color isn't assumed), and plain when a plain piece was planned."""
    title = item.title.lower()
    if h.must_have and not any(w in title for w in h.must_have):
        return False
    if h.color:
        if stated_color(item) != h.color:
            return False
        if PATTERN.search(title) or (item.color and PATTERN.search(item.color)):
            return False
    return True


def keep(item: Listing, h: Hunt) -> bool:
    if item.price_cents is None or item.currency != "USD" or item.in_stock is not True:
        return False
    if KIDS.search(item.title) or any(KIDS.search(c) for c in item.crumbs):
        return False  # kids' things show up under adult searches
    if not for_wears(item, h.wears) or not matches_slot(item, h):
        return False
    if h.near_face and h.careful_colors and stated_color(item) in h.careful_colors:
        return False  # one of your "use carefully" colors, worn by your face
    if size_available(item, h.size) == "no":
        return False  # your size is sold out
    if h.budget_min_cents is not None and item.price_cents < h.budget_min_cents:
        return False
    return h.budget_max_cents is None or item.price_cents <= h.budget_max_cents


def fit_match(item: Listing, fit_pref: str | None) -> float:
    """1 when the product states your preferred fit, else 0 (unstated fits aren't guessed)."""
    if not fit_pref:
        return 0.0
    text = f"{item.title} {' '.join(item.crumbs)}".lower()
    return 1.0 if any(w in text for w in FIT_PREF_WORDS.get(fit_pref, (fit_pref,))) else 0.0


def discount(item: Listing) -> float:
    if not item.was_price_cents or not item.price_cents or item.was_price_cents <= item.price_cents:
        return 0.0
    return 1 - item.price_cents / item.was_price_cents


def rating_score(item: Listing) -> float:
    if item.rating is None:
        return 0.0
    confidence = min(1.0, math.log10(1 + (item.rating_count or 0)) / 2)  # 100+ reviews → full
    return (item.rating / 5) * confidence


@dataclass
class Pick:
    listing: Listing
    store: str
    score: float
    parts: dict[str, float]
    color: str | None = None
    palette_note: str | None = None


def why_text(p: Pick, h: Hunt) -> str:
    """Why it suits you first (only what's true for this item), then the deal."""
    bits = []
    if p.palette_note:
        bits.append(p.palette_note)
    if p.parts.get("fit") and h.fit_pref:
        bits.append(f"It’s cut {h.fit_pref}, your preferred fit.")
    if p.parts.get("size"):
        bits.append("Your size is in stock.")
    if p.parts["match"] >= 0.6:
        bits.append(f"A close match for “{h.query.strip()}”.")
    d = discount(p.listing)
    if d >= 0.1:
        bits.append(f"{round(d * 100)}% off right now.")
    if p.parts["favorite"]:
        bits.append(f"From {p.store}, one of your stores.")
    return " ".join(bits) or f"In budget at {p.store}."


def quality_text(item: Listing) -> str:
    if item.rating is None:
        return "No ratings on the page."
    n = item.rating_count
    count = f" from {n:,} review{'s' if n != 1 else ''}" if n else ""
    return f"{item.rating:.1f}★{count}."


def size_available(item: Listing, size: str | None) -> str:
    if not size or not item.sizes:
        return "unknown"
    want = size.strip().lower()
    for label, ok in item.sizes.items():
        if label.strip().lower() == want:
            return "yes" if ok else "no"
    return "unknown"


@dataclass
class Outcome:
    picks: list[Pick]
    pages_checked: int
    skipped: dict[str, str]  # store → reason
    found_listings: int
    summary: str


def summarize(picks: list[Pick], pages: int, skipped: dict[str, str], found: int, h: Hunt) -> str:
    stores = list(dict.fromkeys(p.store for p in picks))
    out = []
    if picks:
        names = ", ".join(stores[:-1]) + (f" and {stores[-1]}" if len(stores) > 1 else stores[0])
        out.append(f"{len(picks)} pick{'s' if len(picks) != 1 else ''} from {names}.")
    else:
        out.append("No picks in budget.")
    out.append(f"Checked {pages} product page{'s' if pages != 1 else ''}.")
    by_reason: dict[str, list[str]] = {}
    for store, reason in sorted(skipped.items()):
        by_reason.setdefault(reason, []).append(store)
    for reason, stores_ in by_reason.items():
        if reason in REASON_WORDS:
            out.append(f"{', '.join(stores_)} {REASON_WORDS[reason]}.")
    if len(picks) < 2:
        if found > len(picks):
            out.append("Some listings were out of budget or out of stock: try a wider budget.")
        else:
            out.append("Try a simpler search, like the item’s basic name.")
    return " ".join(out)


Searcher = Callable[[str], list[str]]
ImageScore = Callable[[list[Listing], str], list[float]]
Palette = Callable[[Listing], tuple[float, str | None, str | None]]


def run_hunt(
    h: Hunt,
    search: Searcher,
    fetcher: Fetcher,
    image_match: ImageScore,
    palette: Palette,
    stores: StoreList | None = None,
    health_path: Path = HEALTH_PATH,
    now: datetime | None = None,
    pause: Callable[[float], None] = time.sleep,
    max_queries: int = MAX_QUERIES,
    max_pages: int = MAX_PAGES,
    top_n: int = TOP_N,
) -> Outcome:
    sl = stores or load_stores()
    now = now or datetime.now(UTC)
    health = load_health(health_path)
    favorites = {s.name for s in sl.match_names(h.favorites)}
    usable = [s for s in sl.stores if not recently_blocked(health, s.name, now)]

    def status(s: Store) -> str:
        return health.get(s.name, {}).get("status") or s.checked

    rank = {"ok": 0, "unknown": 1, "no_data": 2, "blocked": 3, "robots": 3}
    order = sorted(usable, key=lambda s: (s.name not in favorites, rank.get(status(s), 1)))
    skipped = {
        s.name: recently_blocked(health, s.name, now) or "" for s in sl.stores if s not in usable
    }

    urls: list[tuple[str, Store]] = []
    # Color variants take 2 searches only when the search doesn't already name a color.
    reserve = 1 + (0 if color_in(h.query) else 2)
    plan = queries(h, order[: max(1, max_queries - reserve)])[:max_queries]
    failed = 0
    for i, q in enumerate(plan):
        if i:
            pause(1.5)  # search engines throttle rapid queries
        try:
            found = search(q)
        except Exception:
            failed += 1
            continue
        for u in found:
            st = sl.product_store(u)
            if st is not None and st in usable:
                c = canonical(u)
                if c not in [x for x, _ in urls]:
                    urls.append((c, st))
    per_store: Counter[str] = Counter()
    picked_urls: list[tuple[str, Store]] = []
    for u, st in urls:  # spread pages across stores: at most 4 per store
        if per_store[st.name] < 4:
            per_store[st.name] += 1
            picked_urls.append((u, st))
    listings: list[tuple[Listing, Store]] = []
    pages = 0
    for u, st in picked_urls[:max_pages]:
        if st.name in skipped:
            continue
        page = fetcher.get(u)
        if not page.ok:
            if page.reason in ("robots", "blocked"):
                skipped[st.name] = page.reason
                health[st.name] = {"status": page.reason, "at": now.isoformat()}
            continue
        pages += 1
        item = parse_listing(page.text, page.url)
        if item is None:
            if health.get(st.name, {}).get("status") != "ok":
                health[st.name] = {"status": "no_data", "at": now.isoformat()}
            continue
        health[st.name] = {"status": "ok", "at": now.isoformat()}
        listings.append((item, st))
    save_health(health, health_path)
    skipped = {k: v for k, v in skipped.items() if v and k not in {st.name for _, st in listings}}

    kept = [(item, st) for item, st in listings if keep(item, h)]
    matches = image_match([item for item, _ in kept], h.query) if kept else []
    if matches:
        lo, hi = min(matches), max(matches)
        norm = [(m - lo) / (hi - lo) if hi > lo else 1.0 for m in matches]
    else:
        norm = []
    picks = []
    for (item, st), m in zip(kept, norm, strict=True):
        pal, color, note = palette(item)
        parts = {
            "match": m,
            "palette": pal,
            "fit": fit_match(item, h.fit_pref),
            "size": 1.0 if size_available(item, h.size) == "yes" else 0.0,
            "discount": discount(item),
            "rating": rating_score(item),
            "favorite": 1.0 if st.name in favorites else 0.0,
        }
        picks.append(
            Pick(item, st.name, sum(W[k] * v for k, v in parts.items()), parts, color, note)
        )
    picks.sort(key=lambda p: -p.score)
    top: list[Pick] = []
    seen_titles: set[tuple[str, str]] = set()
    from_store: Counter[str] = Counter()
    for p in picks:  # the same product in another color counts once; ≤2 per store
        key = (p.store, p.listing.title.lower())
        if key not in seen_titles and from_store[p.store] < PER_STORE:
            seen_titles.add(key)
            from_store[p.store] += 1
            top.append(p)
        if len(top) == top_n:
            break
    if plan and failed == len(plan):
        return Outcome([], 0, skipped, 0, SEARCH_DOWN)
    return Outcome(
        top, pages, skipped, len(listings), summarize(top, pages, skipped, len(listings), h)
    )


LIGHT_NEUTRALS = frozenset(
    {"white", "off-white", "ivory", "cream", "light grey", "grey", "silver", "beige", "stone"}
)


def phrase(color: str, palette_color: str, group: str) -> str:
    """ "White is one of your neutrals." or "Its sky blue is close to light blue, one of …"."""
    if color == palette_color:
        return f"{color[0].upper()}{color[1:]} is one of your {group}."
    return f"Its {color} is close to {palette_color}, one of your {group}."


class Images:
    """Product images, fetched once (robots.txt honored) and shared by matching and color."""

    def __init__(self, fetcher: Fetcher) -> None:
        self.fetcher = fetcher
        self.cache: dict[str, Any] = {}

    def get(self, url: str | None) -> Any:
        import io

        from PIL import Image

        if not url:
            return None
        if url not in self.cache:
            page = self.fetcher.get(url)
            img = None
            if page.ok and page.content:
                try:
                    img = Image.open(io.BytesIO(page.content)).convert("RGB")
                except Exception:
                    img = None
            self.cache[url] = img
        return self.cache[url]


def clip_image_match(emb: Any, images: Images) -> ImageScore:
    """Query-to-image similarity with fashion CLIP. A listing whose image can't be read scores 0."""

    def score(items: list[Listing], query: str) -> list[float]:
        q = emb.text([f"a photo of a {query}"])[0]
        out = []
        for it in items:
            img = images.get(it.image_url)
            out.append(float(np.dot(emb.image([img])[0], q)) if img is not None else 0.0)
        return out

    return score


def palette_fit(analysis: dict[str, Any] | None, images: Images) -> Palette:
    """How close the product's main color is to your best colors and neutrals (0 to 1).
    Without a style profile, or without a readable image, it's 0 and nothing is claimed."""
    from closet_worker.vision.color import Palette as Named
    from closet_worker.vision.color import delta_e, dominant_colors, hex_to_rgb, srgb_to_lab
    from closet_worker.vocab import load_vocab

    colors = load_vocab().colors
    named = Named.from_dict(colors)
    best = [(c["name"], c["hex"]) for c in (analysis or {}).get("best", [])]
    neutrals = [(c["name"], c["hex"]) for c in (analysis or {}).get("neutrals", [])]

    def color_of(item: Listing) -> tuple[str, str, bool] | None:
        """(name, hex, stated). The product's own name wins (stated=True). The photo is used only
        for clearly colored garments: light ones (white, grey, cream…) on a white studio
        backdrop can't be told apart, so they're not read from photos at all."""
        said = color_in(item.title)
        if said:
            return said, colors[said], True
        img = images.get(item.image_url)
        if img is None:
            return None
        a = np.asarray(img.resize((160, 160)), dtype=np.uint8)
        h, w = a.shape[:2]
        center = a[h // 6 : h - h // 6, w // 6 : w - w // 6]
        mask = center.astype(int).sum(axis=2) < 3 * 235  # skip the white studio background
        if mask.mean() < 0.25:
            return None
        top = dominant_colors(center, mask, named)[0]
        if top.share < 0.5 or top.name in LIGHT_NEUTRALS:
            return None
        return top.name, top.hex, False

    def fit(item: Listing) -> tuple[float, str | None, str | None]:
        got = color_of(item)
        if got is None:
            return 0.0, None, None
        cname, chex, stated = got
        if not best:
            return 0.0, cname, None
        lab = srgb_to_lab(np.array([hex_to_rgb(chex)]))
        good = best + neutrals
        d = delta_e(
            np.repeat(lab, len(good), axis=0),
            srgb_to_lab(np.array([hex_to_rgb(x) for _, x in good])),
        )
        k = int(np.argmin(d))
        score = 1 - min(float(d[k]), 40.0) / 40.0
        note: str | None = None
        if stated and float(d[k]) <= 10:  # only claim colors the product's name states
            note = phrase(cname, good[k][0].lower(), "best colors" if k < len(best) else "neutrals")
        return score, cname, note

    return fit
