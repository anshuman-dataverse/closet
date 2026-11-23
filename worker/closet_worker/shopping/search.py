"""Local SearXNG (SPEC 5.8 step 2): /search?q=…&format=json, on 127.0.0.1 only."""

from __future__ import annotations

import httpx


class SearchError(Exception):
    pass


def search(base_url: str, query: str, client: httpx.Client | None = None) -> list[str]:
    c = client or httpx.Client(timeout=20.0)
    try:
        r = c.get(f"{base_url}/search", params={"q": query, "format": "json", "language": "en-US"})
    except httpx.HTTPError as e:
        raise SearchError(f"SearXNG isn’t reachable at {base_url}") from e
    if r.status_code != 200:
        raise SearchError(f"SearXNG answered {r.status_code} (is JSON output on in its settings?)")
    return [str(x["url"]) for x in r.json().get("results", []) if x.get("url")]
