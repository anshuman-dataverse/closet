"""Polite fetching (SPEC 5.8 step 4): robots.txt, 1 request per second per site, 10 s timeout.

Every refusal is recorded with its reason (robots.txt, blocked, timeout…) so the hunt can say
honestly why it found little, instead of guessing.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urlsplit

import httpx

USER_AGENT = (
    "ClosetDealHunter/0.1 (personal wardrobe app; reads public product pages; honors robots.txt)"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.8"}
TIMEOUT_S = 10.0
MIN_GAP_S = 1.0  # per site
MAX_BYTES = 12_000_000  # some stores ship 5–8 MB product pages


@dataclass
class Page:
    url: str
    status: int
    text: str = ""
    content: bytes = b""
    reason: str = ""  # why it wasn't read: robots | blocked | not_found | timeout | error | too_big

    @property
    def ok(self) -> bool:
        return not self.reason


@dataclass
class Fetcher:
    client: httpx.Client = field(
        default_factory=lambda: httpx.Client(
            headers=HEADERS,
            timeout=TIMEOUT_S,
            follow_redirects=True,
        )
    )
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _last: dict[str, float] = field(default_factory=dict)
    _robots: dict[str, robotparser.RobotFileParser | None] = field(default_factory=dict)
    requests: int = 0

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = self.clock() - last
            if gap < MIN_GAP_S:
                self.sleep(MIN_GAP_S - gap)
        self._last[host] = self.clock()

    def allowed(self, url: str) -> bool:
        u = urlsplit(url)
        host = u.hostname or ""
        if host not in self._robots:
            self._wait(host)
            parser = robotparser.RobotFileParser()
            rp: robotparser.RobotFileParser | None = parser
            try:
                r = self.client.get(f"{u.scheme}://{host}/robots.txt", headers=HEADERS)
                self.requests += 1
                if r.status_code >= 500:
                    rp = None  # can't tell: treat as disallowed
                elif r.status_code >= 400:
                    parser.parse([])  # no robots.txt: everything allowed
                else:
                    parser.parse(r.text.splitlines())
            except httpx.HTTPError:
                rp = None
            self._robots[host] = rp
        rp = self._robots[host]
        return rp is not None and rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, *, check_robots: bool = True) -> Page:
        host = urlsplit(url).hostname or ""
        if check_robots and not self.allowed(url):
            return Page(url, 0, reason="robots")
        self._wait(host)
        try:
            r = self.client.get(url, headers=HEADERS)
            self.requests += 1
        except httpx.TimeoutException:
            return Page(url, 0, reason="timeout")
        except httpx.HTTPError:
            return Page(url, 0, reason="error")
        if r.status_code in (401, 403, 429) or r.status_code == 503:
            return Page(url, r.status_code, reason="blocked")
        if r.status_code == 404 or r.status_code == 410:
            return Page(url, r.status_code, reason="not_found")
        if r.status_code >= 400:
            return Page(url, r.status_code, reason="error")
        if len(r.content) > MAX_BYTES:
            return Page(url, r.status_code, reason="too_big")
        return Page(str(r.url), r.status_code, r.text, r.content)
