"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Chips } from "@/components/Chips";
import { useToast } from "@/components/Toast";
import { deleteAllData, requestAnalysis, saveProfile, useCloset } from "@/lib/closet/store";
import type { Profile } from "@/lib/closet/types";
import { centsToInput, parseDollars } from "@/lib/domain/money";
import { isWears, WEARS } from "@/lib/domain/fit";
import { formatHeight, parseHeight } from "@/lib/domain/height";
import { findPlaces, type Place } from "@/lib/geocode";

type Sizes = { top?: string; waist?: string; inseam?: string; shoe?: string };

const zones = (): string[] => {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "Asia/Kolkata", "UTC"];
  }
};

function formFrom(p: Profile) {
  const sz = (p.sizes ?? {}) as Sizes;
  return {
    top: sz.top ?? "",
    waist: sz.waist ?? "",
    inseam: sz.inseam ?? "",
    shoe: sz.shoe ?? "",
    fit: p.fit_pref,
    wears: p.wears ?? "",
    height: formatHeight(p.height_cm, p.temp_unit as "F" | "C"),
    budget: centsToInput(p.monthly_budget_cents),
    cap: centsToInput(p.paid_monthly_cap_cents),
    stores: p.favorite_stores.join(", "),
    timezone: p.timezone,
    unit: p.temp_unit as "F" | "C",
  };
}

export function SettingsPanel() {
  const s = useCloset();
  const p = s.profile;
  if (s.status !== "ready" || !p) return null;
  return <SettingsForm key={p.updated_at} profile={p} />;
}

function SettingsForm({ profile }: { profile: Profile }) {
  const toast = useToast();
  const router = useRouter();
  const [f, setF] = useState(() => formFrom(profile));
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [cityQ, setCityQ] = useState(profile.city_name ?? "");
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [cityErr, setCityErr] = useState("");
  const [confirm, setConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  const tzList = useMemo(() => {
    const z = zones();
    return z.includes(f.timezone) ? z : [f.timezone, ...z];
  }, [f.timezone]);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  const save = async () => {
    const budget = f.budget.trim() ? parseDollars(f.budget) : 0;
    const cap = f.cap.trim() ? parseDollars(f.cap) : 0;
    if (budget === null || cap === null) return setErr("Enter amounts as numbers, like 150.");
    const height = f.height.trim() ? parseHeight(f.height) : null;
    if (f.height.trim() && height === null) return setErr(`Enter height like 5'9" or 175 cm.`);
    setBusy(true);
    setErr("");
    try {
      await saveProfile({
        sizes: { top: f.top.trim(), waist: f.waist.trim(), inseam: f.inseam.trim(), shoe: f.shoe.trim() },
        fit_pref: f.fit,
        wears: isWears(f.wears) ? f.wears : null,
        height_cm: height,
        monthly_budget_cents: budget,
        paid_monthly_cap_cents: cap,
        favorite_stores: [
          ...new Set(
            f.stores
              .split(",")
              .map((x) => x.trim())
              .filter(Boolean),
          ),
        ].slice(0, 20),
        timezone: f.timezone,
        temp_unit: f.unit,
      });
      toast("Settings saved");
      // New height: refresh the profile's length notes (palette and text only, on the Mac).
      if (height !== profile.height_cm && profile.analysis) void requestAnalysis(true, 0).catch(() => {});
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const search = async () => {
    if (cityQ.trim().length < 2) return setCityErr("Type at least two letters of your city.");
    setCityErr("");
    try {
      const r = await findPlaces(cityQ);
      setPlaces(r);
      if (!r.length) setCityErr("No matches. Check the spelling, or try a nearby bigger city.");
    } catch (e) {
      setCityErr((e as Error).message);
    }
  };

  const choose = async (pl: Place) => {
    try {
      await saveProfile({
        city_name: pl.region ? `${pl.name}, ${pl.region}` : pl.name,
        latitude: pl.latitude,
        longitude: pl.longitude,
        ...(pl.timezone ? { timezone: pl.timezone } : {}),
      });
      setPlaces(null);
      toast("Home city saved");
    } catch (e) {
      setCityErr((e as Error).message);
    }
  };

  return (
    <section className="block" id="settings" aria-labelledby="settings-h">
      <div className="block-head">
        <h2 id="settings-h">Settings</h2>
      </div>

      <h3>Sizes (US)</h3>
      <div className="field-row">
        <label className="field">
          <span>Top</span>
          <input
            type="text"
            value={f.top}
            onChange={(e) => set("top", e.target.value)}
            placeholder="M"
            maxLength={10}
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Waist</span>
          <input
            type="text"
            inputMode="numeric"
            value={f.waist}
            onChange={(e) => set("waist", e.target.value)}
            placeholder="32"
            maxLength={10}
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Inseam</span>
          <input
            type="text"
            inputMode="numeric"
            value={f.inseam}
            onChange={(e) => set("inseam", e.target.value)}
            placeholder="30"
            maxLength={10}
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Shoe</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.shoe}
            onChange={(e) => set("shoe", e.target.value)}
            placeholder="10"
            maxLength={10}
            autoComplete="off"
          />
        </label>
      </div>
      <label className="field">
        <span>Height</span>
        <input
          type="text"
          value={f.height}
          onChange={(e) => set("height", e.target.value)}
          placeholder={f.unit === "C" ? "175 cm" : `5'9"`}
          maxLength={12}
          autoComplete="off"
        />
        <span className="hint">For jacket and hem length notes in your style profile.</span>
      </label>
      <label className="field">
        <span>Clothes I mostly wear</span>
        <select value={f.wears} onChange={(e) => set("wears", e.target.value)} data-testid="wears">
          <option value="">Not set (show every fit)</option>
          {WEARS.map((w) => (
            <option key={w.id} value={w.id}>
              {w.label}
            </option>
          ))}
        </select>
        <span className="hint">Only changes which fit choices you see when adding clothes.</span>
      </label>
      <label className="field">
        <span>Fit preference</span>
        <select value={f.fit} onChange={(e) => set("fit", e.target.value)}>
          <option value="">No preference</option>
          <option value="slim">Slim</option>
          <option value="regular">Regular</option>
          <option value="relaxed">Relaxed</option>
        </select>
      </label>

      <h3>Money</h3>
      <div className="field-row">
        <label className="field">
          <span>Monthly clothing budget ($)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.budget}
            onChange={(e) => set("budget", e.target.value)}
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Paid search cap ($ a month)</span>
          <input
            type="text"
            inputMode="decimal"
            value={f.cap}
            onChange={(e) => set("cap", e.target.value)}
            autoComplete="off"
          />
        </label>
      </div>
      <p className="hint">
        The paid cap stays at $0 unless you want GPT-powered deal hunts. At $0, nothing paid ever runs.
      </p>
      <label className="field">
        <span>Favorite stores</span>
        <input
          type="text"
          value={f.stores}
          onChange={(e) => set("stores", e.target.value)}
          placeholder="Uniqlo, J.Crew, Banana Republic"
          autoComplete="off"
        />
      </label>

      <h3>Place and units</h3>
      <div className="field">
        <label htmlFor="city-q" style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-2)" }}>
          Home city
        </label>
        <div className="color-in">
          <input
            id="city-q"
            type="text"
            value={cityQ}
            onChange={(e) => setCityQ(e.target.value)}
            autoComplete="address-level2"
            placeholder="Boston"
          />
          <button type="button" className="btn sm" onClick={search}>
            Find
          </button>
        </div>
        {profile.city_name && <p className="hint">Saved: {profile.city_name}</p>}
        <p className="err" role="alert">
          {cityErr}
        </p>
        {places && places.length > 0 && (
          <ul className="piece-list" aria-label="Matching cities">
            {places.map((pl) => (
              <li key={`${pl.latitude},${pl.longitude}`}>
                <button type="button" className="link" onClick={() => void choose(pl)}>
                  {pl.name}
                  {pl.region ? `, ${pl.region}` : ""}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="field-row">
        <label className="field">
          <span>Time zone</span>
          <select value={f.timezone} onChange={(e) => set("timezone", e.target.value)}>
            {tzList.map((z) => (
              <option key={z}>{z}</option>
            ))}
          </select>
        </label>
        <fieldset className="field">
          <legend>Temperature</legend>
          <Chips
            label="Temperature"
            options={[
              { id: "F" as const, label: "°F" },
              { id: "C" as const, label: "°C" },
            ]}
            value={f.unit}
            onChange={(u) => set("unit", u)}
          />
        </fieldset>
      </div>

      <p className="err" role="alert">
        {err}
      </p>
      <div className="row">
        <button type="button" className="btn primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : "Save settings"}
        </button>
      </div>

      <h3>Delete all my data</h3>
      <p className="muted small">
        This removes every piece, outfit, wear, photo and setting. It can’t be undone. Type <strong>delete</strong> to
        confirm.
      </p>
      <div className="color-in">
        <label className="sr" htmlFor="confirm-delete">
          Type delete to confirm
        </label>
        <input
          id="confirm-delete"
          type="text"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          autoComplete="off"
        />
        <button
          type="button"
          className="btn danger"
          disabled={confirm.trim().toLowerCase() !== "delete" || deleting}
          onClick={async () => {
            setDeleting(true);
            try {
              await deleteAllData();
              toast("Everything is deleted");
              router.push("/today");
            } catch (e) {
              toast((e as Error).message);
              setDeleting(false);
            }
          }}
        >
          {deleting ? "Deleting…" : "Delete everything"}
        </button>
      </div>
    </section>
  );
}
