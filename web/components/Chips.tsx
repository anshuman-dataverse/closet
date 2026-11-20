"use client";

/** A row of pill chips. Single-select when `value` is a string, multi-select when it's an array. */
export function Chips<T extends string>({
  label,
  options,
  value,
  onChange,
  wrap = false,
}: {
  label: string;
  options: readonly { id: T; label: string }[];
  value: T | readonly T[];
  onChange: (next: T) => void;
  wrap?: boolean;
}) {
  const on = (id: T) => (Array.isArray(value) ? value.includes(id) : value === id);
  return (
    <div className={`chips${wrap ? " wrap-chips" : ""}`} role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} type="button" className="chip" aria-pressed={on(o.id)} onClick={() => onChange(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export const toggle = <T,>(list: readonly T[], v: T): T[] =>
  list.includes(v) ? list.filter((x) => x !== v) : [...list, v];
