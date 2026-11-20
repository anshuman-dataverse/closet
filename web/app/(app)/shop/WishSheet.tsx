"use client";
/* eslint-disable @next/next/no-img-element -- local blob preview */

import { useEffect, useRef, useState } from "react";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { saveWish, useCloset } from "@/lib/closet/store";
import { CATEGORIES, type Category } from "@/lib/closet/types";
import { parseDollars } from "@/lib/domain/money";
import { normalizeUrl, storeFromUrl } from "@/lib/domain/url";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { preparePhoto, removePaths, uploadPhotoTo } from "@/lib/photos";
import { supabase } from "@/lib/supabase/client";

export type WishDraft = {
  name: string;
  category: Category | "";
  color_name: string;
  occasion: Occasion | "";
  price: string;
  store: string;
  url: string;
  notes: string;
  watch: boolean;
  target: string;
};

export const emptyWish = (p: Partial<WishDraft> = {}): WishDraft => ({
  name: "",
  category: "",
  color_name: "",
  occasion: "",
  price: "",
  store: "",
  url: "",
  notes: "",
  watch: false,
  target: "",
  ...p,
});

/** Add to wishlist (SPEC 4.4). */
export function WishSheet({
  open,
  onClose,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  initial?: Partial<WishDraft>;
}) {
  const s = useCloset();
  const toast = useToast();
  const [f, setF] = useState<WishDraft>(emptyWish());
  const [id, setId] = useState("");
  const [photo, setPhoto] = useState<{
    preview: string;
    promise: Promise<{ photo_path: string; thumb_path: string }>;
  } | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [openedFor, setOpenedFor] = useState(false);
  if (open !== openedFor) {
    setOpenedFor(open);
    if (open) {
      setF(emptyWish(initial));
      setId(crypto.randomUUID());
      setPhoto(null);
      setErr("");
      setBusy(false);
    }
  }
  // Closing without saving drops an uploaded photo (a successful save clears `photo` first).
  useEffect(() => {
    if (open || !photo) return;
    void photo.promise.then((p) => removePaths(supabase(), [p.photo_path, p.thumb_path])).catch(() => {});
  }, [open, photo]);
  const set = <K extends keyof WishDraft>(k: K, v: WishDraft[K]) => setF((x) => ({ ...x, [k]: v }));

  const pick = async (file: File | undefined) => {
    if (!file || !s.userId) return;
    try {
      const p = await preparePhoto(file);
      setPhoto({ preview: p.previewUrl, promise: uploadPhotoTo(supabase(), `${s.userId}/wishlist/${id}`, p) });
      setErr("");
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const save = async () => {
    const name = f.name.trim();
    if (!name) return setErr("Give it a name, like “Light blue oxford shirt”.");
    const url = f.url.trim() ? normalizeUrl(f.url) : null;
    if (f.url.trim() && !url) return setErr("That link doesn’t look right. Paste the full web address.");
    const price = f.price.trim() ? parseDollars(f.price) : null;
    const target = f.target.trim() ? parseDollars(f.target) : null;
    if ((f.price.trim() && price === null) || (f.target.trim() && target === null))
      return setErr("Enter prices as numbers, like 49.50.");
    setBusy(true);
    setErr("");
    try {
      const up = photo ? await photo.promise : null;
      await saveWish({
        id,
        name: name.slice(0, 120),
        category: f.category || null,
        color_name: f.color_name.trim() || null,
        occasion: f.occasion || null,
        price_cents: price,
        url,
        store: f.store.trim() || storeFromUrl(url) || null,
        notes: f.notes.trim() || null,
        photo_path: up?.photo_path ?? null,
        watch: f.watch,
        target_price_cents: f.watch ? target : null,
      });
      setPhoto(null);
      toast("Added to your wishlist");
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Add to wishlist"
      actions={
        <>
          <span className="grow" />
          <button type="button" className="btn primary" onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Add to wishlist"}
          </button>
        </>
      }
    >
      <label className="field">
        <span>Name</span>
        <input
          type="text"
          value={f.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Light blue oxford shirt"
          autoComplete="off"
          maxLength={120}
        />
      </label>
      <div className="field-row">
        <label className="field">
          <span>Category</span>
          <select value={f.category} onChange={(e) => set("category", e.target.value as Category | "")}>
            <option value="">—</option>
            {CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Color</span>
          <input
            type="text"
            value={f.color_name}
            onChange={(e) => set("color_name", e.target.value)}
            autoComplete="off"
            maxLength={40}
          />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Occasion</span>
          <select value={f.occasion} onChange={(e) => set("occasion", e.target.value as Occasion | "")}>
            <option value="">Any</option>
            {OCCASIONS.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Price ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.price}
            onChange={(e) => set("price", e.target.value)}
            autoComplete="off"
          />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Store</span>
          <input
            type="text"
            value={f.store}
            onChange={(e) => set("store", e.target.value)}
            autoComplete="off"
            maxLength={60}
          />
        </label>
        <label className="field">
          <span>Link</span>
          <input
            type="url"
            value={f.url}
            onChange={(e) => set("url", e.target.value)}
            placeholder="uniqlo.com/…"
            autoComplete="off"
          />
        </label>
      </div>
      <label className="field">
        <span>Notes</span>
        <textarea rows={2} value={f.notes} onChange={(e) => set("notes", e.target.value)} maxLength={500} />
      </label>
      <div className="photo-pick">
        <div className="photo-box">
          {photo ? <img src={photo.preview} alt="Wishlist photo" /> : <span className="muted">No photo</span>}
        </div>
        <div className="col">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            hidden
            data-testid="wish-photo-input"
            onChange={(e) => {
              void pick(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button type="button" className="btn sm" onClick={() => fileRef.current?.click()}>
            {photo ? "Change photo" : "Add a photo or screenshot"}
          </button>
        </div>
      </div>
      <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
        <input type="checkbox" checked={f.watch} onChange={(e) => set("watch", e.target.checked)} />
        <span style={{ marginBottom: 0 }}>Watch price</span>
      </label>
      {f.watch && (
        <label className="field">
          <span>Tell me when it’s at or below ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.target}
            onChange={(e) => set("target", e.target.value)}
            autoComplete="off"
          />
        </label>
      )}
      <p className="err" role="alert">
        {err}
      </p>
    </Sheet>
  );
}
