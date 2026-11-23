"""Item and Storage access for job handlers. Every call is scoped to OWNER_USER_ID."""

from __future__ import annotations

import json
from typing import Any, Protocol

from postgrest.types import CountMethod
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
    def list_style_photos(self) -> list[dict[str, Any]]: ...
    def update_profile(self, fields: dict[str, Any]) -> None: ...
    def list_embeddings(self, model: str) -> dict[str, list[float]]: ...
    def list_suggestion_events(self) -> list[dict[str, Any]]: ...
    def list_storage(self) -> list[tuple[str, int]]: ...
    def count_rows(self, tables: tuple[str, ...]) -> dict[str, int]: ...
    def get_hunt(self, hunt_id: str) -> dict[str, Any] | None: ...
    def update_hunt(self, hunt_id: str, fields: dict[str, Any]) -> None: ...
    def replace_hunt_results(self, hunt_id: str, rows: list[dict[str, Any]]) -> None: ...
    def list_watched_wishes(self) -> list[dict[str, Any]]: ...
    def insert_price_check(self, row: dict[str, Any]) -> None: ...


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

    def list_style_photos(self) -> list[dict[str, Any]]:
        q = (
            self.db.table("style_photos")
            .select("*")
            .eq("user_id", self.owner)
            .order("created_at", desc=True)
        )
        return self._rows(q.execute())

    def update_profile(self, fields: dict[str, Any]) -> None:
        self.db.table("profiles").update(fields).eq("user_id", self.owner).execute()

    def list_embeddings(self, model: str) -> dict[str, list[float]]:
        """item_id → vector, for one embedding model (pgvector comes back as text "[…]")."""
        res = (
            self.db.table("item_embeddings")
            .select("item_id, embedding")
            .eq("user_id", self.owner)
            .eq("model", model)
            .execute()
        )
        out: dict[str, list[float]] = {}
        for r in self._rows(res):
            v = r.get("embedding")
            if isinstance(v, str):
                v = json.loads(v)
            if isinstance(v, list):
                out[str(r["item_id"])] = [float(x) for x in v]
        return out

    def list_suggestion_events(self) -> list[dict[str, Any]]:
        res = (
            self.db.table("suggestion_events")
            .select("occasion, item_ids, context, action, created_at")
            .eq("user_id", self.owner)
            .order("created_at")
            .execute()
        )
        return self._rows(res)

    def list_storage(self) -> list[tuple[str, int]]:
        """(path, size) of every file under the owner's folder in the bucket, recursively."""
        bucket = self.db.storage.from_(BUCKET)
        out: list[tuple[str, int]] = []
        folders = [self.owner]
        while folders:
            folder = folders.pop()
            offset = 0
            while True:
                page = bucket.list(folder, {"limit": 1000, "offset": offset})
                for e in page:
                    path = f"{folder}/{e['name']}"
                    if e.get("id") is None:  # a folder
                        folders.append(path)
                    else:
                        out.append((path, int((e.get("metadata") or {}).get("size") or 0)))
                if len(page) < 1000:
                    break
                offset += 1000
        return sorted(out)

    def count_rows(self, tables: tuple[str, ...]) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in tables:
            res = (
                self.db.table(t)
                .select("*", count=CountMethod.exact, head=True)
                .eq("user_id", self.owner)
                .execute()
            )
            out[t] = int(res.count or 0)
        return out

    def get_hunt(self, hunt_id: str) -> dict[str, Any] | None:
        res = (
            self.db.table("hunts")
            .select("*")
            .eq("id", hunt_id)
            .eq("user_id", self.owner)
            .limit(1)
            .execute()
        )
        rows = self._rows(res)
        return rows[0] if rows else None

    def update_hunt(self, hunt_id: str, fields: dict[str, Any]) -> None:
        self.db.table("hunts").update(fields).eq("id", hunt_id).eq("user_id", self.owner).execute()

    def replace_hunt_results(self, hunt_id: str, rows: list[dict[str, Any]]) -> None:
        """Idempotent: a rerun replaces this hunt's picks instead of adding more."""
        self.db.table("hunt_results").delete().eq("hunt_id", hunt_id).eq(
            "user_id", self.owner
        ).execute()
        if rows:
            self.db.table("hunt_results").insert(
                [{**r, "hunt_id": hunt_id, "user_id": self.owner} for r in rows]
            ).execute()

    def list_watched_wishes(self) -> list[dict[str, Any]]:
        res = (
            self.db.table("wishlist_items")
            .select("id, name, url, price_cents, target_price_cents, last_seen_price_cents")
            .eq("user_id", self.owner)
            .eq("watch", True)
            .eq("status", "wanted")
            .not_.is_("url", "null")
            .execute()
        )
        return self._rows(res)

    def insert_price_check(self, row: dict[str, Any]) -> None:
        self.db.table("price_checks").insert({**row, "user_id": self.owner}).execute()
