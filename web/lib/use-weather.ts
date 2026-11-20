"use client";

import { useEffect, useState } from "react";
import type { Profile } from "@/lib/closet/types";
import { getWeather, type Weather } from "@/lib/weather";

/** Today's weather for the profile's home city, or null (no city yet, or the forecast is unavailable). */
export function useWeather(profile: Profile | null, day: string): Weather | null {
  const [w, setW] = useState<{ key: string; value: Weather | null } | null>(null);
  const lat = profile?.latitude;
  const lon = profile?.longitude;
  const tz = profile?.timezone ?? "America/New_York";
  const unit = (profile?.temp_unit === "C" ? "C" : "F") as "F" | "C";
  const key = lat != null && lon != null && day ? `${lat},${lon},${unit},${day}` : "";

  useEffect(() => {
    if (!key || lat == null || lon == null) return;
    let live = true;
    void getWeather({ latitude: lat, longitude: lon, timezone: tz, unit, day }).then((value) => {
      if (live) setW({ key, value });
    });
    return () => {
      live = false;
    };
  }, [key, lat, lon, tz, unit, day]);

  return w && w.key === key ? w.value : null;
}
