"use client";
// Batched, short-lived signed URLs for the private bucket (SPEC 3, Storage).
// Components ask for paths; requests in the same tick go out as one createSignedUrls call.

import { useEffect, useSyncExternalStore } from "react";
import { BUCKET } from "@/lib/photos";
import { supabase } from "@/lib/supabase/client";

const TTL_S = 3600;
const REFRESH_MARGIN_MS = 5 * 60 * 1000;

const cache = new Map<string, { url: string; exp: number }>();
const pending = new Set<string>();
const listeners = new Set<() => void>();
let version = 0;
let timer: ReturnType<typeof setTimeout> | null = null;

const emit = () => {
  version += 1;
  for (const l of listeners) l();
};

function flush() {
  timer = null;
  const paths = [...pending];
  pending.clear();
  if (!paths.length) return;
  void supabase()
    .storage.from(BUCKET)
    .createSignedUrls(paths, TTL_S)
    .then(({ data }) => {
      const exp = Date.now() + TTL_S * 1000;
      for (const r of data ?? []) if (r.path && r.signedUrl) cache.set(r.path, { url: r.signedUrl, exp });
      emit();
    });
}

function request(paths: readonly string[]) {
  const now = Date.now();
  for (const p of paths) {
    const c = cache.get(p);
    if (!c || c.exp - now < REFRESH_MARGIN_MS) pending.add(p);
  }
  if (pending.size && !timer) timer = setTimeout(flush, 0);
}

/** Forget cached URLs, e.g. after deleting files. */
export function dropSignedUrls(paths: readonly (string | null | undefined)[]) {
  for (const p of paths) if (p) cache.delete(p);
}

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => listeners.delete(cb);
};

export function useSignedUrl(path: string | null | undefined): string | undefined {
  useSyncExternalStore(
    subscribe,
    () => version,
    () => 0,
  );
  useEffect(() => {
    if (path) request([path]);
  }, [path]);
  return path ? cache.get(path)?.url : undefined;
}
