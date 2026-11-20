"use client";

import { useRef } from "react";
import { type Occasion, OCCASIONS, stepOccasion } from "@/lib/occasions";
import { useOccasion } from "@/lib/use-occasion";

/** The Today hero: four stacked words, radiogroup semantics, remembered on this device. */
export function OccasionPicker() {
  const [occ, setOcc] = useOccasion();
  const refs = useRef<Partial<Record<Occasion, HTMLButtonElement | null>>>({});

  return (
    <>
      <p className="hero-q" id="occ-label">
        Dressing for
      </p>
      <div
        className="occ-words"
        role="radiogroup"
        aria-labelledby="occ-label"
        onKeyDown={(e) => {
          const next = stepOccasion(occ, e.key);
          if (next) {
            e.preventDefault();
            setOcc(next);
            refs.current[next]?.focus();
          }
        }}
      >
        {OCCASIONS.map((o) => (
          <button
            key={o.id}
            ref={(el) => {
              refs.current[o.id] = el;
            }}
            type="button"
            role="radio"
            className="occ-word"
            aria-checked={occ === o.id}
            tabIndex={occ === o.id ? 0 : -1}
            onClick={() => setOcc(o.id)}
          >
            {o.label.toLowerCase()}
          </button>
        ))}
      </div>
    </>
  );
}
