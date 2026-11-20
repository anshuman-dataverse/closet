"""Item and Storage access for job handlers. Every call is scoped to OWNER_USER_ID."""

from __future__ import annotations

from typing import Any, Protocol

from supabase import Client

BUCKET = "wardrobe"


class ItemStore(Protocol):
    owner: str

    def get_item(self, item_id: str) -> dict[str, Any] | None: ...
    def update_item(self, item_id: str, fields: dict[str, Any]) -> None: ...
    def download(self, path: str) -> bytes: ...
    def upload(self, path: str, data: bytes, content_type: str) -> None: ...
    def upsert_embedding(self, item_id: str, model: str, vec: list[float]) -> None: ...
    def list_items(self) -> list[dict[str, Any]]: ...


class SupabaseItemStore:
    def __init__(self, db: Client, owner: str) -> None:
        self.db = db
        self.owner = owner

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        res = (
            self.db.table("items")
            .select("*")
            .eq("id", item_id)
            .eq("user_id", self.owner)
            .limit(1)
            .execute()
        )
        rows = res.data if isinstance(res.data, list) else []
        return dict(rows[0]) if rows and isinstance(rows[0], dict) else None

    def list_items(self) -> list[dict[str, Any]]:
        res = (
            self.db.table("items")
            .select("*")
            .eq("user_id", self.owner)
            .order("created_at")
            .execute()
        )
        rows = res.data if isinstance(res.data, list) else []
        return [dict(r) for r in rows if isinstance(r, dict)]

    def update_item(self, item_id: str, fields: dict[str, Any]) -> None:
        self.db.table("items").update(fields).eq("id", item_id).eq("user_id", self.owner).execute()

    def _own(self, path: str) -> str:
        if not path.startswith(f"{self.owner}/"):
            raise PermissionError("path outside the owner's folder")
        return path

    def download(self, path: str) -> bytes:
        return bytes(self.db.storage.from_(BUCKET).download(self._own(path)))

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self.db.storage.from_(BUCKET).upload(
            self._own(path), data, {"content-type": content_type, "upsert": "true"}
        )

    def upsert_embedding(self, item_id: str, model: str, vec: list[float]) -> None:
        self.db.table("item_embeddings").upsert(
            {"item_id": item_id, "user_id": self.owner, "model": model, "embedding": vec}
        ).execute()
