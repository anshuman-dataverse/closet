// Generates the PWA and Apple icons from scripts/icon.svg. Run: pnpm icons
import sharp from "sharp";
import { readFile } from "node:fs/promises";

const svg = await readFile(new URL("./icon.svg", import.meta.url));
const out = (p) => new URL(`../${p}`, import.meta.url).pathname;
const render = (size) => sharp(svg, { density: 300 }).resize(size, size).png();

await render(192).toFile(out("public/icons/icon-192.png"));
await render(512).toFile(out("public/icons/icon-512.png"));
await render(180).toFile(out("app/apple-icon.png"));
await render(64).toFile(out("app/icon.png"));
// Maskable: keep the hanger inside the 80% safe zone.
const inner = await render(400).toBuffer();
await sharp({ create: { width: 512, height: 512, channels: 4, background: "#1A2142" } })
  .composite([{ input: inner, gravity: "center" }])
  .png()
  .toFile(out("public/icons/maskable-512.png"));
console.log("icons written");
