import { describe, expect, it } from "vitest";
import { parsePlaces } from "./geocode";

describe("parsePlaces", () => {
  it("keeps the useful fields and drops junk", () => {
    const out = parsePlaces({
      results: [
        {
          name: "Boston",
          latitude: 42.36,
          longitude: -71.06,
          timezone: "America/New_York",
          admin1: "Massachusetts",
          country: "United States",
        },
        { name: "Bad" },
      ],
    });
    expect(out).toEqual([
      {
        name: "Boston",
        region: "Massachusetts, United States",
        latitude: 42.36,
        longitude: -71.06,
        timezone: "America/New_York",
      },
    ]);
  });
  it("handles no results", () => expect(parsePlaces({})).toEqual([]));
});
