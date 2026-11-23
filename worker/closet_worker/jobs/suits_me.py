"""`suits_me` (Would it suit me?): read a product link or a screenshot, then check the piece.

What's read, and from where, is recorded with the result: the store's own data first (name,
price, stated color), the picture for anything the page doesn't state. Links are fetched politely
(robots.txt honored); a store that blocks apps gets an honest "use a screenshot" message.
"""

from __future__ import annotations

import io
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from PIL import Image

from closet_worker.recsys.engine import good_outfits_with
from closet_worker.recsys.model import Context, History, Piece
from closet_worker.recsys.scoring import weights
from closet_worker.recsys.suits import ORDER, Candidate, judge
from closet_worker.shopping.fetch import Fetcher
from closet_worker.shopping.hunt import color_in
from closet_worker.shopping.parse import Listing, parse_listing
from closet_worker.shopping.stores import load_stores
from closet_worker.vision.tagger import tag
from closet_worker.vocab import TypeEntry, load_vocab

from .check_wish import _fetch_image
from .context import JobContext
from .tag_item import BadJob, Vision, vision_for

PLACEHOLDER = "Piece to check"
WHY = {
    "robots": "doesn’t allow apps to read its pages",
    "blocked": "blocked the request",
    "not_found": "says that page doesn’t exist",
    "timeout": "didn’t answer in time",
    "too_big": "sent a page too large to read",
    "error": "couldn’t be reached",
}


def public_url(url: str) -> bool:
    """http(s) to a public address only: never the Mac itself or the home network."""
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except OSError:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            return False
    return True


def store_name(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    s = load_stores().by_host(host)
    return s.name if s else host.removeprefix("www.")


def _words(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower()):
        out.add(w)
        if w.endswith("s") and len(w) > 3:
            out.add(w[:-1])  # plurals: "chinos" also counts as "chino"
    return out


def type_in(title: str) -> TypeEntry | None:
    """The clothing type the product's name states: every word of the type appears in the name
    ("Oxford Button-Down Shirt" → oxford shirt). The most specific (most words) wins."""
    have = _words(title)
    hits = [e for e in load_vocab().types if _words(e.type) <= have]
    return max(hits, key=lambda e: (len(_words(e.type)), len(e.type))) if hits else None


def read_link(url: str, fetcher: Fetcher) -> tuple[Listing | None, str | None]:
    """(listing, why not) for a product link."""
    if not public_url(url):
        return None, "That link can’t be opened. Paste the product page’s address (https://…)."
    page = fetcher.get(url)
    if not page.ok:
        return None, f"{store_name(url)} {WHY.get(page.reason, 'couldn’t be read')}."
    got = parse_listing(page.text, page.url)
    if got is None:
        return None, f"{store_name(url)}’s page doesn’t list the product’s details."
    return got, None


@dataclass
class Read:
    """What the piece is, and where each fact came from."""

    title: str
    type: str
    category: str
    formality: int
    color: str
    hex: str | None
    color_source: str  # you | store | picture | none
    vec: list[float] | None  # image embedding, when there was a picture
    source: str  # link | screenshot
    link_note: str | None = None
    price_cents: int | None = None
    image_url: str | None = None
    fallback_name: str = ""


def read_piece(
    wish: dict[str, Any],
    payload: dict[str, Any],
    ctx: JobContext,
    v: Vision,
    fetcher: Fetcher | None,
) -> Read:
    assert ctx.items is not None
    url = str(wish.get("url") or "")
    photo = str(wish.get("photo_path") or "")
    if not url and not photo:
        raise BadJob("Add a product link or a screenshot to check.")

    listing: Listing | None = None
    why_not: str | None = None
    if url:
        listing, why_not = read_link(url, fetcher or Fetcher())
        if listing is None and not photo:
            raise BadJob(f"{why_not} Take a screenshot of the product and check that instead.")

    img: Image.Image | None = None
    if photo:
        if not photo.startswith(f"{ctx.items.owner}/wishlist/"):
            raise BadJob("That screenshot isn’t yours.")
        img = Image.open(io.BytesIO(ctx.items.download(photo))).convert("RGB")
    elif listing and listing.image_url and public_url(listing.image_url):
        img = _fetch_image(listing.image_url)

    sug: dict[str, Any] = {}
    vec: list[float] | None = None
    if img is not None:
        cut = v.cutter.cut(img)
        s, arr = tag(cut.crop, cut.rgb, cut.mask, v.emb, v.bank, v.palette)
        vec = [float(x) for x in arr]
        if s.status == "not_clothing" and listing is None:
            raise BadJob(
                "That picture doesn’t clearly show a piece of clothing. Crop the screenshot to the "
                "piece and try again."
            )
        sug = s.to_json()
    title = listing.title if listing else ""
    by_name = type_in(title) if title else None
    if by_name is None and not sug:
        raise BadJob("Couldn’t tell what the piece is. Add a screenshot that shows it clearly.")
    typ = by_name.type if by_name else str(sug["type"])
    category = by_name.category if by_name else str(sug["category"])
    formality = by_name.formality if by_name else int(sug["formality"])

    # Color: what you set, else what the store states, else what the picture shows.
    mine = str(payload.get("color") or "").strip().lower()
    store_color = (
        (color_in(title) or (color_in(listing.color) if listing.color else None))
        if listing
        else None
    )
    if mine:
        color, hex_, source = mine, None, "you"
    elif store_color:
        color, hex_, source = store_color, None, "store"
    elif sug:
        color, hex_, source = str(sug["color_name"]).lower(), str(sug["color_hex"]), "picture"
    else:
        color, hex_, source = "", None, "none"

    return Read(
        title=title,
        type=typ,
        category=category,
        formality=formality,
        color=color,
        hex=hex_,
        color_source=source,
        vec=vec,
        source="link" if listing else "screenshot",
        link_note=why_not if (url and listing is None) else None,
        price_cents=listing.price_cents if listing else None,
        image_url=listing.image_url if listing else None,
        fallback_name=str(sug.get("name") or typ.capitalize()),
    )


def run(
    payload: dict[str, Any],
    ctx: JobContext | None,
    vision: Vision | None = None,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    if ctx is None or ctx.items is None:
        raise BadJob("no item store")
    wish = ctx.items.get_wish(str(payload.get("wish_id", "")))
    if wish is None:
        raise BadJob("That check no longer exists.")
    v = vision or vision_for(ctx.settings.embed_model, ctx.settings.device)
    rd = read_piece(wish, payload, ctx, v, fetcher)
    if rd.vec is None:
        text = f"a photo of a {rd.color} {rd.type}".replace("  ", " ")
        rd.vec = [float(x) for x in v.emb.text([text])[0]]
        return check(wish, payload, ctx, rd, weights()["tau_text"])
    return check(wish, payload, ctx, rd, weights()["tau_image"])


def check(
    wish: dict[str, Any], payload: dict[str, Any], ctx: JobContext, rd: Read, tau: float | None
) -> dict[str, Any]:
    """Run every check on what was read and save it. `tau` None: no duplicate search (fake mode)."""
    assert ctx.items is not None
    url = str(wish.get("url") or "")
    occasion = wish.get("occasion") or None
    piece = Piece(
        id="check",
        name=rd.title or rd.fallback_name,
        category=rd.category,
        type=rd.type,
        color_name=rd.color,
        color_hex=rd.hex,
        formality=rd.formality,
        occasions=(occasion,) if occasion else ORDER,
    )

    rows = ctx.items.list_items()
    by_id = {str(r["id"]): r for r in rows}
    history = History.from_logs(ctx.items.list_wear_logs())
    profile = ctx.items.get_profile()
    tz = ZoneInfo(str(profile.get("timezone") or "America/New_York"))
    today = (
        date.fromisoformat(str(payload["date"])) if payload.get("date") else datetime.now(tz).date()
    )

    dupes: list[dict[str, Any]] | None = None
    if tau is not None and rd.vec is not None:
        dupes = []
        for n in ctx.items.nearest_items(rd.vec, rd.category, 5):
            r = by_id.get(str(n["item_id"]))
            if (
                r
                and r.get("status") != "retired"
                and not r.get("is_sample")
                and float(n["similarity"]) >= tau
            ):
                dupes.append({"name": r["name"], "wears": history.piece_wears.get(str(r["id"]), 0)})

    owned = [Piece.from_row(r) for r in rows if not r.get("is_sample")]
    unlocks = (
        {
            o: len(good_outfits_with(piece, owned, Context(occasion=o, day=today), profile))
            for o in ([occasion] if occasion else ORDER)
        }
        if owned
        else {}
    )

    c = Candidate(piece, rd.color_source, rd.title, dupes, unlocks)
    rating = judge(c, occasion, profile.get("analysis"), profile.get("fit_pref") or None)
    read = {
        "from": rd.source,
        "type": rd.type,
        "category": rd.category,
        "color": rd.color or None,
        "color_source": rd.color_source,
        "link_note": rd.link_note,
    }
    result = {**rating.to_json(), "read": read}
    old = wish.get("check_result")
    prev: dict[str, Any] = old if isinstance(old, dict) else {}
    fields: dict[str, Any] = {
        "check_result": {**prev, "suits": result},
        "checked_at": datetime.now(UTC).isoformat(),
        "category": rd.category,
    }
    if rd.vec is not None and len(rd.vec) == 512:
        fields["embedding"] = rd.vec
    if str(wish.get("name") or "") in ("", PLACEHOLDER):
        fields["name"] = (rd.title or rd.fallback_name)[:120]
    if rd.color and not wish.get("color_name"):
        fields["color_name"] = rd.color
    if rd.source == "link":
        if rd.price_cents is not None and wish.get("price_cents") is None:
            fields["price_cents"] = rd.price_cents
        if url and not wish.get("store"):
            fields["store"] = store_name(url)
        if rd.image_url and not wish.get("image_url") and rd.image_url.startswith("http"):
            fields["image_url"] = rd.image_url
    ctx.items.update_wish(str(wish["id"]), fields)
    return result
