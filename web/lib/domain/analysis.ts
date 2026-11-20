// The style profile the Mac writes to profiles.analysis (SPEC 5.2). Parsed defensively: it's JSON.

export type Swatch = { name: string; hex: string; why?: string };
export type Analysis = {
  computed: { undertone: string; depth: string; contrast: string };
  effective: { undertone: string; depth: string; contrast: string };
  summary: string;
  best: Swatch[];
  neutrals: Swatch[];
  careful: Swatch[];
  fit_notes: { area: string; advice: string }[];
  occasion_tips: Record<string, string>;
  face: { shape: string | null; why?: string; frames?: string[]; hair?: string[]; note?: string };
  confidence_note: string | null;
  borderline: string[];
  note: string;
};

const str = (v: unknown) => (typeof v === "string" ? v : "");
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const hex = (v: unknown) => (typeof v === "string" && /^#[0-9a-f]{6}$/i.test(v) ? v.toLowerCase() : "");

function swatches(v: unknown): Swatch[] {
  return arr(v)
    .map((x) => x as Record<string, unknown>)
    .filter((x) => str(x?.name) && hex(x?.hex))
    .map((x) => ({ name: str(x.name), hex: hex(x.hex), ...(str(x.why) ? { why: str(x.why) } : {}) }));
}

function triple(v: unknown) {
  const o = (v ?? {}) as Record<string, unknown>;
  return { undertone: str(o.undertone), depth: str(o.depth), contrast: str(o.contrast) };
}

export function parseAnalysis(raw: unknown): Analysis | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const best = swatches(r.best);
  if (!best.length) return null;
  const face = (r.face ?? {}) as Record<string, unknown>;
  return {
    computed: triple(r.computed),
    effective: triple(r.effective),
    summary: str(r.summary),
    best,
    neutrals: swatches(r.neutrals),
    careful: swatches(r.careful),
    fit_notes: arr(r.fit_notes)
      .map((x) => x as Record<string, unknown>)
      .filter((x) => str(x?.area) && str(x?.advice))
      .map((x) => ({ area: str(x.area), advice: str(x.advice) })),
    occasion_tips: Object.fromEntries(
      Object.entries((r.occasion_tips ?? {}) as Record<string, unknown>).filter(([, v]) => typeof v === "string"),
    ) as Record<string, string>,
    face: {
      shape: str(face.shape) || null,
      ...(str(face.why) ? { why: str(face.why) } : {}),
      frames: arr(face.frames).map(str).filter(Boolean),
      hair: arr(face.hair).map(str).filter(Boolean),
      ...(str(face.note) ? { note: str(face.note) } : {}),
    },
    confidence_note: str(r.confidence_note) || null,
    borderline: arr(r.borderline).map(str).filter(Boolean),
    note: str(r.note) || "An estimate from your photos. You can change it.",
  };
}

export const KIND_LABEL = {
  face: "Face close-up",
  front: "Front",
  side: "Side",
  back: "Back",
  other: "Other",
} as const;
export type PhotoKind = keyof typeof KIND_LABEL;

/** The next kind worth adding: face, then front, side, back, then other. */
export function nextKind(have: readonly string[]): PhotoKind {
  return (["face", "front", "side", "back"] as const).find((k) => !have.includes(k)) ?? "other";
}

export const canAnalyze = (have: readonly string[]) => have.includes("face") && have.includes("front");
