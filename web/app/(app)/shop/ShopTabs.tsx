"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useRef } from "react";
import { EmptyState } from "@/components/EmptyState";

const TABS = [
  { id: "wishlist", label: "Wishlist" },
  { id: "hunts", label: "Deal hunts" },
  { id: "missing", label: "What’s missing" },
] as const;
type Tab = (typeof TABS)[number]["id"];

export function ShopTabs() {
  const params = useSearchParams();
  const router = useRouter();
  const path = usePathname();
  const raw = params.get("tab");
  const tab: Tab = TABS.some((t) => t.id === raw) ? (raw as Tab) : "wishlist";
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const go = (t: Tab, focus = false) => {
    router.replace(`${path}?tab=${t}`, { scroll: false });
    if (focus) refs.current[t]?.focus();
  };

  return (
    <>
      <div
        className="seg"
        role="tablist"
        aria-label="Shopping"
        onKeyDown={(e) => {
          const i = TABS.findIndex((t) => t.id === tab);
          const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (d) {
            e.preventDefault();
            go(TABS[(i + d + TABS.length) % TABS.length]?.id ?? "wishlist", true);
          }
        }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[t.id] = el;
            }}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls="shop-panel"
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => go(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div id="shop-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "wishlist" && (
          <EmptyState title="Your wishlist is empty">
            Add something you’ve seen online or in a store, with the price and link. “Do I need this?” then tells you
            whether it earns a place in your closet.
          </EmptyState>
        )}
        {tab === "hunts" && (
          <EmptyState title="No hunts yet">
            Try something like “white oxford shirt for the office, $25 to $60”.
          </EmptyState>
        )}
        {tab === "missing" && (
          <EmptyState title="Nothing to compare yet">
            Once your closet has a few pieces, this finds the gaps worth filling for each occasion.
          </EmptyState>
        )}
      </div>
    </>
  );
}
