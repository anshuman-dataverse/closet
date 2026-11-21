// Pinked color swatches (SPEC 7), shared by the Style profile and the public palette checker.
export type SwatchItem = { name: string; hex: string; why?: string };

export function Swatches({ title, items, id }: { title: string; items: SwatchItem[]; id: string }) {
  if (!items.length) return null;
  return (
    <>
      <h3 id={id}>{title}</h3>
      <ul className="swatches" aria-labelledby={id}>
        {items.map((c) => (
          <li key={c.name} className="swatch">
            <span className="sw-wrap" aria-hidden="true">
              <span className="chip-sw" style={{ "--sw": c.hex } as React.CSSProperties} />
            </span>
            <span>{c.name}</span>
            {c.why && <span className="sw-why">{c.why}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
