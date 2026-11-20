import { describe, expect, it } from "vitest";
import { fitWithin } from "./photos";

describe("fitWithin", () => {
  it("shrinks the long edge to the max, keeping the ratio", () => {
    expect(fitWithin(4032, 3024, 1600)).toEqual({ w: 1600, h: 1200 });
    expect(fitWithin(3024, 4032, 480)).toEqual({ w: 360, h: 480 });
  });
  it("never upscales", () => expect(fitWithin(800, 600, 1600)).toEqual({ w: 800, h: 600 }));
});
