"use client";

import { LOAD_ERROR, loadCloset, type ClosetState } from "@/lib/closet/store";

/** Shown until the closet has loaded; returns null once it's ready. */
export function LoadGate({ s }: { s: ClosetState }) {
  if (s.status === "ready") return null;
  if (s.status === "error")
    return (
      <section className="empty soft" role="alert">
        <h2>Couldn’t load your closet</h2>
        <p>{s.error ?? LOAD_ERROR}</p>
        <div className="row">
          <button type="button" className="btn" onClick={() => void loadCloset()}>
            Try again
          </button>
        </div>
      </section>
    );
  return (
    <p className="muted thinking" role="status">
      Loading your closet…
    </p>
  );
}
