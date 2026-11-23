"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Chips } from "@/components/Chips";
import { useToast } from "@/components/Toast";
import { addSamples, deleteAllData, removeSamples, requestAnalysis, saveProfile, useCloset } from "@/lib/closet/store";
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

type Section = "sizes" | "shopping" | "place";
const SECTION_OF: Record<keyof ReturnType<typeof formFrom>, Section> = {
  top: "sizes",
  waist: "sizes",
  inseam: "sizes",
  shoe: "sizes",
  fit: "sizes",
  wears: "sizes",
  height: "sizes",
  budget: "shopping",
  cap: "shopping",
  stores: "shopping",
  timezone: "place",
  unit: "place",
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
  // Keyed on the user, not on updated_at: saving as you type must not remount the form.
  return <SettingsForm key={p.user_id} profile={p} />;
}

function SettingsForm({ profile }: { profile: Profile }) {
  const toast = useToast();
  const [f, setF] = useState(() => formFrom(profile));
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState("");
  const last = useRef(JSON.stringify(formFrom(profile)));
  const [cityQ, setCityQ] = useState(profile.city_name ?? "");
  const [places, setPlaces] = useState<Place[] | null>(null);
  const [cityErr, setCityErr] = useState("");
  const tzList = useMemo(() => {
    const z = zones();
    return z.includes(f.timezone) ? z : [f.timezone, ...z];
  }, [f.timezone]);
  // The save status shows in the section you last changed.
  const [where, setWhere] = useState<Section>("sizes");
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => {
    setWhere(SECTION_OF[k]);
    setSaved(""); // a new change isn't saved yet
    setF((x) => ({ ...x, [k]: v }));
  };

  // Saves on its own a moment after you stop typing. Invalid entries say what to fix and aren't saved.
  const save = async (snapshot: string) => {
    const budget = f.budget.trim() ? parseDollars(f.budget) : 0;
    const cap = f.cap.trim() ? parseDollars(f.cap) : 0;
    if (budget === null || cap === null) return setErr("Enter amounts as numbers, like 150.");
    const height = f.height.trim() ? parseHeight(f.height) : null;
    if (f.height.trim() && height === null) return setErr(`Enter height like 5'9" or 175 cm.`);
    setErr("");
    setSaved("Saving…");
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
      last.current = snapshot;
      setSaved("Saved");
      // New height: refresh the profile's length notes (palette and text only, on the Mac).
      if (height !== profile.height_cm && profile.analysis) void requestAnalysis(true, 0).catch(() => {});
    } catch (e) {
      setSaved("");
      setErr((e as Error).message);
    }
  };
  const snapshot = JSON.stringify(f);
  useEffect(() => {
    if (snapshot === last.current) return;
    const t = setTimeout(() => void save(snapshot), 700);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- save reads the current form
  }, [snapshot]);

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
      if (pl.timezone) {
        // Saved with the city: show it, and don't count it as an unsaved change.
        const tz = pl.timezone;
        setF((x) => {
          const next = { ...x, timezone: tz };
          if (last.current === JSON.stringify(x)) last.current = JSON.stringify(next);
          return next;
        });
      }
      toast("Home city saved");
    } catch (e) {
      setCityErr((e as Error).message);
    }
  };

  const status = (sec: Section) =>
    where !== sec ? null : (
      <>
        {err && (
          <p className="err" role="alert">
            {err}
          </p>
        )}
        {saved && !err && (
          <p className="hint" role="status">
            {saved}
          </p>
        )}
      </>
    );

  return (
    <>
      <section className="block" id="sizes" aria-labelledby="sizes-h">
        <div className="block-head">
          <h2 id="sizes-h">Sizes and fit</h2>
        </div>
        <p className="hint">Hunts and Would it suit me? use these. Changes save on their own.</p>

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

        {status("sizes")}
      </section>

      <section className="block" id="shopping" aria-labelledby="shopping-h">
        <div className="block-head">
          <h2 id="shopping-h">Shopping and money</h2>
        </div>
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

        <h3>Sample pieces</h3>
        <SamplesRow />
        {status("shopping")}
      </section>

      <section className="block" id="place" aria-labelledby="place-h">
        <div className="block-head">
          <h2 id="place-h">Place and units</h2>
        </div>
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

        {status("place")}
      </section>
    </>
  );
}

/** At the bottom of the page, under Account: typing "delete" is the confirmation. */
export function DeleteAll() {
  const toast = useToast();
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  return (
    <>
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
    </>
  );
}

function SamplesRow() {
  const s = useCloset();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const n = s.items.filter((i) => i.is_sample).length;
  const run = async (fn: () => Promise<number>, done: (k: number) => string) => {
    setBusy(true);
    try {
      toast(done(await fn()));
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="field">
      <p className="hint">
        Try ideas, looks and What’s missing with a sample closet. Sample pieces show a “Sample” badge and never count as
        spend.
      </p>
      {n ? (
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => void run(removeSamples, (k) => `Removed ${k} sample pieces`)}
        >
          Remove sample pieces ({n})
        </button>
      ) : (
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => void run(addSamples, (k) => `Added ${k} sample pieces`)}
        >
          Add sample pieces
        </button>
      )}
    </div>
  );
}
