// Synthetic "face" photos for the /colors e2e tests (no real faces). Layout matches the fake detector.
import sharp from "sharp";

const W = 400, H = 500; // prettier-ignore
function make({ paper = false, cast = [1, 1, 1], corner = null } = {}) {
  const buf = Buffer.alloc(W * H * 3);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      let c = [150, 150, 150];
      if (x >= 100 && x < 300 && y >= 150 && y < 430) c = [200, 160, 130];
      else if (x >= 110 && x < 290 && y >= 60 && y < 150) c = [35, 28, 24];
      else if (paper && x >= 318 && x < 392 && y >= 180 && y < 440) c = [235, 235, 235];
      if (corner && x < 4 && y < 4) c = corner;
      const i = (y * W + x) * 3;
      for (let k = 0; k < 3; k++)
        buf[i + k] = Math.round(
          Math.min(1, (c[k] / 255) ** 2.2 * (corner && x < 4 && y < 4 ? 1 : cast[k])) ** (1 / 2.2) * 255,
        );
    }
  return sharp(buf, { raw: { width: W, height: H, channels: 3 } }).png();
}
const out = new URL("../tests/e2e/fixtures/", import.meta.url).pathname;
await make({ paper: true, cast: [1, 0.85, 0.6] }).toFile(out + "colors-warm-paper.png");
await make({ paper: false, cast: [1, 0.85, 0.6] }).toFile(out + "colors-no-paper.png");
await make({ corner: [255, 0, 0] }).toFile(out + "colors-two-faces.png");
console.log("colors fixtures written");
