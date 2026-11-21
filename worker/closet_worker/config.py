"""Worker settings, read from worker/.env (never committed)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKER_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=WORKER_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_service_role_key: SecretStr
    owner_user_id: UUID
    database_url: SecretStr | None = None
    worker_id: str = Field(default="mac", min_length=1, max_length=40)
    embed_model: str = "patrickjohncyh/fashion-clip"
    device: Literal["auto", "mps", "cpu"] = "auto"
    searxng_url: str = "http://127.0.0.1:8888"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    openai_api_key: SecretStr | None = None
    openai_model: str = ""
    paid_monthly_cap_usd: float = Field(default=0.0, ge=0)
    backup_dir: Path = Path("~/ClosetBackups")
    # Outfit compatibility model files from colab/outfit_compat.ipynb (SPEC 5.11). Optional.
    compat_model_dir: Path = Path("~/.cache/closet/compat")
    # Which fits the tagging eval measured as reliable on your photos (closet-worker import).
    fit_gate_path: Path = Path("~/.cache/closet/fit/gate.json")

    @field_validator("supabase_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not v.startswith(("http://", "https://")):
            raise ValueError("SUPABASE_URL must start with http:// or https://")
        return v

    @field_validator("searxng_url", "ollama_url")
    @classmethod
    def _local_only(cls, v: str) -> str:
        # SPEC 9: SearXNG and Ollama bind to localhost only.
        v = v.strip().rstrip("/")
        if not v.startswith(("http://127.0.0.1", "http://localhost")):
            raise ValueError("SearXNG and Ollama must be on 127.0.0.1 or localhost")
        return v

    @field_validator("backup_dir", "compat_model_dir", "fit_gate_path")
    @classmethod
    def _expand(cls, v: Path) -> Path:
        return v.expanduser()

    @field_validator("openai_api_key", "database_url", mode="before")
    @classmethod
    def _blank_is_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v

    @property
    def owner(self) -> str:
        return str(self.owner_user_id)

    @property
    def has_openai(self) -> bool:
        return self.openai_api_key is not None


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from env / .env
