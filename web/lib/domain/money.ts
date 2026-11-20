// Money is integer cents (USD). Display: "$35", "$39.50", "$1,200".

export function formatCents(cents: number | null | undefined): string {
  const c = Math.round(Number(cents) || 0);
  const neg = c < 0;
  const abs = Math.abs(c);
  const whole = Math.floor(abs / 100);
  const frac = abs % 100;
  const s = `$${whole.toLocaleString("en-US")}${frac ? `.${String(frac).padStart(2, "0")}` : ""}`;
  return neg ? `−${s}` : s;
}

/** "39.5" → 3950, "$1,200" → 120000, "" or junk → null. Negative → null. */
export function parseDollars(input: string | number | null | undefined): number | null {
  if (input == null) return null;
  const s = String(input).replace(/[$,\s]/g, "");
  if (!s || !/^\d*\.?\d*$/.test(s) || s === ".") return null;
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.round(n * 100);
}

/** Cents → the string an <input type="number"> should show ("39.5" style, no $). */
export const centsToInput = (c: number | null | undefined): string => (c == null ? "" : String(Math.round(c) / 100));

export function budgetRange(min: number | null | undefined, max: number | null | undefined): string {
  const lo = min != null && min > 0 ? min : null;
  const hi = max != null && max > 0 ? max : null;
  if (lo != null && hi != null) return `${formatCents(Math.min(lo, hi))} to ${formatCents(Math.max(lo, hi))}`;
  if (hi != null) return `up to ${formatCents(hi)}`;
  if (lo != null) return `from ${formatCents(lo)}`;
  return "any price";
}
