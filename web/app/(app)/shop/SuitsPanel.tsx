"use client";
/* eslint-disable @next/next/no-img-element -- local previews, signed private URLs and store images */

import { useEffect, useRef, useState } from "react";
import { Chips } from "@/components/Chips";
import { RatingBox } from "@/components/RatingBox";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import {
  deleteWish,
  setWishStatus,
  startSuitsCheck,
  SUITS_PLACEHOLDER,
  useCloset,
  useDerived,
} from "@/lib/closet/store";
import type { Wish } from "@/lib/closet/types";
import { formatCents } from "@/lib/domain/money";
import { readLine, suitsOf } from "@/lib/domain/suits";
import { normalizeUrl } from "@/lib/domain/url";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { preparePhoto, removePaths, uploadPhotoTo } from "@/lib/photos";
import { useSignedUrl } from "@/lib/signed-urls";
import { supabase } from "@/lib/supabase/client";

const thumbOf = (p: string | null) => (p ? p.replace(/\.jpg$/, "_thumb.jpg") : null);

function CheckImage({ w }: { w: Wish }) {
  const url = useSignedUrl(thumbOf(w.photo_path));
  const src = w.photo_path ? url : w.image_url;
  return src ? <img className="wish-img" src={src} alt="" /> : null;
}

/** The answer for one check: verdict, every reason, what was read, and what to do next. */
function Answer({ w, onDone }: { w: Wish; onDone?: () => void }) {
  const toast = useToast();
  const s = suitsOf(w.check_result);
  if (!s) return null;
  const add = async () => {
    try {
      await setWishStatus(w.id, "wanted");
      toast("Added to your wishlist");
      onDone?.();
    } catch (e) {
      toast((e as Error).message);
    }
  };
  const drop = async () => {
    try {
      await deleteWish(w.id);
      onDone?.();
    } catch (e) {
      toast((e as Error).message);
    }
  };
  return (
    <>
      <RatingBox r={s} label="Would it suit me" />
      {s.read && <p className="muted small">{readLine(s.read)}</p>}
      <div className="row">
        <button type="button" className="btn sm primary" onClick={() => void add()}>
          Add to wishlist
        </button>
        <button type="button" className="btn sm" onClick={() => void drop()}>
          Not for me
        </button>
      </div>
    </>
  );
}

type Picked = { preview: string; promise: Promise<{ photo_path: string; thumb_path: string }> };

export function SuitsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const s = useCloset();
  const d = useDerived(s);
  const worker = useWorkerStatus();
  const [id, setId] = useState("");
  const [link, setLink] = useState("");
  const [occasion, setOccasion] = useState<Occasion | "">("");
  const [photo, setPhoto] = useState<Picked | null>(null);
  const [status, setStatus] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [asked, setAsked] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const [openedFor, setOpenedFor] = useState(false);
  if (open !== openedFor) {
    setOpenedFor(open);
    if (open) {
      setId(crypto.randomUUID());
      setLink("");
      setOccasion("");
      setPhoto(null);
      setStatus("");
      setErr("");
      setBusy(false);
      setAsked(false);
    }
  }
  // Closing before a check was started drops an uploaded screenshot.
  useEffect(() => {
    if (open || !photo || asked) return;
    void photo.promise.then((p) => removePaths(supabase(), [p.photo_path, p.thumb_path])).catch(() => {});
  }, [open, photo, asked]);

  const w = s.wishes.find((x) => x.id === id);
  const answer = w ? suitsOf(w.check_result) : null;

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

  const go = async () => {
    const url = link.trim() ? normalizeUrl(link) : null;
    if (link.trim() && !url) return setErr("That link doesn’t look right. Paste the full web address.");
    if (!url && !photo) return setErr("Paste a product link or add a screenshot of the piece.");
    setBusy(true);
    setErr("");
    setAsked(true);
    setStatus(worker.offline ? "Your Mac is offline. The check will run when it’s back." : "Your Mac is checking it…");
    try {
      const up = photo ? await photo.promise : null;
      const job = await startSuitsCheck(
        { id, url, photo_path: up?.photo_path ?? null, occasion: occasion || null },
        d.today,
        worker.offline ? 0 : 60_000,
      );
      if (worker.offline) return;
      if (!job) setStatus("Still working. The answer will show under Recent checks.");
      else if (job.status === "failed") {
        setStatus("");
        setErr(job.error || "Your Mac couldn’t check this one. Try a screenshot instead.");
      } else setStatus("");
    } catch (e) {
      setStatus("");
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Would it suit me?"
      actions={
        answer ? undefined : (
          <button type="button" className="btn primary" onClick={() => void go()} disabled={busy}>
            {busy ? "Checking…" : "Check it"}
          </button>
        )
      }
    >
      {answer && w ? (
        <Answer w={w} onDone={onClose} />
      ) : (
        <>
          <label className="field">
            <span>Product link</span>
            <input
              type="url"
              inputMode="url"
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://"
              autoComplete="off"
            />
          </label>
          <div className="photo-pick">
            <div className="photo-box">
              {photo ? (
                <img src={photo.preview} alt="Screenshot to check" />
              ) : (
                <span className="muted">No picture</span>
              )}
            </div>
            <div className="col">
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                hidden
                data-testid="suits-photo-input"
                onChange={(e) => {
                  void pick(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <input
                ref={cameraRef}
                type="file"
                accept="image/*"
                capture="environment"
                hidden
                onChange={(e) => {
                  void pick(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              <div className="row">
                <button type="button" className="btn sm" onClick={() => fileRef.current?.click()}>
                  {photo ? "Change screenshot" : "Choose screenshot"}
                </button>
                <button type="button" className="btn sm" onClick={() => cameraRef.current?.click()}>
                  Take photo
                </button>
              </div>
              <p className="hint">A link works for most stores. If a store blocks apps, use a screenshot.</p>
            </div>
          </div>
          <fieldset className="field">
            <legend>For (optional)</legend>
            <Chips
              label="Occasion"
              wrap
              options={OCCASIONS}
              value={occasion}
              onChange={(o) => setOccasion(occasion === o ? "" : o)}
            />
          </fieldset>
          <p className="hint">
            Your Mac checks the color against your palette, the formality, how many outfits it makes with what you own,
            whether you already have something like it, and the fit the store states. It can’t show it on you.
          </p>
        </>
      )}
      {status && (
        <p className="small thinking" role="status">
          {status}
        </p>
      )}
      {err && (
        <p className="err" role="alert">
          {err}
        </p>
      )}
    </Sheet>
  );
}

/** Checks you haven't decided on yet (status 'considering'). */
export function RecentChecks() {
  const s = useCloset();
  const toast = useToast();
  const list = s.wishes.filter((w) => w.status === "considering");
  if (!list.length) return null;
  return (
    <section aria-label="Recent checks">
      <h3 className="muted small">Recent checks</h3>
      <ul className="cards">
        {list.map((w) => (
          <li key={w.id} className="card" aria-label={`Check: ${w.name}`}>
            <div className="wish-top">
              <CheckImage w={w} />
              <div>
                <h3>{w.name === SUITS_PLACEHOLDER ? "Piece to check" : w.name}</h3>
                {(w.store || w.price_cents != null) && (
                  <p className="price">
                    {w.price_cents != null && formatCents(w.price_cents)}
                    {w.store && <span className="muted"> · {w.store}</span>}
                  </p>
                )}
                {w.url && (
                  <a className="link" href={w.url} target="_blank" rel="noopener noreferrer">
                    Open listing
                  </a>
                )}
              </div>
            </div>
            {suitsOf(w.check_result) ? (
              <Answer w={w} />
            ) : (
              <>
                <p className="small muted" role="status">
                  No answer yet. If your Mac was offline it will run when it’s back; if it failed, delete it and try a
                  screenshot.
                </p>
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => void deleteWish(w.id).catch((e: Error) => toast(e.message))}
                >
                  Delete
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
