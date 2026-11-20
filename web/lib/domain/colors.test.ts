import { describe, expect, it } from "vitest";
import { colorKey, isDark, safeHex, swatchFor } from "./colors";

describe("colors", () => {
  it("prefers a valid hex, then the named color", () => {
    expect(swatchFor({ color_hex: "#1F2A48", color_name: "Red" })).toBe("#1f2a48");
    expect(swatchFor({ color_name: "Light blue denim" })).toBe("#a9c4e4");
    expect(swatchFor({ color_name: "Gray" })).toBe("#8a8f98");
    expect(swatchFor({ color_name: "Chartreuse" })).toBe("");
  });
  it("rejects bad hex", () => expect(safeHex("red")).toBe(""));
  it("longest name wins", () => expect(colorKey("sky blue shirt")).toBe("sky blue"));
  it("dark detection", () => {
    expect(isDark("#1c1c1e")).toBe(true);
    expect(isDark("#f6f6f3")).toBe(false);
  });
});
