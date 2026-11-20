from __future__ import annotations

import pytest
from pydantic import ValidationError

from closet_worker.config import Settings

BASE = {
    "supabase_url": "https://abc.supabase.co/",
    "supabase_service_role_key": "secret",
    "owner_user_id": "11111111-1111-1111-1111-111111111111",
}


def make(**kw: object) -> Settings:
    return Settings(_env_file=None, **{**BASE, **kw})  # type: ignore[arg-type]


def test_defaults() -> None:
    s = make()
    assert s.supabase_url == "https://abc.supabase.co"
    assert s.worker_id == "mac"
    assert s.paid_monthly_cap_usd == 0
    assert not s.has_openai
    assert "~" not in str(s.backup_dir)


def test_owner_required() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, supabase_url="https://x.co", supabase_service_role_key="k")  # type: ignore[call-arg]


def test_owner_must_be_uuid() -> None:
    with pytest.raises(ValidationError):
        make(owner_user_id="me")


def test_searxng_must_be_local() -> None:
    with pytest.raises(ValidationError):
        make(searxng_url="http://searx.example.com")


def test_blank_openai_key_is_none() -> None:
    assert make(openai_api_key="  ").openai_api_key is None


def test_secret_not_in_repr() -> None:
    assert "secret" not in repr(make())
