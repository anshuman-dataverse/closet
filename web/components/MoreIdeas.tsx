"use client";

import { useState } from "react";
import { Flatlay } from "@/components/Piece";
import { useToast } from "@/components/Toast";
import { useWearActions } from "@/components/useWearActions";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { logSuggestionEvent, saveOutfit, type SuggestionAction, useCloset, useDerived } from "@/lib/closet/store";
import type { Item } from "@/lib/closet/types";
import { enqueueJob, waitForJob } from "@/lib/jobs";
import type { Occasion } from "@/lib/occasions";
import { supabase } from "@/lib/supabase/client";
import type { Weather } from "@/lib/weather";

type Idea = {
  event_id?: string;
  item_ids: string[];
  text: string;
  score: number;
  done?: SuggestionAction;
  savedId?: string;
};

const OFFLINE = "Your Mac is offline, so new ideas will appear when it’s back. Your saved outfits still rotate.";

/** Fresh combos from your closet (SPEC 4.1 More ideas, 5.4). Only ideas that pass every check are shown. */
export function MoreIdeas({ occasion, weather }: { occasion: Occasion; weather: Weather | null }) {
  const s = useCloset();
  const d = useDerived(s);
  const worker = useWorkerStatus();
  const toast = useToast();
  const { wear } = useWearActions();
  const [note, setNote] = useState("");
  const [state, setState] = useState<{ occ: Occasion; loading: boolean; ideas: Idea[] | null; msg: string }>({
    occ: occasion,
    loading: false,
    ideas: null,
    msg: "",
  });
  if (state.occ !== occasion) setState({ occ: occasion, loading: false, ideas: null, msg: "" }); // new occasion, fresh ideas

  const context = { date: d.today, note: note.trim(), weather };

  const ask = async () => {
    if (worker.offline) return setState((x) => ({ ...x, msg: OFFLINE }));
    setState((x) => ({ ...x, loading: true, msg: "" }));
    try {
      const db = supabase();
      const job = await enqueueJob(db, "suggest_outfits", { occasion, ...context }, 6);
      const done = await waitForJob(db, job.id, { timeoutMs: 30_000 });
      const res = (done?.result ?? null) as { ideas?: Idea[]; bar?: { message?: string | null } } | null;
      const ideas = (res?.ideas ?? []).filter((i) => i.item_ids.length >= 2);
      const bar = res?.bar?.message;
      setState((x) =>
        x.occ !== occasion
          ? x
          : {
              ...x,
              loading: false,
              ideas,
              msg: !done
                ? "Your Mac is taking a while. Try again in a moment."
                : done.status === "failed"
                  ? "Your Mac couldn’t put ideas together. Try again."
                  : ideas.length
                    ? ""
                    : bar
                      ? `${bar} Check What’s missing in Shop for the piece that would fix it.`
                      : "Not enough pieces for this occasion yet. Add a top, a bottom and shoes you’d wear for it.",
            },
      );
    } catch {
      setState((x) => ({ ...x, loading: false, msg: "Couldn’t ask your Mac. Check your connection and try again." }));
    }
  };

  const mark = (k: number, patch: Partial<Idea>) =>
    setState((x) => ({ ...x, ideas: x.ideas?.map((i, j) => (j === k ? { ...i, ...patch } : i)) ?? null }));

  const event = (idea: Idea, action: SuggestionAction) =>
    logSuggestionEvent({
      occasion,
      itemIds: idea.item_ids,
      action,
      score: idea.score,
      modelVersion: "rules-v1",
      context: { ...context, shown_event: idea.event_id ?? null },
    });

  const act = async (k: number, idea: Idea, action: SuggestionAction) => {
    try {
      if (action === "saved" || action === "worn") {
        const id =
          idea.savedId ??
          (await saveOutfit({
            id: null,
            name: "",
            occasions: [occasion],
            itemIds: idea.item_ids,
            source: "suggested",
          }));
        mark(k, { savedId: id });
        if (action === "worn") await wear({ id, itemIds: idea.item_ids }, occasion, d.today);
        else toast("Outfit saved");
      }
      await event(idea, action);
      mark(k, { done: action });
    } catch (e) {
      toast((e as Error).message);
    }
  };

  const shown = (state.ideas ?? []).map((i, k) => ({ i, k })).filter(({ i }) => i.done !== "skipped");
  const pieces = (ids: string[]) => ids.map((id) => d.byId.get(id)).filter((x): x is Item => !!x);

  return (
    <section className="block" aria-labelledby="ideas-h">
      <div className="block-head">
        <h2 id="ideas-h">More ideas</h2>
      </div>
      <label className="field">
        <span>Anything special today?</span>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Client meeting at 2"
          autoComplete="off"
          maxLength={200}
        />
      </label>
      <div className="row">
        <button type="button" className="btn" onClick={ask} disabled={state.loading}>
          {state.ideas ? "Try again" : "Get ideas"}
        </button>
      </div>
      {state.loading && (
        <p className="muted thinking" role="status">
          Your Mac is putting outfits together from your closet…
        </p>
      )}
      {state.msg && (
        <p className="muted" role="status">
          {state.msg}
        </p>
      )}
      {shown.length > 0 && (
        <div className="combo-list">
          {shown.map(({ i, k }) => {
            const ps = pieces(i.item_ids);
            const title = ps
              .slice(0, 2)
              .map((p) => p.name)
              .join(" + ");
            return (
              <article key={i.event_id ?? k} className="combo" aria-label={title}>
                <Flatlay pieces={ps} />
                <div>
                  <h3>{title}</h3>
                  <p>{i.text}</p>
                  <div className="row">
                    <button
                      type="button"
                      className="btn primary sm"
                      disabled={i.done === "worn"}
                      onClick={() => void act(k, i, "worn")}
                    >
                      {i.done === "worn" ? "Wearing" : "Wear today"}
                    </button>
                    <button
                      type="button"
                      className="btn sm"
                      disabled={!!i.savedId}
                      onClick={() => void act(k, i, "saved")}
                    >
                      {i.savedId ? "Saved" : "Save outfit"}
                    </button>
                    <button type="button" className="btn sm ghost" onClick={() => void act(k, i, "skipped")}>
                      Not today
                    </button>
                    <button
                      type="button"
                      className="chip"
                      aria-label="Good idea"
                      aria-pressed={i.done === "liked"}
                      onClick={() => void act(k, i, "liked")}
                    >
                      👍
                    </button>
                    <button
                      type="button"
                      className="chip"
                      aria-label="Not for me"
                      aria-pressed={i.done === "disliked"}
                      onClick={() => void act(k, i, "disliked")}
                    >
                      👎
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
