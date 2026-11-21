"use client";
/* eslint-disable @next/next/no-img-element -- signed private URLs */

import { useRef, useState } from "react";
import { Chips } from "@/components/Chips";
import { Swatches } from "@/components/Swatches";
import { useToast } from "@/components/Toast";
import { useWorkerStatus } from "@/components/WorkerStatus";
import { addStylePhoto, removeStylePhoto, requestAnalysis, saveProfile, useCloset } from "@/lib/closet/store";
import type { StylePhoto } from "@/lib/closet/types";
import { type Analysis, canAnalyze, KIND_LABEL, nextKind, parseAnalysis, type PhotoKind } from "@/lib/domain/analysis";
import { useSignedUrl } from "@/lib/signed-urls";

const KINDS = (Object.keys(KIND_LABEL) as PhotoKind[]).map((id) => ({ id, label: KIND_LABEL[id] }));
const OFFLINE = "Your Mac is offline. This will run when it’s back.";

function Photo({ p }: { p: StylePhoto }) {
  const toast = useToast();
  const url = useSignedUrl(p.photo_path.replace(/\.jpg$/, "_thumb.jpg"));
  const [armed, setArmed] = useState(false);
  const label = KIND_LABEL[p.kind as PhotoKind] ?? p.kind;
  return (
    <li>
      {url ? <img src={url} alt={`Style photo: ${label}`} /> : <span className="ph">{label}</span>}
      <span className="pill" style={{ position: "absolute", left: 5, bottom: 5, background: "var(--card)" }}>
        {label}
      </span>
      <button
        type="button"
        className={`x${armed ? " confirm" : ""}`}
        aria-label={armed ? `Tap again to remove the ${label} photo` : `Remove the ${label} photo`}
        onBlur={() => setArmed(false)}
        onClick={async () => {
          if (!armed) return setArmed(true);
          try {
            await removeStylePhoto(p.id);
          } catch (e) {
            toast((e as Error).message);
          }
        }}
      >
        {armed ? "Remove?" : "×"}
      </button>
    </li>
  );
}

function WhatSuitsYou({ a }: { a: Analysis }) {
  const s = useCloset();
  const toast = useToast();
  const worker = useWorkerStatus();
  const [busy, setBusy] = useState(false);
  const p = s.profile;

  const change = async (field: "undertone_override" | "contrast_override", value: string) => {
    setBusy(true);
    try {
      await saveProfile({ [field]: value || null });
      if (worker.offline) toast(OFFLINE);
      else {
        const done = await requestAnalysis(true, 30_000);
        if (!done) toast("Saved. Your colors will update when your Mac finishes.");
        else if (done.status === "failed") toast("Your Mac couldn’t update the colors. Try again.");
      }
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const pill = (k: "undertone" | "contrast" | "depth") => {
    const v = a.effective[k];
    return v ? `${v[0]!.toUpperCase()}${v.slice(1)} ${k}` : "";
  };

  return (
    <section className="block" aria-labelledby="suits-h">
      <div className="block-head">
        <h2 id="suits-h">What suits you</h2>
      </div>
      <p className="lead">{a.summary}</p>
      <div className="pills">
        {(["undertone", "depth", "contrast"] as const).map((k) => (
          <span key={k} className="pill">
            {pill(k)}
          </span>
        ))}
      </div>
      {a.confidence_note && <p className="err">{a.confidence_note}</p>}
      {a.borderline.map((b) => (
        <p key={b} className="muted small">
          {b}
        </p>
      ))}
      <Swatches title="Your best colors" items={a.best} id="best-h" />
      <Swatches title="Easy neutrals" items={a.neutrals} id="neutrals-h" />
      <Swatches title="Use carefully" items={a.careful} id="careful-h" />

      {a.fit_notes.length > 0 && (
        <>
          <h3>Fit notes</h3>
          <dl className="fitnotes">
            {a.fit_notes.map((n) => (
              <div key={n.area}>
                <dt>{n.area}</dt>
                <dd>{n.advice}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      <h3>Glasses, sunglasses and hair</h3>
      {a.face.shape ? (
        <dl className="fitnotes" aria-label="Face shape tips">
          <div>
            <dt>Face shape</dt>
            <dd>
              {a.face.shape[0]!.toUpperCase() + a.face.shape.slice(1)}. {a.face.why}
            </dd>
          </div>
          <div>
            <dt>Frames</dt>
            <dd>{a.face.frames?.join(". ")}.</dd>
          </div>
          <div>
            <dt>Hair</dt>
            <dd>{a.face.hair?.join(". ")}.</dd>
          </div>
        </dl>
      ) : (
        <p className="muted">{a.face.note}</p>
      )}
      <p className="muted small">These are common style guidelines, not rules. Wear what you like.</p>

      {Object.keys(a.occasion_tips).length > 0 && (
        <>
          <h3>By occasion</h3>
          <dl className="facts">
            {["office", "college", "party", "home"]
              .filter((k) => a.occasion_tips[k])
              .map((k) => [k, a.occasion_tips[k]!] as const)
              .map(([k, v]) => (
                <div key={k}>
                  <dt>{k[0]!.toUpperCase() + k.slice(1)}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
          </dl>
        </>
      )}

      <h3>Change</h3>
      <div className="field-row">
        <label className="field">
          <span>Undertone</span>
          <select
            value={p?.undertone_override ?? ""}
            disabled={busy}
            onChange={(e) => void change("undertone_override", e.target.value)}
          >
            <option value="">From photos ({a.computed.undertone})</option>
            {["warm", "cool", "neutral", "olive"].map((v) => (
              <option key={v} value={v}>
                {v[0]!.toUpperCase() + v.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Contrast</span>
          <select
            value={p?.contrast_override ?? ""}
            disabled={busy}
            onChange={(e) => void change("contrast_override", e.target.value)}
          >
            <option value="">From photos ({a.computed.contrast})</option>
            {["low", "medium", "high"].map((v) => (
              <option key={v} value={v}>
                {v[0]!.toUpperCase() + v.slice(1)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted small">{a.note}</p>
    </section>
  );
}

export function StyleSection() {
  const s = useCloset();
  const toast = useToast();
  const worker = useWorkerStatus();
  const fileRef = useRef<HTMLInputElement>(null);
  const kinds = s.stylePhotos.map((p) => p.kind);
  const [kind, setKind] = useState<PhotoKind | null>(null);
  const chosen = kind ?? nextKind(kinds);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState("");
  const analysis = parseAnalysis(s.profile?.analysis);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      await addStylePhoto(chosen, file);
      setKind(null);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const analyze = async () => {
    if (worker.offline) {
      setStatus(OFFLINE);
      void requestAnalysis(false, 0).catch(() => {});
      return;
    }
    setStatus("Your Mac is reading your photos…");
    try {
      const done = await requestAnalysis();
      setStatus(
        !done
          ? "Still working. Your colors will appear here when your Mac finishes."
          : done.status === "failed"
            ? (done.error ?? "Your Mac couldn’t read these photos. Try a clearer face close-up in daylight.")
            : "",
      );
    } catch {
      setStatus("Couldn’t ask your Mac. Check your connection and try again.");
    }
  };

  return (
    <>
      <section className="block" style={{ marginTop: 4 }} aria-labelledby="photos-h">
        <div className="block-head">
          <h2 id="photos-h">Style photos</h2>
          <span className="muted small">{s.stylePhotos.length} of 6</span>
        </div>
        <p className="muted" style={{ maxWidth: "62ch", margin: 0 }}>
          Up to 6: front, side and back in fitted clothes, plus a face close-up in daylight with no filter.
        </p>
        <ul className="me-photos" aria-label="Your style photos">
          {s.stylePhotos.map((p) => (
            <Photo key={p.id} p={p} />
          ))}
        </ul>
        {s.status === "ready" && s.stylePhotos.length < 6 && (
          <>
            <Chips label="Photo type" options={KINDS} value={chosen} onChange={setKind} wrap />
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              data-testid="style-photo-input"
              onChange={(e) => {
                void upload(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <div className="row">
              <button type="button" className="btn" onClick={() => fileRef.current?.click()} disabled={uploading}>
                {uploading ? "Adding…" : `Add a ${KIND_LABEL[chosen].toLowerCase()} photo`}
              </button>
            </div>
          </>
        )}
        <div className="row">
          <button type="button" className="btn primary" disabled={!canAnalyze(kinds)} onClick={analyze}>
            {analysis ? "Analyze again" : "Analyze my photos"}
          </button>
          {!canAnalyze(kinds) && <span className="muted small">Add a face close-up and a front photo first.</span>}
        </div>
        {status && (
          <p className={`muted${status.endsWith("…") ? " thinking" : ""}`} role="status">
            {status}
          </p>
        )}
        <p className="muted small privacy">Your photos are analyzed on your Mac and never sent to an AI service.</p>
      </section>
      {analysis && <WhatSuitsYou a={analysis} />}
    </>
  );
}
