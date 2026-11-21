// Face shape from Face Mesh proportions. A port of worker/closet_worker/vision/face_shape.py.
import { T } from "./data";
import { CHIN, LEFT, NOSE, RIGHT, TOP } from "./skin";
import type { Point } from "./types";

const JAW_L = 172,
  JAW_R = 397,
  FH_L = 103,
  FH_R = 332;
const dist = (a: Point, b: Point) => Math.hypot(a[0] - b[0], a[1] - b[1]);

export type FaceRatios = { length: number; jaw: number; forehead: number; yaw: number };

export function faceRatios(p: Point[]): FaceRatios {
  const cheek = dist(p[LEFT]!, p[RIGHT]!);
  const mid = (p[LEFT]![0] + p[RIGHT]![0]) / 2;
  return {
    length: dist(p[TOP]!, p[CHIN]!) / cheek,
    jaw: dist(p[JAW_L]!, p[JAW_R]!) / cheek,
    forehead: dist(p[FH_L]!, p[FH_R]!) / cheek,
    yaw: Math.abs(p[NOSE]![0] - mid) / cheek,
  };
}

export function classifyFace(r: FaceRatios): string | null {
  const f = T.face_shape as Record<string, number>;
  if (r.yaw > f.max_yaw!) return null;
  if (r.length >= f.oblong_min_length!) return "oblong";
  if (r.length < f.round_max_length! && r.jaw >= f.round_jaw!) return "round";
  if (r.length < f.square_max_length! && r.jaw >= f.wide_jaw!) return "square";
  if (r.forehead >= f.wide_forehead! && r.jaw < f.narrow_jaw!) return "heart";
  if (r.forehead < f.narrow_forehead! && r.jaw < f.narrow_jaw!) return "diamond";
  return "oval";
}

/** Majority over photos; ties go to the straightest photo. */
export function voteShape(rs: FaceRatios[]): string | null {
  const votes = rs.map((r) => ({ s: classifyFace(r), yaw: r.yaw }));
  const counts = new Map<string, number>();
  for (const v of votes) if (v.s) counts.set(v.s, (counts.get(v.s) ?? 0) + 1);
  if (!counts.size) return null;
  const top = Math.max(...counts.values());
  const tied = votes.filter((v) => v.s && counts.get(v.s) === top).sort((a, b) => a.yaw - b.yaw);
  return tied[0]!.s;
}
