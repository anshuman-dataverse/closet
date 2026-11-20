"use client";

import { useEffect } from "react";
import { loadCloset } from "@/lib/closet/store";

/** Loads the closet once signed in, and again when the app comes back to the foreground. */
export function ClosetProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    void loadCloset();
    const onVisible = () => {
      if (document.visibilityState === "visible") void loadCloset();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);
  return children;
}
