"""What this Mac can do right now. Reported in every heartbeat."""

from __future__ import annotations

import httpx

from .config import Settings


def _reachable(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2.0).status_code < 500
    except httpx.HTTPError:
        return False


def detect(settings: Settings) -> dict[str, bool]:
    return {
        "searxng": _reachable(f"{settings.searxng_url}/healthz"),
        "ollama": bool(settings.ollama_model) and _reachable(f"{settings.ollama_url}/api/tags"),
        "openai": settings.has_openai and settings.paid_monthly_cap_usd > 0,
    }
