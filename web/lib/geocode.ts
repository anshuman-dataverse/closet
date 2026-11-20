// Home city lookup through Open-Meteo's free geocoding API (no key, called from the browser).

export type Place = { name: string; region: string; latitude: number; longitude: number; timezone: string };

export const GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search";

export function parsePlaces(json: unknown): Place[] {
  const results = (json as { results?: unknown[] } | null)?.results;
  if (!Array.isArray(results)) return [];
  return results
    .map((r) => r as Record<string, unknown>)
    .filter((r) => typeof r.name === "string" && typeof r.latitude === "number" && typeof r.longitude === "number")
    .map((r) => ({
      name: r.name as string,
      region: [r.admin1, r.country].filter((x) => typeof x === "string" && x).join(", "),
      latitude: r.latitude as number,
      longitude: r.longitude as number,
      timezone: typeof r.timezone === "string" ? r.timezone : "",
    }))
    .slice(0, 5);
}

export async function findPlaces(query: string, signal?: AbortSignal): Promise<Place[]> {
  const q = new URLSearchParams({ name: query.trim(), count: "5", language: "en", format: "json" });
  const res = await fetch(`${GEOCODE_URL}?${q}`, { signal });
  if (!res.ok) throw new Error("City search isn’t working right now. Try again in a minute.");
  return parsePlaces(await res.json());
}
