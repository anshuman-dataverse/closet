import { describe, expect, it } from "vitest";
import { formatHeight, parseHeight } from "./height";

describe("height", () => {
  it("parses the ways people type it", () => {
    expect(parseHeight(`5'9"`)).toBe(175);
    expect(parseHeight("5′9″")).toBe(175);
    expect(parseHeight("5 ft 9")).toBe(175);
    expect(parseHeight("6'")).toBe(183);
    expect(parseHeight("69 in")).toBe(175);
    expect(parseHeight("175")).toBe(175);
    expect(parseHeight("175 cm")).toBe(175);
    expect(parseHeight("1.75 m")).toBe(175);
    expect(parseHeight("")).toBeNull();
    expect(parseHeight("tall")).toBeNull();
    expect(parseHeight("400")).toBeNull();
  });
  it("formats for the chosen units", () => {
    expect(formatHeight(175, "F")).toBe(`5'9"`);
    expect(formatHeight(175, "C")).toBe("175 cm");
    expect(formatHeight(null, "F")).toBe("");
  });
});
