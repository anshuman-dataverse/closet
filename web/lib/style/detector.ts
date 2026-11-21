"use client";
// Face and pose detection in the visitor's browser (MediaPipe WASM, self-hosted). Nothing is uploaded.
import type { PoseLm } from "./body";
import type { Point } from "./types";

export type Detector = {
  faces: (c: HTMLCanvasElement) => Promise<Point[][]>;
  people: (c: HTMLCanvasElement) => Promise<PoseLm[][]>;
};

let cached: Promise<Detector> | null = null;

/** Test seam for e2e only (NEXT_PUBLIC_FAKE_DETECTOR=1 at build time): fixed landmarks, keyed by a corner pixel. */
function fakeDetector(): Detector {
  const corner = (c: HTMLCanvasElement) => Array.from(c.getContext("2d")!.getImageData(0, 0, 1, 1).data);
  const face = (w: number, h: number): Point[] => {
    const p: Point[] = Array.from({ length: 478 }, () => [w / 2, h * 0.6]);
    const set = (i: number, x: number, y: number) => (p[i] = [x * w, y * h]);
    set(234, 0.25, 0.52);
    set(454, 0.75, 0.52);
    set(10, 0.5, 0.3);
    set(152, 0.5, 0.84); // prettier-ignore
    set(50, 0.375, 0.6);
    set(280, 0.625, 0.6);
    set(151, 0.5, 0.38);
    set(1, 0.5, 0.6); // prettier-ignore
    set(172, 0.2925, 0.75);
    set(397, 0.7075, 0.75);
    set(103, 0.285, 0.36);
    set(332, 0.715, 0.36); // prettier-ignore
    return p;
  };
  return {
    faces: async (c) => {
      const [r, g, b] = corner(c);
      if (r! > 240 && g! < 20 && b! < 20) return [face(c.width, c.height), face(c.width, c.height)]; // red: two faces
      if (r! < 20 && g! < 20 && b! > 240) return []; // blue: no face
      return [face(c.width, c.height)];
    },
    people: async () => [],
  };
}

/** MediaPipe logs routine "INFO:" notices through console.error; drop those, keep real errors. */
function quietInfo<T>(fn: () => T): T {
  const orig = console.error;
  console.error = (...a: unknown[]) => {
    if (typeof a[0] === "string" && a[0].startsWith("INFO:")) return;
    orig(...a);
  };
  let out: T;
  try {
    out = fn();
  } catch (e) {
    console.error = orig;
    throw e;
  }
  if (out instanceof Promise) {
    // async model loading logs later: keep filtering until it settles
    return out.finally(() => (console.error = orig)) as T;
  }
  console.error = orig;
  return out;
}

export function getDetector(): Promise<Detector> {
  if (process.env.NEXT_PUBLIC_FAKE_DETECTOR === "1") return Promise.resolve(fakeDetector());
  cached ??= (async () => {
    const { FilesetResolver, FaceLandmarker, PoseLandmarker } = await import("@mediapipe/tasks-vision");
    const files = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
    const face = await quietInfo(() =>
      FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: "/mediapipe/face_landmarker.task", delegate: "CPU" },
        runningMode: "IMAGE",
        numFaces: 3,
      }),
    );
    let pose: Awaited<ReturnType<typeof PoseLandmarker.createFromOptions>> | null = null;
    return {
      faces: async (c) => {
        const r = quietInfo(() => face.detect(c));
        return r.faceLandmarks.map((lm) => lm.map((p) => [p.x * c.width, p.y * c.height] as Point));
      },
      people: async (c) => {
        pose ??= await quietInfo(() =>
          PoseLandmarker.createFromOptions(files, {
            baseOptions: { modelAssetPath: "/mediapipe/pose_landmarker_lite.task", delegate: "CPU" },
            runningMode: "IMAGE",
            numPoses: 2,
          }),
        );
        const r = quietInfo(() => pose!.detect(c));
        return r.landmarks.map((lm) => lm.map((p) => [p.x * c.width, p.y * c.height, p.visibility ?? 0] as PoseLm));
      },
    };
  })();
  cached.catch(() => (cached = null)); // allow a retry after a failed load
  return cached;
}
