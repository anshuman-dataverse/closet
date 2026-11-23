"use client";
/* eslint-disable @next/next/no-img-element -- signed private URLs and store images */

import { useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { ItemSheet, type Prefill } from "@/components/ItemSheet";
import { LoadGate } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { checkWish, setWishStatus, useCloset, useDerived } from "@/lib/closet/store";
import type { Wish } from "@/lib/closet/types";
import { priceDrop } from "@/lib/domain/hunts";
import { centsToInput, formatCents } from "@/lib/domain/money";
import { overlapNote, similarTo } from "@/lib/domain/similar";
import { useSignedUrl } from "@/lib/signed-urls";
import { seenAgo } from "@/lib/worker-status";
import { WishSheet } from "./WishSheet";

const VERDICT = {
  buy: { word: "Worth it", cls: "good" },
  wait: { word: "Wait on it", cls: "wait" },
  skip: { word: "Skip it", cls: "bad" },
} as const;

type Check = { verdict: keyof typeof VERDICT; reasons: string[]; duplicates?: { name: string }[] };

const thumbOf = (p: string | null) => (p ? p.replace(/\.jpg$/, "_thumb.jpg") : null);

function WishImage({ w }: { w: Wish }) {
  const url = useSignedUrl(thumbOf(w.photo_path));
  const src = w.photo_path ? url : w.image_url;
  return src ? <img className="wish-img" src={src} alt="" /> : null;
}

function WishCard({ w, onBought }: { w: Wish; onBought: (w: Wish) => void }) {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const worker = useWorkerStatus();
  const [checking, setChecking] = useState("");
  const check = w.check_result as Check | null;
  const v = check && VERDICT[check.verdict] ? VERDICT[check.verdict] : null;
  const local = check?.duplicates?.length ? check.duplicates : similarTo(w, s.items);
  const note = overlapNote(local);
  const drop = priceDrop(w);

  const ask = async () => {
    if (worker.offline) {
      setChecking("Your Mac is offline. This will run when it’s back.");
      void checkWish(w.id, d.today, 0).catch(() => {});
      return;
    }
    setChecking("Your Mac is weighing it up…");
    try {
      const job = await checkWish(w.id, d.today);
      setChecking(
        job
          ? job.status === "failed"
            ? "Your Mac couldn’t check this one. Try again."
            : ""
          : "Still checking. The verdict will appear here.",
      );
    } catch {
      setChecking("Couldn’t ask your Mac. Check your connection and try again.");
    }
  };

  const remove = async () => {
    try {
      await setWishStatus(w.id, "removed");
      toast("Removed from your wishlist", { action: "Undo", onAction: () => void setWishStatus(w.id, "wanted") });
    } catch (e) {
      toast((e as Error).message);
    }
  };

  return (
    <li className="card" aria-label={w.name}>
      <div className="wish-top">
        <WishImage w={w} />
        <div>
          <h3>{w.name}</h3>
          <p className="price">
            {w.price_cents != null ? formatCents(w.price_cents) : "No price yet"}
            {w.store && <span className="muted"> · {w.store}</span>}
          </p>
          {w.url && (
            <a className="link" href={w.url} target="_blank" rel="noopener noreferrer">
              Open listing
            </a>
          )}
        </div>
      </div>
      {drop && (
        <p className="drop" data-testid="price-drop">
          Price dropped to {formatCents(drop.to)}
          {drop.from != null && <> from {formatCents(drop.from)}</>}
          {w.last_price_check_at && <span className="muted"> · checked {seenAgo(w.last_price_check_at)}</span>}
        </p>
      )}
      {note && <p className="overlap">{note}</p>}
      {v && check && (
        <div className={`verdict ${v.cls}`}>
          <p>
            <span className="v-word">{v.word}</span>
          </p>
          <ul>
            {check.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
      {checking && (
        <p className="muted small thinking" role="status">
          {checking}
        </p>
      )}
      <div className="row">
        <button type="button" className="btn sm" onClick={ask}>
          {check ? "Check again" : "Do I need this?"}
        </button>
        <button type="button" className="btn sm primary" onClick={() => onBought(w)}>
          I bought it
        </button>
        <button type="button" className="btn sm ghost" onClick={remove}>
          Remove
        </button>
      </div>
    </li>
  );
}

export function WishlistPanel() {
  const s = useCloset();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [bought, setBought] = useState<Wish | null>(null);
  const list = s.wishes.filter((w) => w.status === "wanted");

  const prefill: Prefill | undefined = bought
    ? {
        form: {
          name: bought.name,
          ...(bought.category ? { category: bought.category } : {}),
          color_name: bought.color_name ?? "",
          occasions: bought.occasion ? [bought.occasion] : [],
          price: centsToInput(bought.price_cents),
          store: bought.store ?? "",
          notes: bought.notes ?? "",
        },
        photo: bought.photo_path
          ? { photo_path: bought.photo_path, thumb_path: thumbOf(bought.photo_path) }
          : undefined,
      }
    : undefined;

  return (
    <>
      <div className="panel-head">
        <p className="muted">
          Things you’re thinking of buying. Check each against what you already own before you spend.
        </p>
        <button type="button" className="btn primary" onClick={() => setAdding(true)} disabled={s.status !== "ready"}>
          Add to wishlist
        </button>
      </div>
      {s.status !== "ready" ? (
        <LoadGate s={s} />
      ) : list.length ? (
        <ul className="cards" aria-label="Your wishlist">
          {list.map((w) => (
            <WishCard key={w.id} w={w} onBought={setBought} />
          ))}
        </ul>
      ) : (
        <EmptyState title="Your wishlist is empty">
          Add something you’ve seen online or in a store, with the price and link. “Do I need this?” then tells you
          whether it earns a place in your closet.
        </EmptyState>
      )}
      <WishSheet open={adding} onClose={() => setAdding(false)} />
      <ItemSheet
        open={!!bought}
        itemId={null}
        prefill={prefill}
        onClose={() => setBought(null)}
        onSaved={() => {
          const w = bought;
          if (w)
            void setWishStatus(w.id, "bought").then(
              () => toast("Moved to your closet"),
              () => {},
            );
        }}
      />
    </>
  );
}
