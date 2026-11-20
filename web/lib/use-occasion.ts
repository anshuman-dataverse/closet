"use client";

import { useCallback, useSyncExternalStore } from "react";
import { isOccasion, type Occasion } from "@/lib/occasions";

// The last occasion picked on Today, remembered on this device (SPEC 4.1).
const KEY = "closet.occ";
const EVENT = "closet:occ";
const DEFAULT: Occasion = "office";

function read(): Occasion {
  try {
    const v = localStorage.getItem(KEY);
    return isOccasion(v) ? v : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

function subscribe(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function useOccasion(): [Occasion, (o: Occasion) => void] {
  const occ = useSyncExternalStore(subscribe, read, () => DEFAULT);
  const set = useCallback((o: Occasion) => {
    try {
      localStorage.setItem(KEY, o);
    } catch {
      /* private mode: just don't remember */
    }
    window.dispatchEvent(new Event(EVENT));
  }, []);
  return [occ, set];
}
