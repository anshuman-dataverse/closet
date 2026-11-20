// Weather (SPEC 5.3): Open-Meteo daily forecast in the profile's units and time zone, cached 1 hour per device.

export type Weather = { high: number; low: number; rain_pct: number; code: number; unit: "F" | "C" };

export const FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
const TTL_MS = 60 * 60 * 1000;

export function weatherLine(w: Weather | null | undefined): string {
  if (!w) return "";
  const range = `${Math.round(w.low)}° to ${Math.round(w.high)}°${w.unit}`;
  return w.rain_pct >= 20 ? `${range}, ${Math.round(w.rain_pct)}% chance of rain` : range;
}

export function parseForecast(json: unknown, unit: "F" | "C"): Weather | null {
  const d = (json as { daily?: Record<string, unknown[]> } | null)?.daily;
  const num = (k: string) => {
    const v = d?.[k]?.[0];
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  };
  const high = num("temperature_2m_max");
  const low = num("temperature_2m_min");
  if (high === null || low === null) return null;
  return { high, low, rain_pct: num("precipitation_probability_max") ?? 0, code: num("weather_code") ?? 0, unit };
}

export const cacheKey = (lat: number, lon: number, unit: string, day: string) =>
  `closet.weather:${lat.toFixed(2)},${lon.toFixed(2)}:${unit}:${day}`;

export async function getWeather(p: {
  latitude: number;
  longitude: number;
  timezone: string;
  unit: "F" | "C";
  day: string;
}): Promise<Weather | null> {
  const key = cacheKey(p.latitude, p.longitude, p.unit, p.day);
  try {
    const hit = JSON.parse(localStorage.getItem(key) ?? "null") as { at: number; w: Weather } | null;
    if (hit && Date.now() - hit.at < TTL_MS) return hit.w;
  } catch {
    /* private mode or bad cache: fetch fresh */
  }
  const q = new URLSearchParams({
    latitude: String(p.latitude),
    longitude: String(p.longitude),
    daily: "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
    timezone: p.timezone,
    temperature_unit: p.unit === "C" ? "celsius" : "fahrenheit",
    forecast_days: "1",
  });
  try {
    const res = await fetch(`${FORECAST_URL}?${q}`);
    if (!res.ok) return null;
    const w = parseForecast(await res.json(), p.unit);
    if (w) {
      try {
        localStorage.setItem(key, JSON.stringify({ at: Date.now(), w }));
      } catch {
        /* ignore */
      }
    }
    return w;
  } catch {
    return null; // Today works without weather
  }
}
