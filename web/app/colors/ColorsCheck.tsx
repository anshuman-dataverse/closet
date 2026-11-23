"use client";
/* eslint-disable @next/next/no-img-element -- local blob previews; nothing is uploaded */

import { useEffect, useRef, useState } from "react";
import { Swatches } from "@/components/Swatches";
import { createBrowserClient } from "@supabase/ssr";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "@/lib/env";
import { buildAnalysis } from "@/lib/style/build";
import { applyGains, findPaper, type Paper, paperAt } from "@/lib/style/calibrate";
import { combine, type FaceRead } from "@/lib/style/combine";
import { getDetector } from "@/lib/style/detector";
import { faceRatios } from "@/lib/style/face-shape";
import { decodePhoto } from "@/lib/style/image";
import { checkBody, checkFace, faceBox } from "@/lib/style/quality";
import { lightingNote, readSkin } from "@/lib/style/skin";
import type { BodyRatios } from "@/lib/style/body";
import type { Pixels, Point } from "@/lib/style/types";

type FaceShot = {
  id: string;
  url: string;
  pixels: Pixels;
  pts: Point[];
  paper: Paper | null;
  paperProblem: string | null;
  /** An auto-detected paper is only used after you confirm it; a tapped one counts as confirmed. */
  confirmed: boolean;
  skipPaper: boolean;
};

const cap = (s: string) => s.slice(0, 1).toUpperCase() + s.slice(1);

function readOf(s: FaceShot): FaceRead {
  const use = s.paper && s.confirmed ? s.paper : null;
  const img = use ? applyGains(s.pixels, use.gains) : s.pixels;
  const r = readSkin(img, s.pts);
  return {
    lab: r.lab,
    hairL: r.hairL,
    ratios: faceRatios(s.pts),
    calibrated: !!use,
    lighting: lightingNote(img, r.facePixels, !!use),
  };
}

export function ColorsCheck() {
  const [faces, setFaces] = useState<FaceShot[]>([]);
  const [body, setBody] = useState<{ url: string; ratios: BodyRatios } | null>(null);
  const [busy, setBusy] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [show, setShow] = useState(false);
  const [tentative, setTentative] = useState(false);
  const [over, setOver] = useState<{ undertone?: string; contrast?: string }>({});
  const [owner, setOwner] = useState(false);
  const [saved, setSaved] = useState("");
  const faceInput = useRef<HTMLInputElement>(null);
  const bodyInput = useRef<HTMLInputElement>(null);

  // Only the signed-in owner gets "Use this in my profile". Visitors have no session.
  useEffect(() => {
    if (!SUPABASE_URL) return;
    const db = createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    void db.auth.getUser().then(({ data }) => setOwner(!!data.user));
  }, []);

  const addFace = async (file: File | undefined) => {
    if (!file) return;
    setProblems([]);
    setBusy("Checking your photo on this device…");
    try {
      const det = await getDetector();
      const { canvas, pixels, url } = await decodePhoto(file);
      const found = await det.faces(canvas);
      const check = checkFace(pixels, found);
      if (!check.ok) {
        URL.revokeObjectURL(url);
        setProblems(check.problems);
        return;
      }
      const pts = found[0]!;
      const { paper, problem } = findPaper(pixels, faceBox(pts));
      setFaces((f) => [
        ...f,
        { id: crypto.randomUUID(), url, pixels, pts, paper, paperProblem: problem, confirmed: false, skipPaper: false },
      ]);
      setShow(false);
    } catch (e) {
      setProblems([(e as Error).message || "Something went wrong reading that photo. Try another one."]);
    } finally {
      setBusy("");
    }
  };

  const addBody = async (file: File | undefined) => {
    if (!file) return;
    setProblems([]);
    setBusy("Checking your full-length photo…");
    try {
      const det = await getDetector();
      const { canvas, url } = await decodePhoto(file);
      const c = checkBody(await det.people(canvas));
      if (!c.ok || !c.ratios) {
        URL.revokeObjectURL(url);
        setProblems(c.problems);
        return;
      }
      setBody({ url, ratios: c.ratios });
    } catch (e) {
      setProblems([(e as Error).message || "Something went wrong reading that photo. Try another one."]);
    } finally {
      setBusy("");
    }
  };

  const tapPaper = (shot: FaceShot, e: React.MouseEvent<HTMLImageElement>) => {
    const el = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - el.left) / el.width) * shot.pixels.width;
    const y = ((e.clientY - el.top) / el.height) * shot.pixels.height;
    const { paper, problem } = paperAt(shot.pixels, x, y);
    setFaces((f) =>
      f.map((s) =>
        s.id === shot.id ? { ...s, paper, paperProblem: problem, confirmed: !!paper, skipPaper: false } : s,
      ),
    );
  };

  const pending = faces.filter((f) => !(f.paper && f.confirmed) && !f.skipPaper);
  const result = faces.length && !pending.length ? combine(faces.map(readOf), body?.ratios ?? null) : null;
  const analysis = result ? buildAnalysis(result.measurements, over) : null;

  const saveToProfile = async () => {
    if (!analysis) return;
    setSaved("Saving…");
    const db = createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    const { data } = await db.auth.getUser();
    if (!data.user) return setSaved("Sign in to Closet first.");
    const { error } = await db
      .from("profiles")
      .update({
        analysis: JSON.parse(JSON.stringify(analysis)),
        analyzed_at: new Date().toISOString(),
        undertone_override: null,
        contrast_override: null,
        depth_override: null,
      })
      .eq("user_id", data.user.id);
    setSaved(error ? "Couldn’t save. Try again." : "Saved to your Style profile.");
  };

  return (
    <>
      <p className="lead">
        See which colors suit your skin, hair and contrast, plus frame and hair tips for your face shape.
      </p>
      <section className="block" aria-labelledby="how-h" style={{ marginTop: 8 }}>
        <h2 id="how-h">For the best read</h2>
        <ul className="piece-list">
          <li>Stand facing a window in daylight. No lamps, no filter, no makeup if you can.</li>
          <li>
            <strong>Hold a plain sheet of white paper</strong> beside your face. It lets the app remove your camera’s
            color cast, which is the biggest source of error.
          </li>
          <li>Take a second photo in different daylight for a more reliable result.</li>
          <li>Optional: a full-length front photo for fit notes.</li>
        </ul>
        <p className="muted small">Your photos stay on this device. Nothing is uploaded or saved.</p>
      </section>

      <section className="block" aria-labelledby="photos-h">
        <div className="block-head">
          <h2 id="photos-h">Your photos</h2>
          <span className="muted small">
            {faces.length} face {faces.length === 1 ? "photo" : "photos"}
          </span>
        </div>
        <ul className="cards" aria-label="Face photos">
          {faces.map((s, k) => {
            const set = (patch: Partial<FaceShot>) =>
              setFaces((f) => f.map((x) => (x.id === s.id ? { ...x, ...patch } : x)));
            const box = s.paper?.box;
            const tapping = !s.paper && !s.skipPaper;
            return (
              <li key={s.id} className="card">
                <div className="wish-top">
                  <div style={{ position: "relative", width: 120, flex: "none" }}>
                    <img
                      src={s.url}
                      alt={`Face photo ${k + 1}`}
                      style={{
                        width: 120,
                        display: "block",
                        borderRadius: 6,
                        cursor: tapping ? "crosshair" : "default",
                      }}
                      onClick={(e) => tapping && tapPaper(s, e)}
                    />
                    {box && (
                      <span
                        aria-hidden="true"
                        data-testid="paper-outline"
                        style={{
                          position: "absolute",
                          left: `${(box.x0 / s.pixels.width) * 100}%`,
                          top: `${(box.y0 / s.pixels.height) * 100}%`,
                          width: `${((box.x1 - box.x0) / s.pixels.width) * 100}%`,
                          height: `${((box.y1 - box.y0) / s.pixels.height) * 100}%`,
                          outline: "3px solid var(--chalk)",
                          borderRadius: 2,
                          pointerEvents: "none",
                        }}
                      />
                    )}
                  </div>
                  <div>
                    <h3>Face photo {k + 1}</h3>
                    {s.paper && s.confirmed ? (
                      <p className="ok" style={{ margin: 0 }}>
                        ✓ White paper confirmed. Color cast corrected.
                      </p>
                    ) : s.paper ? (
                      <>
                        <p style={{ margin: 0 }}>Is the outlined area your sheet of white paper?</p>
                        <div className="row tight">
                          <button type="button" className="btn sm primary" onClick={() => set({ confirmed: true })}>
                            Yes, that’s the paper
                          </button>
                          <button
                            type="button"
                            className="btn sm"
                            onClick={() =>
                              set({ paper: null, paperProblem: "Tap the paper on the photo, or continue without it." })
                            }
                          >
                            No
                          </button>
                        </div>
                      </>
                    ) : s.skipPaper ? (
                      <p className="muted" style={{ margin: 0 }}>
                        Without paper: lower confidence.
                      </p>
                    ) : (
                      <>
                        <p className="err" style={{ margin: 0 }}>
                          {s.paperProblem}
                        </p>
                        <p className="muted small">Tap the paper on the photo, or continue without it.</p>
                        <button type="button" className="btn sm" onClick={() => set({ skipPaper: true })}>
                          Continue without paper
                        </button>
                      </>
                    )}
                    <div className="row tight">
                      <button
                        type="button"
                        className="btn sm ghost"
                        onClick={() => {
                          URL.revokeObjectURL(s.url);
                          setFaces((f) => f.filter((x) => x.id !== s.id));
                        }}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
        <input
          ref={faceInput}
          type="file"
          accept="image/*"
          hidden
          data-testid="face-input"
          onChange={(e) => {
            void addFace(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <input
          ref={bodyInput}
          type="file"
          accept="image/*"
          hidden
          data-testid="body-input"
          onChange={(e) => {
            void addBody(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
        <div className="row">
          <button
            type="button"
            className={`btn${faces.length ? "" : " primary"}`}
            onClick={() => faceInput.current?.click()}
            disabled={!!busy || faces.length >= 4}
          >
            {faces.length ? "Add another face photo" : "Add a face close-up"}
          </button>
          <button type="button" className="btn ghost" onClick={() => bodyInput.current?.click()} disabled={!!busy}>
            {body ? "Replace full-length photo" : "Add a full-length photo (optional)"}
          </button>
        </div>
        {body && <p className="ok">✓ Full-length photo checked. Fit notes added.</p>}
        {busy && (
          <p className="muted thinking" role="status">
            {busy}
          </p>
        )}
        {problems.length > 0 && (
          <div role="alert">
            {problems.map((p) => (
              <p key={p} className="err">
                Retake: {p}
              </p>
            ))}
          </div>
        )}
        {result && !show && (
          <div className="row">
            <button type="button" className="btn primary" onClick={() => setShow(true)}>
              See my colors
            </button>
            {result.askSecond && (
              <span className="muted small">
                A second face photo in different daylight would make this more reliable.
              </span>
            )}
          </div>
        )}
      </section>

      {show && result && result.confidence === "low" && !tentative && (
        <section className="block" aria-labelledby="notyet-h">
          <div className="block-head">
            <h2 id="notyet-h">Not reliable yet</h2>
          </div>
          <p>
            From these photos the read could easily be wrong, so we’re not showing it as your result. Here’s what would
            make it reliable:
          </p>
          <ul className="piece-list" aria-label="Why this result">
            {result.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="muted">
            Best fix: a face close-up by a window in daylight with a plain white sheet of paper beside your face, plus a
            second photo in different daylight.
          </p>
          <div className="row">
            <button type="button" className="btn ghost" onClick={() => setTentative(true)}>
              Show a tentative result anyway
            </button>
          </div>
        </section>
      )}

      {show && analysis && result && (result.confidence !== "low" || tentative) && (
        <section className="block" aria-labelledby="result-h">
          <div className="block-head">
            <h2 id="result-h">{result.confidence === "low" ? "Tentative colors" : "Your colors"}</h2>
          </div>
          {result.confidence === "low" && (
            <p className="err">
              Low confidence: treat this as a guess, not a result. Add a white-paper photo to confirm.
            </p>
          )}
          <p className="lead">{analysis.summary}</p>
          <div className="pills">
            <span className={`pill${result.confidence === "low" ? " err" : ""}`} data-testid="confidence">
              {cap(result.confidence)} confidence
            </span>
            <span className="pill">{cap(analysis.effective.undertone)} undertone</span>
            <span className="pill">{cap(analysis.effective.depth)} depth</span>
            <span className="pill">{cap(analysis.effective.contrast)} contrast</span>
          </div>
          <ul className="piece-list" aria-label="Why this result">
            {result.reasons.map((r) => (
              <li key={r} className="muted small">
                {r}
              </li>
            ))}
            {analysis.borderline.map((b) => (
              <li key={b} className="muted small">
                {b}
              </li>
            ))}
            {analysis.confidence_note && <li className="err small">{analysis.confidence_note}</li>}
          </ul>
          <Swatches title="Your best colors" items={analysis.best} id="c-best-h" />
          <Swatches title="Easy neutrals" items={analysis.neutrals} id="c-neutrals-h" />
          <Swatches title="Use carefully near your face" items={analysis.careful} id="c-careful-h" />

          <h3>Glasses, sunglasses and hair</h3>
          {analysis.face.shape ? (
            <dl className="fitnotes" aria-label="Face shape tips">
              <div>
                <dt>Face shape</dt>
                <dd>
                  {cap(analysis.face.shape)}. {analysis.face.why}
                </dd>
              </div>
              <div>
                <dt>Frames</dt>
                <dd>{analysis.face.frames?.join(". ")}.</dd>
              </div>
              <div>
                <dt>Hair</dt>
                <dd>{analysis.face.hair?.join(". ")}.</dd>
              </div>
            </dl>
          ) : (
            <p className="muted">{analysis.face.note}</p>
          )}
          <h3>Fit notes</h3>
          <dl className="fitnotes">
            {analysis.fit_notes.map((n) => (
              <div key={n.area}>
                <dt>{n.area}</dt>
                <dd>{n.advice}</dd>
              </div>
            ))}
          </dl>
          <p className="muted small">These are common style guidelines, not rules. Wear what you like.</p>

          <h3>Change</h3>
          <div className="field-row">
            <label className="field">
              <span>Undertone</span>
              <select
                value={over.undertone ?? ""}
                onChange={(e) => setOver((o) => ({ ...o, undertone: e.target.value || undefined }))}
              >
                <option value="">From photos ({analysis.computed.undertone})</option>
                {["warm", "cool", "neutral", "olive"].map((v) => (
                  <option key={v} value={v}>
                    {cap(v)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Contrast</span>
              <select
                value={over.contrast ?? ""}
                onChange={(e) => setOver((o) => ({ ...o, contrast: e.target.value || undefined }))}
              >
                <option value="">From photos ({analysis.computed.contrast})</option>
                {["low", "medium", "high"].map((v) => (
                  <option key={v} value={v}>
                    {cap(v)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="muted small">
            This is not a professional color analysis. The color suggestions follow common seasonal color guidance,
            which is a styling convention rather than settled science, and no dataset exists to measure its accuracy.
            Use it as a starting point and trust what you see in the mirror.
          </p>
          <p className="muted small">
            An estimate from your photos, based on common color guidance (CIE L*a*b* skin color, hue angle for
            undertone, ITA° for depth). Skin hue {result.measurements.hue}°, ITA {result.measurements.ita}°, from{" "}
            {result.measurements.photos_used as number}{" "}
            {(result.measurements.photos_used as number) === 1 ? "photo" : "photos"}.
          </p>
          {owner && (
            <div className="row">
              <button type="button" className="btn" onClick={saveToProfile}>
                Use this in my profile
              </button>
              <span className="muted small" role="status">
                {saved}
              </span>
            </div>
          )}
        </section>
      )}
    </>
  );
}
