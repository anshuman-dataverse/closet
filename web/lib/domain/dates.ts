// Calendar days are YYYY-MM-DD strings in the profile's time zone (SPEC 3, 8).

const YMD = /^\d{4}-\d{2}-\d{2}$/;
export const isYmd = (s: unknown): s is string => typeof s === "string" && YMD.test(s);

/** Today's date in a time zone, e.g. todayIn("America/New_York") → "2026-11-20". */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
      now,
    );
  } catch {
    return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  }
}

const dayNum = (s: string) => {
  const [y, m, d] = s.split("-").map(Number) as [number, number, number];
  return Math.round(Date.UTC(y, m - 1, d) / 86_400_000);
};

/** Whole days from a to b (b − a). */
export const daysBetween = (a: string, b: string): number => dayNum(b) - dayNum(a);

export function addDays(s: string, n: number): string {
  const t = new Date((dayNum(s) + n) * 86_400_000);
  return t.toISOString().slice(0, 10);
}

export function lastWornText(last: string | null | undefined, today: string): string {
  if (!isYmd(last)) return "Never worn";
  const n = daysBetween(last, today);
  if (n <= 0) return "Worn today";
  if (n === 1) return "Worn yesterday";
  return `Last worn ${n} days ago`;
}

/** "Nov 17", or "Nov 17, 2025" when it's not this year. */
export function shortDate(s: string | null | undefined, today: string): string {
  if (!isYmd(s)) return "";
  const [y, m, d] = s.split("-").map(Number) as [number, number, number];
  const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric", timeZone: "UTC" };
  if (String(y) !== today.slice(0, 4)) opts.year = "numeric";
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", opts);
}

/** "2026-11" → "November" (or "November 2025" with withYear). */
export function monthName(ym: string, withYear = false): string {
  const [y, m] = ym.split("-").map(Number) as [number, number];
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", {
    month: "long",
    ...(withYear ? { year: "numeric" } : {}),
    timeZone: "UTC",
  });
}

/** The last n months ending with today's month, oldest first: ["2025-12", …, "2026-11"]. */
export function lastMonths(today: string, n = 12): string[] {
  const [y, m] = today.split("-").map(Number) as [number, number];
  return Array.from({ length: n }, (_, k) => {
    const d = new Date(Date.UTC(y, m - 1 - (n - 1 - k), 1));
    return d.toISOString().slice(0, 7);
  });
}
