import { describe, expect, it } from "vitest";
import { budgetRange, centsToInput, formatCents, parseDollars } from "./money";

describe("money", () => {
  it("formats like the spec", () => {
    expect(formatCents(3500)).toBe("$35");
    expect(formatCents(3950)).toBe("$39.50");
    expect(formatCents(120000)).toBe("$1,200");
    expect(formatCents(5)).toBe("$0.05");
    expect(formatCents(null)).toBe("$0");
  });
  it("parses what people type", () => {
    expect(parseDollars("39.5")).toBe(3950);
    expect(parseDollars("$1,200")).toBe(120000);
    expect(parseDollars("0.1")).toBe(10);
    expect(parseDollars("")).toBeNull();
    expect(parseDollars("abc")).toBeNull();
    expect(parseDollars("-5")).toBeNull();
    expect(centsToInput(3950)).toBe("39.5");
  });
  it("budget ranges", () => {
    expect(budgetRange(2500, 6000)).toBe("$25 to $60");
    expect(budgetRange(6000, 2500)).toBe("$25 to $60");
    expect(budgetRange(null, 6000)).toBe("up to $60");
    expect(budgetRange(2500, null)).toBe("from $25");
  });
});
