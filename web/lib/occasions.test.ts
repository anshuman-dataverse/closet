import { describe, expect, it } from "vitest";
import { isOccasion, stepOccasion } from "./occasions";

describe("occasion picker keys", () => {
  it("moves and wraps", () => {
    expect(stepOccasion("office", "ArrowDown")).toBe("college");
    expect(stepOccasion("home", "ArrowDown")).toBe("office");
    expect(stepOccasion("office", "ArrowUp")).toBe("home");
    expect(stepOccasion("party", "Home")).toBe("office");
    expect(stepOccasion("office", "End")).toBe("home");
    expect(stepOccasion("office", "a")).toBeNull();
  });
  it("validates stored values", () => {
    expect(isOccasion("party")).toBe(true);
    expect(isOccasion("gym")).toBe(false);
  });
});
