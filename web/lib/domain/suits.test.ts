import { describe, expect, it } from "vitest";

import { readLine, suitsOf } from "./suits";

const result = {
  verdict: "works",
  headline: "It works, with one thing to know: it’s cut relaxed; you prefer slim.",
  checks: [{ key: "fit", label: "Fit", ok: false, detail: "It’s cut relaxed; you prefer slim." }],
  read: {
    from: "link",
    type: "knit polo",
    category: "Tops",
    color: "navy",
    color_source: "store",
    link_note: null,
  },
};

describe("suits", () => {
  it("reads the check from check_result and ignores anything else", () => {
    expect(suitsOf({ suits: result })?.verdict).toBe("works");
    expect(suitsOf({ verdict: "buy", reasons: [] })).toBeNull();
    expect(suitsOf(null)).toBeNull();
  });
  it("says what was read and where the color came from", () => {
    expect(readLine(suitsOf({ suits: result })!.read)).toBe(
      "Read from the store’s page: knit polo in navy (the color the store states).",
    );
    expect(
      readLine({
        ...result.read,
        from: "screenshot",
        color_source: "picture",
        link_note: "Zara blocked the request.",
      } as never),
    ).toBe("Read from your screenshot: knit polo in navy (read from the picture). Zara blocked the request.");
  });
});
