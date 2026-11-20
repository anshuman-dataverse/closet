"use client";
// One client store for the wardrobe. It loads everything for the signed-in user at once
// (a few hundred rows), applies each write to Supabase first, then patches local state.
// RLS scopes every query; nothing here can see another user's rows.

import { useMemo, useSyncExternalStore } from "react";
import type { Item, ItemStatus, Outfit, Profile, WearLog } from "@/lib/closet/types";
import type { Database } from "@/lib/database.types";
import { todayIn } from "@/lib/domain/dates";
import { wearStats, type WearStats } from "@/lib/domain/wear";
import type { Occasion } from "@/lib/occasions";
import { listAllFiles, removePaths } from "@/lib/photos";
import { dropSignedUrls } from "@/lib/signed-urls";
import { supabase } from "@/lib/supabase/client";

export type ClosetState = {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  userId: string | null;
  profile: Profile | null;
  items: Item[];
  outfits: Outfit[];
  logs: WearLog[];
};

const EMPTY: ClosetState = { status: "idle", userId: null, profile: null, items: [], outfits: [], logs: [] };
let state: ClosetState = EMPTY;
const listeners = new Set<() => void>();

const set = (patch: Partial<ClosetState>) => {
  state = { ...state, ...patch };
  for (const l of listeners) l();
};
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => listeners.delete(cb);
};

export const LOAD_ERROR = "Couldn’t load your closet. Check your connection, then pull down or reopen the app.";

let inflight: Promise<void> | null = null;

export function loadCloset(): Promise<void> {
  inflight ??= (async () => {
    const db = supabase();
    if (state.status !== "ready") set({ status: "loading" });
    try {
      const {
        data: { user },
      } = await db.auth.getUser();
      if (!user) throw new Error("signed out");
      const [p, i, o, oi, w, wi] = await Promise.all([
        db.from("profiles").select("*").eq("user_id", user.id).maybeSingle(),
        db.from("items").select("*").order("created_at", { ascending: false }),
        db.from("outfits").select("*").order("created_at", { ascending: true }),
        db.from("outfit_items").select("outfit_id,item_id,position"),
        db.from("wear_logs").select("*").order("worn_on", { ascending: false }),
        db.from("wear_log_items").select("wear_log_id,item_id"),
      ]);
      const err = [p, i, o, oi, w, wi].find((r) => r.error)?.error;
      if (err) throw err;

      const pieces = new Map<string, { item_id: string; position: number }[]>();
      for (const r of oi.data ?? []) (pieces.get(r.outfit_id) ?? pieces.set(r.outfit_id, []).get(r.outfit_id)!).push(r);
      const worn = new Map<string, string[]>();
      for (const r of wi.data ?? [])
        (worn.get(r.wear_log_id) ?? worn.set(r.wear_log_id, []).get(r.wear_log_id)!).push(r.item_id);

      set({
        status: "ready",
        error: undefined,
        userId: user.id,
        profile: p.data,
        items: i.data ?? [],
        outfits: (o.data ?? []).map((x) => ({
          ...x,
          itemIds: (pieces.get(x.id) ?? []).sort((a, b) => a.position - b.position).map((r) => r.item_id),
        })),
        logs: (w.data ?? []).map((x) => ({ ...x, itemIds: worn.get(x.id) ?? [] })),
      });
    } catch {
      set({ status: state.status === "ready" ? "ready" : "error", error: LOAD_ERROR });
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

export function useCloset(): ClosetState {
  return useSyncExternalStore(
    subscribe,
    () => state,
    () => EMPTY,
  );
}

export type Derived = {
  today: string;
  timezone: string;
  byId: Map<string, Item>;
  stats: WearStats;
  active: Item[];
};

/** Lookups and stats derived from the store. `today` uses the profile's time zone. */
export function useDerived(s: ClosetState): Derived {
  const timezone = s.profile?.timezone ?? "America/New_York";
  return useMemo(() => {
    const byId = new Map(s.items.map((i) => [i.id, i]));
    return {
      today: s.status === "ready" ? todayIn(timezone) : "",
      timezone,
      byId,
      stats: wearStats(s.logs),
      active: s.items.filter((i) => i.status === "active"),
    };
  }, [s.items, s.logs, s.status, timezone]);
}

// ---------------------------------------------------------------- writes

const fail = (e: { message?: string } | null | undefined, fallback: string): never => {
  throw new Error(e?.message && !/^(JWT|fetch|Failed)/i.test(e.message) ? e.message : fallback);
};

export type ItemInput = Omit<
  Database["public"]["Tables"]["items"]["Insert"],
  "user_id" | "created_at" | "updated_at" | "suggestions" | "tags_status"
>;

export async function saveItem(
  input: ItemInput & { id: string },
  replacedPaths: (string | null)[] = [],
): Promise<Item> {
  const db = supabase();
  const exists = state.items.some((i) => i.id === input.id);
  const { data, error } = exists
    ? await db.from("items").update(input).eq("id", input.id).select("*").single()
    : await db.from("items").insert(input).select("*").single();
  if (error || !data) fail(error, "Couldn’t save that piece. Try again.");
  const item = data!;
  set({ items: exists ? state.items.map((i) => (i.id === item.id ? item : i)) : [item, ...state.items] });
  if (replacedPaths.length) {
    dropSignedUrls(replacedPaths);
    void removePaths(db, replacedPaths);
  }
  return item;
}

export async function setItemsStatus(ids: readonly string[], status: ItemStatus): Promise<void> {
  if (!ids.length) return;
  const { data, error } = await supabase().from("items").update({ status }).in("id", ids).select("*");
  if (error) fail(error, "Couldn’t update that. Try again.");
  const byId = new Map((data ?? []).map((i) => [i.id, i]));
  set({ items: state.items.map((i) => byId.get(i.id) ?? i) });
}

/** Deletes the piece, its files, and removes it from outfits (cascade). */
export async function deleteItem(id: string): Promise<void> {
  const db = supabase();
  const it = state.items.find((i) => i.id === id);
  if (!it) return;
  const { error } = await db.from("items").delete().eq("id", id);
  if (error) fail(error, "Couldn’t delete that piece. Try again.");
  const files = [it.photo_path, it.thumb_path, it.cutout_path];
  dropSignedUrls(files);
  void removePaths(db, files);
  set({
    items: state.items.filter((i) => i.id !== id),
    outfits: state.outfits.map((o) => ({ ...o, itemIds: o.itemIds.filter((x) => x !== id) })),
    logs: state.logs.map((l) => ({ ...l, itemIds: l.itemIds.filter((x) => x !== id) })),
  });
}

export async function saveOutfit(o: {
  id: string | null;
  name: string;
  occasions: Occasion[];
  itemIds: string[];
  source?: "manual" | "suggested";
}): Promise<string> {
  const db = supabase();
  const { data: id, error } = await db.rpc("save_outfit", {
    p_id: o.id as string, // null creates a new outfit (generated types miss nullable uuid args)
    p_name: o.name,
    p_occasions: o.occasions,
    p_item_ids: o.itemIds,
    p_source: o.source ?? "manual",
  });
  if (error || !id) fail(error, "Couldn’t save the outfit. Try again.");
  const [row, pieces] = await Promise.all([
    db.from("outfits").select("*").eq("id", id!).single(),
    db.from("outfit_items").select("item_id,position").eq("outfit_id", id!).order("position"),
  ]);
  if (row.error || !row.data) fail(row.error, "Saved, but couldn’t refresh. Reopen the app.");
  const outfit: Outfit = { ...row.data!, itemIds: (pieces.data ?? []).map((r) => r.item_id) };
  const exists = state.outfits.some((x) => x.id === id);
  set({ outfits: exists ? state.outfits.map((x) => (x.id === id ? outfit : x)) : [...state.outfits, outfit] });
  return id!;
}

export async function deleteOutfit(id: string): Promise<void> {
  const { error } = await supabase().from("outfits").delete().eq("id", id);
  if (error) fail(error, "Couldn’t delete the outfit. Try again.");
  set({
    outfits: state.outfits.filter((o) => o.id !== id),
    logs: state.logs.map((l) => (l.outfit_id === id ? { ...l, outfit_id: null } : l)),
  });
}

export type LogResult = { status: "logged" | "already"; id: string };

export async function logWear(p: {
  wornOn: string;
  occasion: Occasion;
  outfitId: string | null;
  itemIds: string[];
}): Promise<LogResult> {
  const db = supabase();
  const { data, error } = await db.rpc("log_wear", {
    p_worn_on: p.wornOn,
    p_occasion: p.occasion,
    p_outfit_id: p.outfitId as string, // null for loose pieces (generated types miss nullable uuid args)
    p_item_ids: p.itemIds,
  });
  if (error || !data) fail(error, "Couldn’t log that. Try again.");
  const r = data as unknown as LogResult;
  if (r.status === "logged") {
    const { data: row } = await db.from("wear_logs").select("*").eq("id", r.id).single();
    if (row) set({ logs: [{ ...row, itemIds: [...new Set(p.itemIds)] }, ...state.logs] });
  }
  return r;
}

export async function removeWear(id: string): Promise<void> {
  const { error } = await supabase().from("wear_logs").delete().eq("id", id);
  if (error) fail(error, "Couldn’t remove that. Try again.");
  set({ logs: state.logs.filter((l) => l.id !== id) });
}

export type ProfilePatch = Database["public"]["Tables"]["profiles"]["Update"];

export async function saveProfile(patch: ProfilePatch): Promise<void> {
  const uid = state.userId;
  if (!uid) throw new Error("Sign in first.");
  const { data, error } = await supabase().from("profiles").update(patch).eq("user_id", uid).select("*").single();
  if (error || !data) fail(error, "Couldn’t save your settings. Try again.");
  set({ profile: data });
}

/** Removes every stored file, then every row (SPEC 4.6). */
export async function deleteAllData(): Promise<void> {
  const db = supabase();
  const uid = state.userId;
  if (!uid) throw new Error("Sign in first.");
  const files = await listAllFiles(db, uid);
  for (let k = 0; k < files.length; k += 100) await removePaths(db, files.slice(k, k + 100));
  const { error } = await db.rpc("delete_all_my_data");
  if (error) fail(error, "Couldn’t delete everything. Try again.");
  dropSignedUrls(files);
  await loadCloset();
}
