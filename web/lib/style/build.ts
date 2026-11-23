// Palette lookup and neutral, templated text. A port of worker/closet_worker/vision/style.py (same output shape).
import { fitNotes, type BodyRatios } from "./body";
import { COLORS, FACE_TIPS, PALETTES, T } from "./data";
import { contrast, depth, undertone } from "./skin";

export type Measurements = {
  skin_lab: [number, number, number];
  hair_L: number | null;
  hue: number;
  ita: number;
  face_shape: string | null;
  face_shape_votes: (string | null)[];
  body_ratios: BodyRatios | null;
  lighting_note: string | null;
  [k: string]: unknown;
};
export type Overrides = { undertone?: string | null; contrast?: string | null; depth?: string | null };

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);
const capFirst = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1).toLowerCase(); // Python str.capitalize
const sw = (n: string) => ({ name: cap(n), hex: COLORS[n]! });
const list = (xs: string[]) => (xs.length === 1 ? xs[0]! : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const lightness = (hx: string) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hx.slice(i, i + 2), 16)) as [number, number, number];
  return 0.299 * r + 0.587 * g + 0.114 * b;
};

export function borderlineNotes(m: Measurements, o: Overrides): string[] {
  const edge = T.borderline ?? 3;
  const u = T.undertone;
  const out: string[] = [];
  if (!o.undertone) {
    if (Math.abs(m.hue - u.cool_max_hue) <= edge)
      out.push("Your undertone read sits between cool and neutral. If neutral feels truer, change it below.");
    else if (Math.abs(m.hue - u.warm_min_hue) <= edge)
      out.push("Your undertone read sits between neutral and warm. If warm feels truer, change it below.");
  }
  const spread = Number(m.hue_spread ?? 0);
  if (!o.undertone && spread > (T.photos_disagree_hue ?? 12))
    out.push(
      `Your face photos disagree by ${spread.toFixed(0)}° on undertone, so the light changed between them. Retake them in the same daylight, facing the window.`,
    );
  const d = T.depth;
  if (!o.depth && Math.min(Math.abs(m.ita - d.light_min_ita), Math.abs(m.ita - d.deep_max_ita)) <= edge)
    out.push("Your depth read is close to the next band, so the palette may shift slightly between photos.");
  const votes = [...new Set(m.face_shape_votes.filter((v): v is string => !!v))].sort();
  if (votes.length > 1) out.push(`Your face shape reads between ${votes.join(" and ")}; tips for both can work.`);
  if (m.hair_L !== null && !o.contrast) {
    const delta = Math.abs(m.skin_lab[0] - m.hair_L);
    const c = T.contrast;
    if (Math.min(Math.abs(delta - c.low_below), Math.abs(delta - c.high_above)) <= edge)
      out.push("Your contrast read is close to the next band. Change it below if it feels off.");
  }
  return out;
}

export function buildAnalysis(m: Measurements, o: Overrides = {}) {
  const lab = m.skin_lab;
  const computed = {
    undertone: undertone(lab),
    depth: depth(lab),
    contrast: contrast(lab[0], m.hair_L) ?? "medium",
  };
  const effective = {
    undertone: o.undertone || computed.undertone,
    depth: o.depth || computed.depth,
    contrast: o.contrast || computed.contrast,
  };
  const pal = PALETTES[`${effective.undertone}/${effective.depth}/${effective.contrast}`]!;
  const best = pal.best.map(sw);
  const neutrals = pal.neutrals.map(sw);
  const careful = pal.careful.map((c) => ({ ...sw(c.name), why: c.why }));
  const b = best.map((x) => x.name.toLowerCase()),
    nn = neutrals.map((x) => x.name.toLowerCase());
  const tips = m.face_shape ? FACE_TIPS[m.face_shape] : undefined;
  const face = tips
    ? { shape: m.face_shape, why: tips.why, frames: tips.frames, hair: tips.hair }
    : { shape: null, note: "Face the camera straight on in your close-up for frame and hair tips." };
  const dark = [...b].sort((x, y) => lightness(COLORS[x]!) - lightness(COLORS[y]!));
  return {
    version: 1,
    computed,
    effective,
    summary:
      `${capFirst(effective.undertone)} undertone, ${effective.depth} depth and ${effective.contrast} contrast. ` +
      `${capFirst(list(b.slice(0, 3)))} sit well near your face; ${list(nn.slice(0, 3))} are easy neutrals.`,
    best,
    neutrals,
    careful,
    fit_notes: fitNotes(m.body_ratios),
    occasion_tips: {
      office: `${capFirst(nn[0]!)} or ${nn[1]} layers over crisp shirts, with ${b[0]} as the accent.`,
      college: `Overshirts and knits in ${b[0]} or ${b[1]} with dark denim or ${nn[0]} trousers.`,
      party: `Deeper ${dark[0]} or ${dark[1]} with one statement piece; ${nn[0]} keeps the rest calm.`,
      home: `Soft knits in ${nn[0]} and ${nn.length > 1 ? nn[1] : nn[0]}.`,
    },
    face,
    confidence_note: m.lighting_note,
    borderline: borderlineNotes(m, o),
    measurements: m,
    thresholds: T,
    note: "An estimate from your photos. You can change it.",
  };
}
export type BuiltAnalysis = ReturnType<typeof buildAnalysis>;
