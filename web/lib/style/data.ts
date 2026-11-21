// Tables exported from the worker's YAML (scripts/export-style-data.py). Edit the YAML, then re-export.
import raw from "./data.json";

export type Thresholds = {
  undertone: { warm_min_hue: number; cool_max_hue: number; olive_max_a: number; olive_b: [number, number] };
  depth: { light_min_ita: number; deep_max_ita: number };
  contrast: { low_below: number; high_above: number };
  lighting: { dark_face_L: number; cast_a: number; warm_cast_b: number; cool_cast_b: number; blown_share: number };
  face_shape: Record<string, number>;
  body: Record<string, number>;
  borderline: number;
};
export type PaletteEntry = { best: string[]; neutrals: string[]; careful: { name: string; why: string }[] };
export type FaceTip = { why: string; frames: string[]; hair: string[] };

export const T = raw.thresholds as unknown as Thresholds;
export const PALETTES = raw.palettes as unknown as Record<string, PaletteEntry>;
export const FACE_TIPS = raw.faceTips as unknown as Record<string, FaceTip>;
export const COLORS = raw.colors as Record<string, string>;
