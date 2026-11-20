import { describe, expect, it } from "vitest";
import { addDays, daysBetween, lastMonths, lastWornText, monthName, shortDate, todayIn } from "./dates";

describe("todayIn", () => {
  // 03:30 UTC on Nov 21 is still Nov 20 in New York.
  const t = new Date("2026-11-21T03:30:00Z");
  it("uses the profile's time zone for the day boundary", () => {
    expect(todayIn("America/New_York", t)).toBe("2026-11-20");
    expect(todayIn("Asia/Kolkata", t)).toBe("2026-11-21");
  });
  it("falls back on a bad zone", () => expect(todayIn("Not/AZone", t)).toMatch(/^\d{4}-\d{2}-\d{2}$/));
});

describe("lastWornText", () => {
  it("matches the spec's phrasing", () => {
    expect(lastWornText(null, "2026-11-20")).toBe("Never worn");
    expect(lastWornText("2026-11-20", "2026-11-20")).toBe("Worn today");
    expect(lastWornText("2026-11-19", "2026-11-20")).toBe("Worn yesterday");
    expect(lastWornText("2026-11-08", "2026-11-20")).toBe("Last worn 12 days ago");
  });
});

describe("calendar math", () => {
  it("crosses month and year ends", () => {
    expect(daysBetween("2026-12-31", "2027-01-01")).toBe(1);
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
  it("short dates add a year only when it differs", () => {
    expect(shortDate("2026-11-17", "2026-11-20")).toBe("Nov 17");
    expect(shortDate("2025-11-17", "2026-11-20")).toBe("Nov 17, 2025");
  });
  it("last 12 months end with this month", () => {
    const m = lastMonths("2026-01-15", 12);
    expect(m).toHaveLength(12);
    expect(m[0]).toBe("2025-02");
    expect(m[11]).toBe("2026-01");
    expect(monthName("2026-11")).toBe("November");
  });
});
