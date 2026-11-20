"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { EmptyState } from "@/components/EmptyState";
import { OccasionPicker } from "@/components/OccasionPicker";

const noSubscribe = () => () => {};
const todayLine = () => new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });

export function TodayView() {
  // Read on the client so the date is the phone's local day, not the server's.
  const dateLine = useSyncExternalStore(noSubscribe, todayLine, () => "");

  return (
    <div className="today">
      <section className="hero">
        <h1 className="sr">Today</h1>
        <p className="dateline">{dateLine || " "}</p>
        <OccasionPicker />
      </section>
      <div className="today-main">
        <EmptyState
          title="Your closet is empty"
          actions={
            <Link className="btn primary" href="/closet">
              Add clothes
            </Link>
          }
        >
          Add the pieces you wear most: go-to shirts, trousers and shoes. Outfit picks start once there’s something to
          pick from.
        </EmptyState>
      </div>
    </div>
  );
}
