"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Chips } from "@/components/Chips";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { saveWish, useCloset, useDerived } from "@/lib/closet/store";
import type { Category } from "@/lib/closet/types";
import { budgetRange } from "@/lib/domain/money";
import { enqueueJob, waitForJob } from "@/lib/jobs";
import { type Occasion, OCCASIONS } from "@/lib/occasions";
import { useOccasion } from "@/lib/use-occasion";
import { supabase } from "@/lib/supabase/client";

type Gap = {
  name: string;
  category: Category;
  color_name: string;
  price_min_cents: number;
  price_max_cents: number;
  unlocks: number;
  reason: string;
};

/** What's missing (SPEC 4.4, 5.7). */
export function GapsPanel() {
  const s = useCloset();
  const d = useDerived(s);
  const toast = useToast();
  const worker = useWorkerStatus();
  const router = useRouter();
  const hunt = (g: Gap) => {
    const q = new URLSearchParams({
      tab: "hunts",
      new: "hunt",
      what: g.name,
      occ: res?.occ ?? occ,
      min: String(g.price_min_cents),
      max: String(g.price_max_cents),
    });
    router.push(`/shop?${q}`, { scroll: false });
  };
  const [today] = useOccasion();
  const [occ, setOcc] = useState<Occasion>(today);
  const [res, setRes] = useState<{ occ: Occasion; ideas: Gap[] } | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [added, setAdded] = useState<string[]>([]);

  const find = async () => {
    if (worker.offline) return setMsg("Your Mac is offline. This will run when it’s back.");
    setBusy(true);
    setMsg("");
    try {
      const db = supabase();
      const job = await enqueueJob(db, "find_gaps", { occasion: occ, date: d.today }, 3);
      const done = await waitForJob(db, job.id, { timeoutMs: 60_000 });
      const ideas = ((done?.result as { ideas?: Gap[] } | null)?.ideas ?? []).slice(0, 5);
      setRes({ occ, ideas });
      if (!done) setMsg("Your Mac is taking a while. Try again in a moment.");
      else if (done.status === "failed") setMsg("Your Mac couldn’t work this out. Try again.");
      else if (!ideas.length) setMsg("Nothing obvious is missing for this occasion. Nice.");
    } catch {
      setMsg("Couldn’t ask your Mac. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  const add = async (g: Gap) => {
    try {
      await saveWish({
        id: crypto.randomUUID(),
        name: g.name,
        category: g.category,
        color_name: g.color_name,
        occasion: res?.occ ?? occ,
        notes: g.reason,
      });
      setAdded((x) => [...x, g.name]);
      toast("Added to your wishlist");
    } catch (e) {
      toast((e as Error).message);
    }
  };

  return (
    <>
      <div className="panel-head">
        <p className="muted">Pick an occasion. Your Mac looks for the staple that would add the most new outfits.</p>
      </div>
      <Chips label="Occasion" options={OCCASIONS} value={occ} onChange={setOcc} />
      <div className="row">
        <button type="button" className="btn primary" onClick={find} disabled={busy || s.status !== "ready"}>
          Find what’s missing
        </button>
      </div>
      {busy && (
        <p className="muted thinking" role="status">
          Your Mac is looking for gaps in your closet…
        </p>
      )}
      {msg && (
        <p className="muted" role="status">
          {msg}
        </p>
      )}
      {res && res.ideas.length > 0 && (
        <ul className="cards" aria-label="Ideas">
          {res.ideas.map((g) => (
            <li key={g.name} className="card">
              <h3>{g.name}</h3>
              <p className="price">{budgetRange(g.price_min_cents, g.price_max_cents)}</p>
              <p className="muted">{g.reason}</p>
              <div className="row">
                <button type="button" className="btn sm" onClick={() => hunt(g)}>
                  Start a hunt
                </button>
                <button
                  type="button"
                  className="btn sm primary"
                  disabled={added.includes(g.name)}
                  onClick={() => void add(g)}
                >
                  {added.includes(g.name) ? "On your wishlist" : "Add to wishlist"}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
