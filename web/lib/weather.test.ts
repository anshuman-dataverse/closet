import { describe, expect, it } from "vitest";
import { cacheKey, parseForecast, weatherLine } from "./weather";

describe("weather", () => {
  it("line matches the spec", () => {
    expect(weatherLine({ high: 47.3, low: 38.1, rain_pct: 70, code: 61, unit: "F" })).toBe(
      "38° to 47°F, 70% chance of rain",
    );
    expect(weatherLine({ high: 22, low: 15, rain_pct: 5, code: 1, unit: "C" })).toBe("15° to 22°C");
    expect(weatherLine(null)).toBe("");
  });
  it("parses Open-Meteo daily data", () => {
    const w = parseForecast(
      {
        daily: {
          temperature_2m_max: [47],
          temperature_2m_min: [38],
          precipitation_probability_max: [70],
          weather_code: [61],
        },
      },
      "F",
    );
    expect(w).toEqual({ high: 47, low: 38, rain_pct: 70, code: 61, unit: "F" });
    expect(parseForecast({ daily: {} }, "F")).toBeNull();
    expect(parseForecast(null, "F")).toBeNull();
  });
  it("cache key per place, unit and day", () => {
    expect(cacheKey(42.3584, -71.0598, "F", "2026-11-20")).toBe("closet.weather:42.36,-71.06:F:2026-11-20");
  });
});
