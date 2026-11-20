// The Mac counts as offline when its last heartbeat is more than 2 minutes old (SPEC 4).

export const OFFLINE_AFTER_MS = 2 * 60 * 1000;

export function isOffline(lastSeenAt: string | null | undefined, now: number = Date.now()): boolean {
  if (!lastSeenAt) return true;
  const t = Date.parse(lastSeenAt);
  if (Number.isNaN(t)) return true;
  return now - t > OFFLINE_AFTER_MS;
}

export type Capabilities = { searxng: boolean; ollama: boolean; openai: boolean };

export function readCapabilities(raw: unknown): Capabilities {
  const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return { searxng: o.searxng === true, ollama: o.ollama === true, openai: o.openai === true };
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
