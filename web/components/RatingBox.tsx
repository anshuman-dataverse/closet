// The verdict in words and every check with its reason (Check my outfit, Would it suit me?).

export type RatingCheck = { key: string; label: string; ok: boolean | null; detail: string };
export type Rating = { verdict: "strong" | "works" | "rethink"; headline: string; checks: RatingCheck[] };

export function parseRating(raw: unknown): Rating | null {
  const r = raw as Partial<Rating> | null;
  if (!r || !r.verdict || !Array.isArray(r.checks)) return null;
  return { verdict: r.verdict, headline: String(r.headline ?? ""), checks: r.checks };
}

const MARK = { true: "✓", false: "✕", null: "–" } as const;

/** The verdict in words and every check with its reason (no made-up percentages). */
export function RatingBox({ r, label = "Outfit check" }: { r: Rating; label?: string }) {
  const cls = r.verdict === "strong" ? "good" : r.verdict === "works" ? "wait" : "bad";
  return (
    <section className={`verdict ${cls}`} aria-label={label} data-testid="outfit-check">
      <p>
        <span className="v-word">
          {r.verdict === "strong" ? "Strong" : r.verdict === "works" ? "It works" : "Rethink it"}
        </span>
      </p>
      <p className="small">{r.headline}</p>
      <ul className="checks">
        {r.checks.map((c) => (
          <li key={c.key} className={c.ok === false ? "fail" : c.ok === null ? "skip" : "pass"}>
            <span aria-hidden="true">{MARK[String(c.ok) as "true" | "false" | "null"]}</span>{" "}
            <strong>{c.label}:</strong> {c.detail}
          </li>
        ))}
      </ul>
    </section>
  );
}
