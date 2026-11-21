// Copies MediaPipe's WASM runtime into public/ (self-hosted: visitors never fetch it from a CDN)
// and verifies the committed model files. Runs before dev and build.
import { createHash } from "node:crypto";
import { cpSync, mkdirSync, readFileSync } from "node:fs";

const root = new URL("../", import.meta.url).pathname;
mkdirSync(`${root}public/mediapipe/wasm`, { recursive: true });
cpSync(`${root}node_modules/@mediapipe/tasks-vision/wasm`, `${root}public/mediapipe/wasm`, { recursive: true });

const MODELS = {
  "face_landmarker.task": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
  "pose_landmarker_lite.task": "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
};
for (const [name, sha] of Object.entries(MODELS)) {
  const got = createHash("sha256")
    .update(readFileSync(`${root}public/mediapipe/${name}`))
    .digest("hex");
  if (got !== sha) throw new Error(`public/mediapipe/${name} checksum mismatch`);
}
console.log("mediapipe assets ready");
