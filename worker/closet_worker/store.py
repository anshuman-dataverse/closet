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
    def list_outfits(self) -> list[dict[str, Any]]: ...
    def list_wear_logs(self) -> list[dict[str, Any]]: ...
    def get_profile(self) -> dict[str, Any]: ...
    def insert_events(self, rows: list[dict[str, Any]]) -> list[str]: ...
    def get_wish(self, wish_id: str) -> dict[str, Any] | None: ...
    def update_wish(self, wish_id: str, fields: dict[str, Any]) -> None: ...
    def nearest_items(
        self, vec: list[float], category: str | None, k: int
    ) -> list[dict[str, Any]]: ...


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

    def _rows(self, res: Any) -> list[dict[str, Any]]:
        data = res.data if isinstance(res.data, list) else []
        return [dict(r) for r in data if isinstance(r, dict)]

    def list_outfits(self) -> list[dict[str, Any]]:
        outfits = self._rows(
            self.db.table("outfits").select("*").eq("user_id", self.owner).execute()
        )
        links = self._rows(
            self.db.table("outfit_items")
            .select("outfit_id,item_id,position")
            .eq("user_id", self.owner)
            .execute()
        )
        by: dict[str, list[tuple[int, str]]] = {}
        for r in links:
            by.setdefault(str(r["outfit_id"]), []).append((int(r["position"]), str(r["item_id"])))
        for o in outfits:
            o["item_ids"] = [i for _, i in sorted(by.get(str(o["id"]), []))]
        return outfits

    def list_wear_logs(self) -> list[dict[str, Any]]:
        logs = self._rows(
            self.db.table("wear_logs").select("*").eq("user_id", self.owner).execute()
        )
        links = self._rows(
            self.db.table("wear_log_items")
            .select("wear_log_id,item_id")
            .eq("user_id", self.owner)
            .execute()
        )
        by: dict[str, list[str]] = {}
        for r in links:
            by.setdefault(str(r["wear_log_id"]), []).append(str(r["item_id"]))
        for log in logs:
            log["item_ids"] = by.get(str(log["id"]), [])
        return logs

    def get_profile(self) -> dict[str, Any]:
        rows = self._rows(
            self.db.table("profiles").select("*").eq("user_id", self.owner).limit(1).execute()
        )
        return rows[0] if rows else {}

    def insert_events(self, rows: list[dict[str, Any]]) -> list[str]:
        res = (
            self.db.table("suggestion_events")
            .insert([{**r, "user_id": self.owner} for r in rows])
            .execute()
        )
        return [str(r["id"]) for r in self._rows(res)]

    def get_wish(self, wish_id: str) -> dict[str, Any] | None:
        q = (
            self.db.table("wishlist_items")
            .select("*")
            .eq("id", wish_id)
            .eq("user_id", self.owner)
            .limit(1)
        )
        rows = self._rows(q.execute())
        return rows[0] if rows else None

    def update_wish(self, wish_id: str, fields: dict[str, Any]) -> None:
        self.db.table("wishlist_items").update(fields).eq("id", wish_id).eq(
            "user_id", self.owner
        ).execute()

    def nearest_items(self, vec: list[float], category: str | None, k: int) -> list[dict[str, Any]]:
        res = self.db.rpc(
            "nearest_items",
            {"p_owner": self.owner, "p_embedding": vec, "p_category": category, "p_k": k},
        ).execute()
        return self._rows(res)
