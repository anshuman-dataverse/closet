// White-reference calibration (von Kries): find the sheet of white paper, then scale each linear RGB
// channel so the paper reads neutral. This removes the camera/lighting color cast before skin is read.
import { chroma, fromLinear, srgbToLab, toLinear } from "./color";
import type { Pixels } from "./types";

export type Box = { x0: number; y0: number; x1: number; y1: number };
export type Paper = { gains: [number, number, number]; cast: number; cells: number; box: Box };
export type PaperResult = { paper: Paper | null; problem: string | null };

const MIN_L = 70, // brighter than a typical wall; white paper in daylight reads ~80–95
  MAX_CHROMA = 22,
  CLIP = 250;

type Grid = { size: number; cols: number; rows: number; mean: Float64Array; lab: [number, number, number][] };

function grid(img: Pixels): Grid {
  const size = Math.max(4, Math.round(Math.min(img.width, img.height) / 80));
  const cols = Math.floor(img.width / size),
    rows = Math.floor(img.height / size);
  const mean = new Float64Array(cols * rows * 3);
  const lab: [number, number, number][] = [];
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) {
      let R = 0,
        G = 0,
        B = 0,
        n = 0;
      for (let y = r * size; y < (r + 1) * size; y++)
        for (let x = c * size; x < (c + 1) * size; x++) {
          const i = (y * img.width + x) * 4;
          R += img.data[i]!;
          G += img.data[i + 1]!;
          B += img.data[i + 2]!;
          n++;
        }
      const k = (r * cols + c) * 3;
      mean[k] = R / n;
      mean[k + 1] = G / n;
      mean[k + 2] = B / n;
      lab.push(srgbToLab(R / n, G / n, B / n));
    }
  return { size, cols, rows, mean, lab };
}

function components(g: Grid, ok: (i: number) => boolean): number[][] {
  const seen = new Uint8Array(g.cols * g.rows);
  const out: number[][] = [];
  for (let s = 0; s < g.cols * g.rows; s++) {
    if (seen[s] || !ok(s)) continue;
    const comp: number[] = [];
    const stack = [s];
    seen[s] = 1;
    while (stack.length) {
      const i = stack.pop()!;
      comp.push(i);
      const r = Math.floor(i / g.cols),
        c = i % g.cols;
      for (const [dr, dc] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ] as const) {
        const rr = r + dr,
          cc = c + dc;
        if (rr < 0 || cc < 0 || rr >= g.rows || cc >= g.cols) continue;
        const j = rr * g.cols + cc;
        if (!seen[j] && ok(j)) {
          seen[j] = 1;
          stack.push(j);
        }
      }
    }
    out.push(comp);
  }
  return out;
}

/** Is this bright area shaped like a sheet of paper held beside the face (not sky, a wall or a window)? */
export function sheetLike(
  g: { cols: number; rows: number },
  comp: number[],
  face: { y0: number; y1: number },
  cell: number,
): boolean {
  let c0 = Infinity,
    r0 = Infinity,
    c1 = -1,
    r1 = -1;
  for (const i of comp) {
    const r = Math.floor(i / g.cols),
      c = i % g.cols;
    c0 = Math.min(c0, c);
    r0 = Math.min(r0, r);
    c1 = Math.max(c1, c);
    r1 = Math.max(r1, r);
  }
  const w = c1 - c0 + 1,
    h = r1 - r0 + 1;
  const fill = comp.length / (w * h);
  const aspect = w / h;
  const edges = [r0 === 0, c0 === 0, r1 === g.rows - 1, c1 === g.cols - 1].filter(Boolean).length;
  const share = comp.length / (g.cols * g.rows);
  const y0 = r0 * cell,
    y1 = (r1 + 1) * cell;
  const overlap = Math.max(0, Math.min(y1, face.y1) - Math.max(y0, face.y0)) / Math.max(1, y1 - y0);
  return fill >= 0.7 && aspect >= 0.25 && aspect <= 4 && r0 !== 0 && edges <= 1 && share <= 0.2 && overlap >= 0.3;
}

function largestComponent(g: Grid, ok: (i: number) => boolean, seed?: number): number[] {
  const seen = new Uint8Array(g.cols * g.rows);
  let best: number[] = [];
  const starts = seed !== undefined ? [seed] : [...Array(g.cols * g.rows).keys()];
  for (const s of starts) {
    if (seen[s] || !ok(s)) continue;
    const comp: number[] = [];
    const stack = [s];
    seen[s] = 1;
    while (stack.length) {
      const i = stack.pop()!;
      comp.push(i);
      const r = Math.floor(i / g.cols),
        c = i % g.cols;
      for (const [dr, dc] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ] as const) {
        const rr = r + dr,
          cc = c + dc;
        if (rr < 0 || cc < 0 || rr >= g.rows || cc >= g.cols) continue;
        const j = rr * g.cols + cc;
        if (!seen[j] && ok(j)) {
          seen[j] = 1;
          stack.push(j);
        }
      }
    }
    if (comp.length > best.length) best = comp;
  }
  return best;
}

function toPaper(g: Grid, comp: number[]): Paper {
  let r = 0,
    gr = 0,
    b = 0;
  let x0 = Infinity,
    y0 = Infinity,
    x1 = 0,
    y1 = 0;
  for (const i of comp) {
    r += toLinear(g.mean[i * 3]!);
    gr += toLinear(g.mean[i * 3 + 1]!);
    b += toLinear(g.mean[i * 3 + 2]!);
    const row = Math.floor(i / g.cols),
      col = i % g.cols;
    x0 = Math.min(x0, col * g.size);
    y0 = Math.min(y0, row * g.size);
    x1 = Math.max(x1, (col + 1) * g.size);
    y1 = Math.max(y1, (row + 1) * g.size);
  }
  const n = comp.length;
  const lin: [number, number, number] = [r / n, gr / n, b / n];
  const Y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  const gains = lin.map((c) => Y / Math.max(c, 1e-6)) as [number, number, number];
  const paperLab = srgbToLab(fromLinear(lin[0]), fromLinear(lin[1]), fromLinear(lin[2]));
  return { gains, cast: chroma(paperLab), cells: n, box: { x0, y0, x1, y1 } };
}

/** Finds the white paper automatically: the largest bright, low-saturation area outside the face. */
export function findPaper(img: Pixels, face: Box): PaperResult {
  const g = grid(img);
  const pad = 0.1 * (face.x1 - face.x0);
  const outsideFace = (i: number) => {
    const cx = ((i % g.cols) + 0.5) * g.size,
      cy = (Math.floor(i / g.cols) + 0.5) * g.size;
    return cx < face.x0 - pad || cx > face.x1 + pad || cy < face.y0 - pad || cy > face.y1 + pad;
  };
  const max = (i: number) => Math.max(g.mean[i * 3]!, g.mean[i * 3 + 1]!, g.mean[i * 3 + 2]!);
  const white = (i: number) => outsideFace(i) && g.lab[i]![0] >= MIN_L && chroma(g.lab[i]!) <= MAX_CHROMA;
  const minCells = Math.max(12, Math.round(0.015 * g.cols * g.rows));
  const sheets = components(g, (i) => white(i) && max(i) < CLIP)
    .filter((c) => c.length >= minCells && sheetLike(g, c, face, g.size))
    .sort((a, b) => b.length - a.length);
  if (sheets.length) return { paper: toPaper(g, sheets[0]!), problem: null };
  const clipped = largestComponent(g, (i) => white(i) && max(i) >= CLIP);
  if (clipped.length >= minCells)
    return { paper: null, problem: "The paper is too bright to read. Tilt it a little away from the light." };
  return { paper: null, problem: "No white paper found. Hold a plain white sheet beside your face, or tap it." };
}

/** Tap-to-pick fallback: grows the paper region from the tapped point. */
export function paperAt(img: Pixels, x: number, y: number): PaperResult {
  const g = grid(img);
  const seed = Math.min(g.rows - 1, Math.floor(y / g.size)) * g.cols + Math.min(g.cols - 1, Math.floor(x / g.size));
  const s = g.lab[seed]!;
  if (s[0] < 45) return { paper: null, problem: "That spot looks too dark for white paper. Tap the paper itself." };
  const near = (i: number) => {
    const l = g.lab[i]!;
    return Math.hypot(l[0] - s[0], l[1] - s[1], l[2] - s[2]) < 10 && chroma(l) < 30;
  };
  const comp = largestComponent(g, near, seed);
  if (comp.length < 6) return { paper: null, problem: "That area is too small. Tap the middle of the paper." };
  return { paper: toPaper(g, comp), problem: null };
}

/** A corrected copy of the image (sRGB in, sRGB out). */
export function applyGains(img: Pixels, gains: [number, number, number]): Pixels {
  const lut = [0, 1, 2].map((ch) => {
    const t = new Uint8Array(256);
    for (let v = 0; v < 256; v++) t[v] = fromLinear(Math.min(1, toLinear(v) * gains[ch]!));
    return t;
  });
  const out = new Uint8ClampedArray(img.data.length);
  for (let i = 0; i < img.data.length; i += 4) {
    out[i] = lut[0]![img.data[i]!]!;
    out[i + 1] = lut[1]![img.data[i + 1]!]!;
    out[i + 2] = lut[2]![img.data[i + 2]!]!;
    out[i + 3] = img.data[i + 3] ?? 255;
  }
  return { data: out, width: img.width, height: img.height };
}
