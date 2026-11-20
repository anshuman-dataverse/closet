"use client";
/* eslint-disable @next/next/no-img-element -- local blob preview */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Chips, toggle } from "@/components/Chips";
import { ConfirmButton } from "@/components/ConfirmButton";
import { HangTag } from "@/components/HangTag";
import { PieceCell } from "@/components/Piece";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { deleteItem, type ItemInput, saveItem, setItemsStatus, useCloset, useDerived } from "@/lib/closet/store";
import { CATEGORIES, type Category, type Item } from "@/lib/closet/types";
import { NAMED, safeHex, swatchFor } from "@/lib/domain/colors";
import { isYmd, lastWornText } from "@/lib/domain/dates";
import { centsToInput, formatCents, parseDollars } from "@/lib/domain/money";
import { STARTERS, type Starter } from "@/lib/domain/starters";
import { costPerWear, NO_WEAR } from "@/lib/domain/wear";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { preparePhoto, removePaths, uploadItemPhoto } from "@/lib/photos";
import { supabase } from "@/lib/supabase/client";

const FORMALITY = ["", "1 · Lounge", "2 · Casual", "3 · Smart casual", "4 · Business", "5 · Formal"];

type Form = {
  name: string;
  category: Category;
  type: string;
  color_name: string;
  pattern: string;
  occasions: Occasion[];
  formality: string;
  warmth: string;
  price: string;
  bought_on: string;
  brand: string;
  size: string;
  store: string;
  notes: string;
};

const blank = (occ: Occasion[] = []): Form => ({
  name: "",
  category: "Tops",
  type: "",
  color_name: "",
  pattern: "",
  occasions: occ,
  formality: "",
  warmth: "",
  price: "",
  bought_on: "",
  brand: "",
  size: "",
  store: "",
  notes: "",
});

const fromItem = (i: Item): Form => ({
  name: i.name,
  category: i.category ?? "Tops",
  type: i.type ?? "",
  color_name: i.color_name ?? "",
  pattern: i.pattern ?? "",
  occasions: [...i.occasions],
  formality: i.formality ? String(i.formality) : "",
  warmth: i.warmth ?? "",
  price: centsToInput(i.price_cents),
  bought_on: i.bought_on ?? "",
  brand: i.brand ?? "",
  size: i.size ?? "",
  store: i.store ?? "",
  notes: i.notes ?? "",
});

type Upload = { previewUrl: string; promise: Promise<{ photo_path: string; thumb_path: string }> };

export function ItemSheet({ open, itemId, onClose }: { open: boolean; itemId: string | null; onClose: () => void }) {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const item = itemId ? (d.byId.get(itemId) ?? null) : null;
  const editing = !!item;

  const [form, setForm] = useState<Form>(blank());
  const [draftId, setDraftId] = useState("");
  const [upload, setUpload] = useState<Upload | null>(null);
  const [hint, setHint] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const uid = useId();

  // Reset whenever the sheet opens for a different piece.
  const [openedFor, setOpenedFor] = useState<string | null | undefined>(undefined);
  const key = open ? (itemId ?? "new") : undefined;
  if (key !== openedFor) {
    setOpenedFor(key);
    if (open) {
      setForm(item ? fromItem(item) : blank());
      setDraftId(item ? item.id : crypto.randomUUID());
      setUpload(null);
      setHint("");
      setErr("");
      setBusy(false);
    }
  }

  // Drop an uploaded-but-unsaved photo when the sheet closes without saving.
  // (A successful save clears `upload` before closing, so only abandoned uploads get here.)
  useEffect(() => {
    if (open || !upload) return;
    void upload.promise.then((p) => removePaths(supabase(), [p.photo_path, p.thumb_path])).catch(() => {});
  }, [open, upload]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm((f) => ({ ...f, [k]: v }));

  const owned = useMemo(() => new Set(s.items.map((i) => i.name.trim().toLowerCase())), [s.items]);
  const starters = editing ? [] : STARTERS.filter((x) => !owned.has(x.name.toLowerCase()));

  const applyStarter = (st: Starter) => {
    setForm((f) => ({
      ...f,
      name: st.name,
      category: st.category,
      type: st.type,
      color_name: st.color_name,
      occasions: [...st.occasions],
    }));
    setErr("");
  };

  const pickPhoto = async (file: File | undefined) => {
    if (!file || !s.userId) return;
    setHint("Preparing the photo…");
    setErr("");
    try {
      const prepared = await preparePhoto(file);
      const promise = uploadItemPhoto(supabase(), s.userId, draftId, prepared);
      promise.then(
        () => setHint("Photo ready."),
        (e: Error) => {
          setUpload(null);
          setHint("");
          setErr(e.message);
        },
      );
      setUpload({ previewUrl: prepared.previewUrl, promise });
      setHint("Uploading…");
    } catch (e) {
      setHint("");
      setErr((e as Error).message);
    }
  };

  const save = async (again: boolean) => {
    const name = form.name.trim();
    if (!name) {
      setErr("Give it a name, like “Navy oxford shirt”.");
      nameRef.current?.focus();
      return;
    }
    const price = form.price.trim() ? parseDollars(form.price) : null;
    if (form.price.trim() && price === null) {
      setErr("Enter the price as a number, like 39.50.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const photo = upload ? await upload.promise : null;
      const colorHex =
        safeHex(item?.color_hex) && form.color_name === (item?.color_name ?? "") ? item!.color_hex : null;
      const input: ItemInput & { id: string } = {
        id: draftId,
        name: name.slice(0, 80),
        category: form.category,
        type: form.type.trim() || null,
        color_name: form.color_name.trim() || null,
        color_hex: colorHex,
        pattern: form.pattern.trim() || null,
        occasions: form.occasions,
        formality: form.formality ? Number(form.formality) : null,
        warmth: (form.warmth || null) as ItemInput["warmth"],
        price_cents: price,
        bought_on: isYmd(form.bought_on) ? form.bought_on : null,
        brand: form.brand.trim() || null,
        size: form.size.trim() || null,
        store: form.store.trim() || null,
        notes: form.notes.trim() || null,
        ...(photo ?? {}),
        ...(photo && item?.cutout_path ? { cutout_path: null } : {}),
      };
      const replaced = photo && item ? [item.photo_path, item.thumb_path, item.cutout_path] : [];
      await saveItem(input, replaced);
      setUpload(null);
      if (again) {
        toast("Added to your closet");
        setForm((f) => ({ ...blank(f.occasions) }));
        setDraftId(crypto.randomUUID());
        setHint("");
        nameRef.current?.focus();
      } else {
        toast(editing ? "Saved" : "Added to your closet");
        onClose();
      }
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const status = async (next: "active" | "laundry" | "retired", msg: string) => {
    if (!item) return;
    try {
      await setItemsStatus([item.id], next);
      toast(msg);
      onClose();
    } catch (e) {
      setErr((e as Error).message);
    }
  };

  const ws = item ? (d.stats.items.get(item.id) ?? NO_WEAR) : NO_WEAR;
  const cpw = item ? costPerWear(item.price_cents, ws.count) : null;
  const inOutfits = item ? s.outfits.filter((o) => o.itemIds.includes(item.id)).length : 0;
  const swatch = swatchFor({ color_name: form.color_name }) || (item ? swatchFor(item) : "");
  const preview = upload?.previewUrl;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={editing ? item!.name : "Add clothes"}
      actions={
        <>
          {editing && (
            <>
              <ConfirmButton
                onConfirm={async () => {
                  try {
                    await deleteItem(item!.id);
                    toast("Deleted");
                    onClose();
                  } catch (e) {
                    setErr((e as Error).message);
                  }
                }}
              >
                Delete
              </ConfirmButton>
              {item!.status !== "retired" && (
                <button
                  type="button"
                  className="btn sm ghost"
                  onClick={() =>
                    item!.status === "laundry"
                      ? status("active", "Back in your closet")
                      : status("laundry", "In the laundry. It’s out of picks until it’s back.")
                  }
                >
                  {item!.status === "laundry" ? "Out of laundry" : "In laundry"}
                </button>
              )}
              <button
                type="button"
                className="btn sm ghost"
                onClick={() =>
                  item!.status === "retired"
                    ? status("active", "Back in your closet")
                    : status("retired", "Retired. It won’t come up in picks.")
                }
              >
                {item!.status === "retired" ? "Bring back" : "Retire"}
              </button>
            </>
          )}
          <span className="grow" />
          {!editing && (
            <button type="button" className="btn" disabled={busy} onClick={() => save(true)}>
              Save and add another
            </button>
          )}
          <button type="button" className="btn primary" disabled={busy} onClick={() => save(false)}>
            {busy ? "Saving…" : editing ? "Save changes" : "Add to closet"}
          </button>
        </>
      }
    >
      {editing && (
        <div className="stats">
          <HangTag small>{lastWornText(ws.last, d.today)}</HangTag>
          <span className="pill">
            {ws.count} {ws.count === 1 ? "wear" : "wears"}
          </span>
          {cpw !== null && <span className="pill">{formatCents(cpw)} per wear</span>}
          {inOutfits > 0 && (
            <span className="pill">
              In {inOutfits} {inOutfits === 1 ? "outfit" : "outfits"}
            </span>
          )}
          {item!.status !== "active" && (
            <span className="pill">{item!.status === "laundry" ? "In laundry" : "Retired"}</span>
          )}
        </div>
      )}

      {starters.length > 0 && (
        <fieldset className="field">
          <legend>Starters from your photos</legend>
          <div className="chips">
            {starters.map((st) => (
              <button
                key={st.name}
                type="button"
                className="chip"
                aria-pressed={form.name === st.name}
                onClick={() => applyStarter(st)}
              >
                {st.name}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      <div className="photo-pick">
        <div className="photo-box">
          {preview ? (
            <img src={preview} alt="New photo" />
          ) : item && (item.photo_path || swatch) ? (
            <PieceCell item={item} large />
          ) : (
            <span className="muted">No photo yet</span>
          )}
        </div>
        <div className="col">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            hidden
            data-testid="photo-input"
            onChange={(e) => {
              void pickPhoto(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <button type="button" className="btn sm" onClick={() => fileRef.current?.click()}>
            {preview || item?.photo_path ? "Change photo" : "Take or choose a photo"}
          </button>
          <p className="hint" aria-live="polite">
            {hint}
          </p>
        </div>
      </div>

      <label className="field">
        <span>Name</span>
        <input
          ref={nameRef}
          type="text"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="Navy oxford shirt"
          autoComplete="off"
          maxLength={80}
          required
        />
      </label>
      <div className="field-row">
        <label className="field">
          <span>Category</span>
          <select value={form.category} onChange={(e) => set("category", e.target.value as Category)}>
            {CATEGORIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Type</span>
          <input
            type="text"
            value={form.type}
            onChange={(e) => set("type", e.target.value)}
            placeholder="Oxford shirt"
            autoComplete="off"
            maxLength={60}
          />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Color</span>
          <span className="color-in">
            <span className="dot" style={swatch ? ({ "--sw": swatch } as React.CSSProperties) : undefined} />
            <input
              type="text"
              value={form.color_name}
              onChange={(e) => set("color_name", e.target.value)}
              placeholder="Navy"
              autoComplete="off"
              maxLength={40}
              list={`${uid}-colors`}
            />
          </span>
          <datalist id={`${uid}-colors`}>
            {Object.keys(NAMED)
              .filter((k) => k !== "gray")
              .map((k) => (
                <option key={k} value={k[0]!.toUpperCase() + k.slice(1)} />
              ))}
          </datalist>
        </label>
        <label className="field">
          <span>Pattern</span>
          <select value={form.pattern} onChange={(e) => set("pattern", e.target.value)}>
            <option value="">—</option>
            {["Solid", "Striped", "Checked", "Printed", "Textured"].map((p) => (
              <option key={p} value={p.toLowerCase()}>
                {p}
              </option>
            ))}
          </select>
        </label>
      </div>
      <fieldset className="field">
        <legend>Good for</legend>
        <Chips
          label="Good for"
          wrap
          options={OCCASIONS}
          value={form.occasions}
          onChange={(o) => set("occasions", toggle(form.occasions, o))}
        />
      </fieldset>
      <div className="field-row">
        <label className="field">
          <span>Formality</span>
          <select value={form.formality} onChange={(e) => set("formality", e.target.value)}>
            {FORMALITY.map((label, k) => (
              <option key={k} value={k ? String(k) : ""}>
                {label || "—"}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Warmth</span>
          <select value={form.warmth} onChange={(e) => set("warmth", e.target.value)}>
            <option value="">—</option>
            <option value="light">Light</option>
            <option value="medium">Medium</option>
            <option value="warm">Warm</option>
          </select>
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Price paid ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={form.price}
            onChange={(e) => set("price", e.target.value)}
            placeholder="0"
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Bought on</span>
          <input
            type="date"
            value={form.bought_on}
            max={d.today || undefined}
            onChange={(e) => set("bought_on", e.target.value)}
          />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          <span>Brand</span>
          <input
            type="text"
            value={form.brand}
            onChange={(e) => set("brand", e.target.value)}
            autoComplete="off"
            maxLength={60}
          />
        </label>
        <label className="field">
          <span>Size</span>
          <input
            type="text"
            value={form.size}
            onChange={(e) => set("size", e.target.value)}
            autoComplete="off"
            maxLength={20}
          />
        </label>
      </div>
      <label className="field">
        <span>Store</span>
        <input
          type="text"
          value={form.store}
          onChange={(e) => set("store", e.target.value)}
          autoComplete="off"
          maxLength={60}
        />
      </label>
      <label className="field">
        <span>Notes</span>
        <textarea rows={2} value={form.notes} onChange={(e) => set("notes", e.target.value)} maxLength={500} />
      </label>
      <p className="err" role="alert">
        {err}
      </p>
    </Sheet>
  );
}
