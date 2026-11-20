"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ICONS } from "@/components/Icons";
import { Sheet } from "@/components/Sheet";
import { KIND_LABEL, useWorkerStatus } from "@/components/WorkerStatus";
import type { JobKind } from "@/lib/jobs";
import { seenAgo } from "@/lib/worker-status";

const TABS = [
  { href: "/today", label: "Today", icon: ICONS.today },
  { href: "/closet", label: "Closet", icon: ICONS.closet },
  { href: "/outfits", label: "Outfits", icon: ICONS.outfits },
  { href: "/shop", label: "Shop", icon: ICONS.shop },
  { href: "/spend", label: "Spend", icon: ICONS.spend },
] as const;

const current = (path: string, href: string) => (path === href || path.startsWith(`${href}/`) ? "page" : undefined);

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const status = useWorkerStatus();
  const [why, setWhy] = useState(false);

  return (
    <>
      <header className="top">
        <div className="top-in">
          <Link className="mark" href="/today" aria-label="Closet, today">
            closet
          </Link>
          <nav className="tabs-wide" aria-label="Sections">
            {TABS.map((t) => (
              <Link key={t.href} href={t.href} aria-current={current(path, t.href)}>
                {t.label}
              </Link>
            ))}
          </nav>
          {status.loaded && status.offline && (
            <button type="button" className="offline-pill" onClick={() => setWhy(true)}>
              Mac offline
            </button>
          )}
          <Link
            className="me-btn"
            href="/profile"
            aria-label="Style profile"
            title="Style profile"
            aria-current={current(path, "/profile")}
          >
            {ICONS.profile}
          </Link>
        </div>
      </header>

      <main id="view" className="wrap" tabIndex={-1}>
        {children}
      </main>

      <nav className="tabbar" aria-label="Sections">
        {TABS.map((t) => (
          <Link key={t.href} href={t.href} aria-current={current(path, t.href)}>
            {t.icon}
            <span>{t.label}</span>
          </Link>
        ))}
      </nav>

      <Sheet open={why} onClose={() => setWhy(false)} title="Your Mac is offline">
        <p>
          {status.lastSeenAt
            ? `Last seen ${seenAgo(status.lastSeenAt)}. Anything that needs it will run when it’s back.`
            : "Your Mac hasn’t checked in yet. Start the worker on your Mac to turn on photo reading, ideas and deal hunts."}
        </p>
        <h3>Waiting for your Mac</h3>
        {status.queued.length ? (
          <ul className="piece-list">
            {status.queued.map((q) => (
              <li key={q.kind}>
                {KIND_LABEL[q.kind as JobKind] ?? q.kind}
                {q.count > 1 ? ` (${q.count})` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing is waiting.</p>
        )}
        <h3>Still works</h3>
        <p className="muted">
          Your closet, outfits, wear log, Today’s rotation, spend, wishlist and weather all work without your Mac.
        </p>
      </Sheet>
    </>
  );
}
