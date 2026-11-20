"use client";
/* eslint-disable @next/next/no-img-element -- local blob preview */

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Chips, toggle } from "@/components/Chips";
import { ConfirmButton } from "@/components/ConfirmButton";
import { HangTag } from "@/components/HangTag";
import { PieceCell } from "@/components/Piece";
import { Sheet } from "@/components/Sheet";
import { SuggestionBox } from "@/components/SuggestionBox";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import {
  deleteItem,
  type ItemInput,
  requestTagging,
  saveItem,
  setItemsStatus,
  useCloset,
  useDerived,
} from "@/lib/closet/store";
import { CATEGORIES, type Category, type Item } from "@/lib/closet/types";
import { NAMED, safeHex, swatchFor } from "@/lib/domain/colors";
import { isYmd, lastWornText } from "@/lib/domain/dates";
import { centsToInput, formatCents, parseDollars } from "@/lib/domain/money";
import { STARTERS, type Starter } from "@/lib/domain/starters";
import {
  mergeSuggestions,
  OFFLINE_MESSAGE,
  parseSuggestion,
  type SuggestableKey,
  statusMessage,
  touchedFromValues,
} from "@/lib/domain/suggestions";
import { costPerWear, NO_WEAR } from "@/lib/domain/wear";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { preparePhoto, removePaths, uploadItemPhoto } from "@/lib/photos";
import { supabase } from "@/lib/supabase/client";

const FORMALITY = ["", "1 · Lounge", "2 · Casual", "3 · Smart casual", "4 · Business", "5 · Formal"];
const READING = "Reading your photo…";

export type Form = {
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

export const fromItem = (i: Item): Form => ({
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

/** Everything the sheet edits, kept together so async suggestion merges see the latest touches. */
type Draft = {
  mode: "add" | "edit";
  id: string;
  form: Form;
  touched: SuggestableKey[];
  saved: "none" | "draft" | "done"; // add mode: is there a draft row, and has it been saved for real?
  merged: boolean; // suggestions were reviewed in the form
  sugHex: { name: string; hex: string } | null;
  cutout: { photo: string; path: string } | null; // cutout made for a new, unsaved photo
};

const fresh = (item: Item | null): Draft => ({
  mode: item ? "edit" : "add",
  id: item ? item.id : crypto.randomUUID(),
  form: item ? fromItem(item) : blank(),
  touched: [],
  saved: "none",
  merged: false,
  sugHex: null,
  cutout: null,
});

export function ItemSheet({ open, itemId, onClose }: { open: boolean; itemId: string | null; onClose: () => void }) {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const worker = useWorkerStatus();
  const item = itemId ? (d.byId.get(itemId) ?? null) : null;
  const editing = !!item;

  const [dr, setDr] = useState<Draft>(() => fresh(null));
  const form = dr.form;
  const [upload, setUpload] = useState<Upload | null>(null);
  const [hint, setHint] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [view, setView] = useState<"photo" | "cutout">("cutout");
  const fileRef = useRef<HTMLInputElement>(null);
  const nameRef = useRef<HTMLInputElement>(null);
  const session = useRef(0);
  const uid = useId();

  // Reset whenever the sheet opens for a different piece.
  const [openedFor, setOpenedFor] = useState<string | null | undefined>(undefined);
  const key = open ? (itemId ?? "new") : undefined;
  if (key !== openedFor) {
    setOpenedFor(key);
    if (open) {
      setDr(fresh(item));
      setUpload(null);
      setHint("");
      setErr("");
      setBusy(false);
      setReading(false);
      setView("cutout");
    }
  }
  useEffect(() => {
    session.current += 1; // async work from an earlier opening must not touch this one
  }, [key]);

  // Closing without saving: drop the draft row (add) or the unsaved replacement photo (edit).
  useEffect(() => {
    if (open) return;
    if (dr.mode === "add" && dr.saved === "draft") void deleteItem(dr.id).catch(() => {});
    if (dr.mode === "edit" && upload)
      void upload.promise.then((p) => removePaths(supabase(), [p.photo_path, p.thumb_path])).catch(() => {});
  }, [open, dr.mode, dr.saved, dr.id, upload]);

  const set = <K extends keyof Form>(k: K, v: Form[K]) =>
    setDr((x) => ({
      ...x,
      form: { ...x.form, [k]: v },
      touched: x.touched.includes(k as SuggestableKey) ? x.touched : [...x.touched, k as SuggestableKey],
    }));

  const owned = useMemo(() => new Set(s.items.map((i) => i.name.trim().toLowerCase())), [s.items]);
  const starters = editing ? [] : STARTERS.filter((x) => !owned.has(x.name.toLowerCase()));

  const applyStarter = (st: Starter) => {
    setDr((x) => ({
      ...x,
      form: {
        ...x.form,
        name: st.name,
        category: st.category,
        type: st.type,
        color_name: st.color_name,
        occasions: [...st.occasions],
      },
      touched: [...new Set<SuggestableKey>([...x.touched, "name", "category", "type", "color_name", "occasions"])],
    }));
    setErr("");
  };

  /** Queue tagging and merge the result into untouched fields (SPEC 4.2 steps 3–6). */
  const readPhoto = async (pieceId: string, photoPath: string | undefined, mine: number) => {
    if (worker.offline) {
      setHint(OFFLINE_MESSAGE);
      void requestTagging(pieceId, photoPath, 0).catch(() => {});
      return;
    }
    setReading(true);
    setHint(READING);
    try {
      const job = await requestTagging(pieceId, photoPath);
      if (session.current !== mine) return;
      if (!job) return setHint("Still reading. The details will show on this piece when your Mac finishes.");
      if (job.status === "failed") return setHint("Your Mac couldn’t read this photo. Fill in the details yourself.");
      const result = (job.result ?? {}) as { suggestions?: unknown; cutout_path?: string | null; photo_path?: string };
      const sug = parseSuggestion(result.suggestions);
      if (!sug) return setHint("");
      setDr((x) => {
        const touched = new Set<SuggestableKey>(
          x.mode === "edit" ? [...touchedFromValues(x.form), ...x.touched] : x.touched,
        );
        const { form: merged, filled } = mergeSuggestions(x.form, touched, sug);
        return {
          ...x,
          form: merged,
          merged: true,
          sugHex:
            filled.includes("color_name") && sug.color_hex ? { name: sug.color_name, hex: sug.color_hex } : x.sugHex,
          cutout: photoPath && result.cutout_path ? { photo: photoPath, path: result.cutout_path } : x.cutout,
        };
      });
      setHint(statusMessage(sug.status));
    } catch {
      if (session.current === mine) setHint("");
    } finally {
      if (session.current === mine) setReading(false);
    }
  };

  const pickPhoto = async (file: File | undefined) => {
    if (!file || !s.userId) return;
    const mine = session.current;
    const uidNow = s.userId;
    setHint("Preparing the photo…");
    setErr("");
    try {
      const prepared = await preparePhoto(file);
      const promise = uploadItemPhoto(supabase(), uidNow, dr.id, prepared);
      setUpload({ previewUrl: prepared.previewUrl, promise });
      setHint("Uploading…");
      const paths = await promise;
      if (session.current !== mine) {
        void removePaths(supabase(), [paths.photo_path, paths.thumb_path]);
        return;
      }
      if (dr.mode === "add") {
        // Save a draft row right away so the Mac has a piece to write to. Cancel deletes it.
        const old = s.items.find((i) => i.id === dr.id);
        await saveItem(
          {
            id: dr.id,
            name: dr.form.name.trim() || "New piece",
            category: dr.form.category,
            occasions: dr.form.occasions,
            ...paths,
            cutout_path: null,
          },
          old ? [old.photo_path, old.thumb_path, old.cutout_path] : [],
        );
        setDr((x) => ({ ...x, saved: x.saved === "none" ? "draft" : x.saved }));
        await readPhoto(dr.id, undefined, mine);
      } else {
        await readPhoto(dr.id, paths.photo_path, mine);
      }
    } catch (e) {
      setUpload(null);
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
      const keepHex = safeHex(item?.color_hex) && form.color_name === (item?.color_name ?? "") ? item!.color_hex : null;
      const colorHex = dr.sugHex && form.color_name === dr.sugHex.name ? dr.sugHex.hex : keepHex;
      const newPhotoCutout = photo && dr.cutout?.photo === photo.photo_path ? dr.cutout.path : null;
      const input: ItemInput & { id: string } = {
        id: dr.id,
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
        ...(dr.mode === "edit" && photo ? { ...photo, cutout_path: newPhotoCutout } : {}),
        ...(dr.merged ? { suggestions: null } : {}),
      };
      const replaced = dr.mode === "edit" && photo && item ? [item.photo_path, item.thumb_path, item.cutout_path] : [];
      await saveItem(input, replaced);
      setUpload(null);
      if (again) {
        toast("Added to your closet");
        session.current += 1;
        setDr((x) => ({ ...fresh(null), form: blank(x.form.occasions) }));
        setHint("");
        setReading(false);
        nameRef.current?.focus();
      } else {
        setDr((x) => ({ ...x, saved: "done" }));
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
  const draftRow = !editing ? s.items.find((i) => i.id === dr.id) : undefined;

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

      {editing && item!.suggestions && item!.tags_status !== "pending" && !dr.merged && (
        <SuggestionBox
          item={item!}
          form={form}
          onApplied={(f) => setDr((x) => ({ ...x, form: { ...x.form, ...f } }))}
        />
      )}

      <div className="photo-pick">
        <div className="photo-box">
          {preview ? (
            <img src={preview} alt="New photo" />
          ) : item && (item.photo_path || swatch) ? (
            <PieceCell item={item} large prefer={view} />
          ) : draftRow?.cutout_path ? (
            <PieceCell item={draftRow} large />
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
          <button type="button" className="btn sm" onClick={() => fileRef.current?.click()} disabled={reading}>
            {preview || item?.photo_path ? "Change photo" : "Take or choose a photo"}
          </button>
          {editing && item!.photo_path && !preview && (
            <button
              type="button"
              className="btn sm"
              disabled={reading}
              onClick={() => void readPhoto(item!.id, undefined, session.current)}
            >
              Fill in from photo
            </button>
          )}
          {editing && item!.cutout_path && !preview && (
            <Chips
              label="Show"
              options={[
                { id: "cutout" as const, label: "Cutout" },
                { id: "photo" as const, label: "Photo" },
              ]}
              value={view}
              onChange={setView}
            />
          )}
          <p className={`hint${reading ? " thinking" : ""}`} aria-live="polite" data-testid="photo-hint">
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
