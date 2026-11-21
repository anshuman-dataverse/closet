"""Read a garment's own label: brand, size, materials, and fit when the label says it.

Text comes from Apple's on-device text recognition (Vision framework, through PyObjC), so the
photo never leaves the Mac. Parsing only reports what is printed: a size is reported only when the
label shows exactly one, a fit only when a fit word is on the label, materials only for known
fibers with a percentage. The brand is the most prominent line of text that isn't a size, a
material or care wording, and the app shows it as a suggestion you can change.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Line:
    text: str
    confidence: float
    height: float  # share of the photo's height (bigger = more prominent)


class TextReader(Protocol):
    def read(self, image: bytes) -> list[Line]: ...


class AppleVisionReader:
    """VNRecognizeTextRequest, accurate mode. macOS only."""

    def read(self, image: bytes) -> list[Line]:
        import Vision
        from Foundation import NSData

        data = NSData.dataWithBytes_length_(image, len(image))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(True)
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(f"text recognition failed: {err}")
        out: list[Line] = []
        for obs in req.results() or []:
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            c = cands[0]
            out.append(
                Line(str(c.string()), float(c.confidence()), float(obs.boundingBox().size.height))
            )
        return out


FIBERS = {
    "cotton": "cotton",
    "organic cotton": "organic cotton",
    "polyester": "polyester",
    "recycled polyester": "recycled polyester",
    "elastane": "elastane",
    "spandex": "elastane",
    "lycra": "elastane",
    "viscose": "viscose",
    "rayon": "viscose",
    "lyocell": "lyocell",
    "tencel": "lyocell",
    "modal": "modal",
    "linen": "linen",
    "flax": "linen",
    "wool": "wool",
    "merino": "merino wool",
    "merino wool": "merino wool",
    "cashmere": "cashmere",
    "silk": "silk",
    "nylon": "nylon",
    "polyamide": "nylon",
    "acrylic": "acrylic",
    "hemp": "hemp",
    "leather": "leather",
}
_FIBER_RE = "|".join(sorted((re.escape(k) for k in FIBERS), key=len, reverse=True))
PCT_FIRST = re.compile(rf"(\d{{1,3}}) ?%[ \t]*({_FIBER_RE})\b", re.I)
FIBER_FIRST = re.compile(rf"\b({_FIBER_RE})[ \t:]*(\d{{1,3}}) ?%", re.I)

LETTER_SIZES = ("XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "2XL", "3XL", "4XL")
LETTER_LINE = re.compile(rf"^(?:size[:\s]*)?({'|'.join(LETTER_SIZES)})$", re.I)
SIZE_PREFIX = re.compile(rf"\bsize[:\s]+({'|'.join(LETTER_SIZES)}|\d{{1,2}}(?:\.\d)?)\b", re.I)
WAIST_INSEAM = (
    re.compile(r"\bW\s?(\d{2})\s*[/ ]?\s*L\s?(\d{2})\b", re.I),
    re.compile(r"\b(\d{2})\s?W\s*[/ ]?\s*(\d{2})\s?L\b", re.I),
    re.compile(r"\b(\d{2})\s?[x×/]\s?(\d{2})\b"),
)

# Fit words printed on labels → fit ids in vocab/fits.yaml. Longest phrases are matched first.
FIT_WORDS = {
    "skinny fit": "skinny",
    "skinny": "skinny",
    "super skinny": "skinny",
    "slim fit": "slim",
    "slim taper": "slim",
    "slim tapered": "slim",
    "slim straight": "straight",
    "straight fit": "straight",
    "straight leg": "straight",
    "regular fit": "regular",
    "classic fit": "regular",
    "relaxed fit": "relaxed",
    "relaxed": "relaxed",
    "loose fit": "relaxed",
    "oversized fit": "oversized",
    "oversized": "oversized",
    "oversize": "oversized",
    "boxy fit": "oversized",
    "wide leg": "wide",
    "wide fit": "wide",
    "baggy": "wide",
    "bootcut": "bootcut",
    "boot cut": "bootcut",
    "flare": "flare",
    "flared": "flare",
    "cropped": "cropped",
    "a-line": "a-line",
    "bodycon": "bodycon",
}
_FIT_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(FIT_WORDS, key=len, reverse=True)) + r")\b",
    re.I,
)

NOT_BRAND = re.compile(
    r"\d|%|\b(made in|size|wash|dry|iron|bleach|tumble|care|cotton|polyester|fit|fabric|"
    r"style|rn|ca|art|ref|model|machine|cold|warm|hot|do not|only|with like colors|reverse)\b",
    re.I,
)


@dataclass
class LabelRead:
    brand: str | None = None
    size: str | None = None
    fit: str | None = None
    materials: list[dict[str, Any]] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # why a field was left out

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def materials_text(self) -> str:
        return ", ".join(f"{m['pct']}% {m['fiber']}" for m in self.materials)


def _materials(texts: list[str]) -> list[dict[str, Any]]:
    """Line by line. Each line is read in its own order: "98% cotton 2% elastane" (percent
    first) or "COTTON 60% POLYESTER 40%" (fiber first), whichever starts earlier on the line."""
    found: dict[str, int] = {}
    for t in texts:
        a, b = PCT_FIRST.search(t), FIBER_FIRST.search(t)
        if a is None and b is None:
            continue
        if b is None or (a is not None and a.start() <= b.start()):
            pairs = [(m.group(2), int(m.group(1))) for m in PCT_FIRST.finditer(t)]
        else:
            pairs = [(m.group(1), int(m.group(2))) for m in FIBER_FIRST.finditer(t)]
        for fiber, pct in pairs:
            found.setdefault(FIBERS[fiber.lower()], pct)
    items = [(f, p) for f, p in found.items() if 0 < p <= 100]
    # Reported only when the fibers add up to 100%: a partial read (lining, a missed line) or a
    # label listing several parts would otherwise give a wrong composition.
    if sum(p for _, p in items) != 100:
        return []
    return [{"fiber": f, "pct": p} for f, p in sorted(items, key=lambda x: -x[1])]


def _sizes(lines: list[str]) -> set[str]:
    out: set[str] = set()
    for t in lines:
        s = t.strip()
        if m := LETTER_LINE.match(s):
            out.add(m.group(1).upper())
        if m := SIZE_PREFIX.search(s):
            out.add(m.group(1).upper())
        for rx in WAIST_INSEAM:
            if m := rx.search(s):
                w, inseam = int(m.group(1)), int(m.group(2))
                if 24 <= w <= 50 and 24 <= inseam <= 40:
                    out.add(f"W{w} L{inseam}")
    return out


def parse(lines: list[Line], min_confidence: float = 0.4) -> LabelRead:
    good = [x for x in lines if x.confidence >= min_confidence and x.text.strip()]
    texts = [x.text.strip() for x in good]
    joined = " \n ".join(texts)
    r = LabelRead(lines=texts)

    r.materials = _materials(texts)
    if not r.materials and (PCT_FIRST.search(joined) or FIBER_FIRST.search(joined)):
        r.notes.append("materials didn’t add up to 100%, so they were left out")

    sizes = _sizes(texts)
    if len(sizes) == 1:
        r.size = next(iter(sizes))
    elif len(sizes) > 1:
        r.notes.append(
            f"more than one size printed ({', '.join(sorted(sizes))}), so none was picked"
        )

    fits = {FIT_WORDS[m.group(1).lower()] for m in _FIT_RE.finditer(joined)}
    if len(fits) == 1:
        r.fit = next(iter(fits))
    elif len(fits) > 1:
        r.notes.append(f"more than one fit word ({', '.join(sorted(fits))}), so none was picked")

    candidates = [
        x
        for x in good
        if 2 <= len(x.text.strip()) <= 30
        and not NOT_BRAND.search(x.text)
        and sum(c.isalpha() for c in x.text) >= 2
        and x.text.strip().upper() not in LETTER_SIZES
    ]
    if candidates:
        top = max(candidates, key=lambda x: x.height)
        r.brand = " ".join(top.text.split())
    return r
