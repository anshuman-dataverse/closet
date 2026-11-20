// Named swatches, from the prototype. Used when a piece has no photo and no hex.
export const NAMED: Record<string, string> = {
  black: "#1c1c1e",
  white: "#f6f6f3",
  ivory: "#f1ead8",
  cream: "#ede3c8",
  beige: "#d6c3a1",
  khaki: "#b5a273",
  tan: "#c19f72",
  camel: "#c0955f",
  brown: "#6a4a33",
  navy: "#1f2a48",
  "light blue": "#a9c4e4",
  "sky blue": "#86b4df",
  blue: "#3a5aa4",
  teal: "#2c7a7a",
  "forest green": "#2c4a33",
  olive: "#6a6a39",
  green: "#3e7a4a",
  charcoal: "#3c3f47",
  grey: "#8a8f98",
  gray: "#8a8f98",
  silver: "#c0c4ca",
  maroon: "#6c1f2a",
  burgundy: "#6d1f30",
  red: "#b2261e",
  pink: "#e6a2b6",
  lavender: "#b7a8d8",
  purple: "#6a4b99",
  mustard: "#c79a2d",
  yellow: "#e6c446",
  orange: "#d8722a",
  rust: "#a54a2a",
  indigo: "#27365a",
  terracotta: "#b5583b",
};
const KEYS = Object.keys(NAMED).sort((a, b) => b.length - a.length);

export function safeHex(h: unknown): string {
  return typeof h === "string" && /^#[0-9a-f]{6}$/i.test(h.trim()) ? h.trim().toLowerCase() : "";
}

/** "Light blue denim" → "light blue"; unknown → "". */
export function colorKey(name: string | null | undefined): string {
  const c = (name ?? "").toLowerCase();
  const k = KEYS.find((n) => c.includes(n));
  return k === "gray" ? "grey" : (k ?? "");
}

export function swatchFor(it: { color_hex?: string | null; color_name?: string | null }): string {
  return safeHex(it.color_hex) || NAMED[colorKey(it.color_name)] || "";
}

export function isDark(hex: string): boolean {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255,
    g = (n >> 8) & 255,
    b = n & 255;
  return 0.299 * r + 0.587 * g + 0.114 * b < 140;
}
