// The Mac counts as offline when its last heartbeat is more than 2 minutes old (SPEC 4).

export const OFFLINE_AFTER_MS = 2 * 60 * 1000;

export function isOffline(lastSeenAt: string | null | undefined, now: number = Date.now()): boolean {
  if (!lastSeenAt) return true;
  const t = Date.parse(lastSeenAt);
  if (Number.isNaN(t)) return true;
  return now - t > OFFLINE_AFTER_MS;
}

export type CompatStatus = { installed: boolean; on: boolean; n: number; need: number };
export type Capabilities = { searxng: boolean; ollama: boolean; openai: boolean; compat: CompatStatus };

const count = (v: unknown, fallback: number) => (typeof v === "number" && Number.isInteger(v) && v >= 0 ? v : fallback);

export function readCapabilities(raw: unknown): Capabilities {
  const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const c = o.compat && typeof o.compat === "object" ? (o.compat as Record<string, unknown>) : {};
  return {
    searxng: o.searxng === true,
    ollama: o.ollama === true,
    openai: o.openai === true,
    compat: { installed: c.installed === true, on: c.on === true, n: count(c.n, 0), need: count(c.need, 30) },
  };
}

/** The outfit model line in Your Mac (SPEC 5.11). It's on only after beating the rules on your picks. */
export function compatText(c: CompatStatus): string {
  if (!c.installed) return "Not installed";
  if (c.on) return "On";
  if (c.n >= c.need) return "Off: it didn’t beat the rules on your logged outfits";
  return `Off until it beats the rules on ${c.need} of your logged outfits (${c.n} so far)`;
}

/** "15 photos, 4.8 MB" from a backup job's result, or "" if it isn't one. */
export function backupSummary(result: unknown): string {
  const r = result && typeof result === "object" ? (result as Record<string, unknown>) : {};
  const n = typeof r.files_total === "number" ? r.files_total : null;
  const bytes =
    (typeof r.files_bytes === "number" ? r.files_bytes : 0) + (typeof r.db_bytes === "number" ? r.db_bytes : 0);
  if (n === null) return "";
  const size = bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${(bytes / 1e6).toFixed(1)} MB`;
  return `${n} ${n === 1 ? "photo" : "photos"}, ${size}`;
}

/** "just now", "3 minutes ago", "2 hours ago", or a short date. */
export function seenAgo(iso: string | null | undefined, now: number = Date.now()): string {
  if (!iso) return "never";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "never";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} ${m === 1 ? "minute" : "minutes"} ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} ${h === 1 ? "hour" : "hours"} ago`;
  return new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
