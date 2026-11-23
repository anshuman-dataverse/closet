// Height in Settings: typed as 5'9", 5 ft 9, 69 in, 175 or 175 cm. Stored in centimeters.

export function parseHeight(input: string): number | null {
  const t = input.trim().toLowerCase().replace(/[’′]/g, "'").replace(/[”″]/g, '"');
  if (!t) return null;
  let cm: number | null = null;
  const ftIn = t.match(/^(\d)\s*(?:'|ft|feet)\s*(\d{1,2}(?:\.\d)?)?\s*(?:"|in|inches)?$/);
  const inches = t.match(/^(\d{2}(?:\.\d)?)\s*(?:"|in|inches)$/);
  const metric = t.match(/^(\d{2,3}(?:\.\d)?)\s*(?:cm)?$/);
  const meters = t.match(/^([12](?:\.\d{1,2}))\s*m$/);
  if (ftIn) cm = (Number(ftIn[1]) * 12 + Number(ftIn[2] ?? 0)) * 2.54;
  else if (inches) cm = Number(inches[1]) * 2.54;
  else if (meters) cm = Number(meters[1]) * 100;
  else if (metric) cm = Number(metric[1]);
  if (cm === null || !Number.isFinite(cm)) return null;
  const r = Math.round(cm);
  return r >= 100 && r <= 250 ? r : null;
}

/** 175 → 5'9" (with °F settings) or 175 cm. */
export function formatHeight(cm: number | null | undefined, unit: "F" | "C"): string {
  if (!cm) return "";
  if (unit === "C") return `${cm} cm`;
  const total = Math.round(cm / 2.54);
  return `${Math.floor(total / 12)}'${total % 12}"`;
}
