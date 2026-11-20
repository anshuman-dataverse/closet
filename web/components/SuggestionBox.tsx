"use client";

import { useState } from "react";
import type { Form } from "@/components/ItemSheet";
import { useToast } from "@/components/Toast";
import { patchItem } from "@/lib/closet/store";
import type { Item } from "@/lib/closet/types";
import {
  applyChanges,
  parseSuggestion,
  type SuggestableKey,
  statusMessage,
  suggestionChanges,
} from "@/lib/domain/suggestions";

/** "Your Mac suggests…" on a saved piece, with Apply (SPEC 4.2 item sheet). */
export function SuggestionBox({
  item,
  form,
  onApplied,
}: {
  item: Item;
  form: Form;
  onApplied: (f: Partial<Form>) => void;
}) {
  const toast = useToast();
  const sug = parseSuggestion(item.suggestions);
  const changes = sug ? suggestionChanges(form, sug) : [];
  const [picked, setPicked] = useState<SuggestableKey[] | null>(null);
  const chosen = picked ?? changes.filter((c) => c.empty).map((c) => c.key);
  if (!sug || (sug.status !== "not_clothing" && !changes.length)) return null;

  const dismiss = async () => {
    try {
      await patchItem(item.id, { suggestions: null });
    } catch (e) {
      toast((e as Error).message);
    }
  };

  const apply = async () => {
    const next = applyChanges(form, sug, chosen);
    try {
      await patchItem(item.id, {
        suggestions: null,
        type: next.type || null,
        category: next.category,
        color_name: next.color_name || null,
        ...(chosen.includes("color_name") && sug.color_hex ? { color_hex: sug.color_hex } : {}),
        pattern: next.pattern || null,
        occasions: next.occasions,
        formality: next.formality ? Number(next.formality) : null,
        warmth: (next.warmth || null) as Item["warmth"],
        name: next.name.trim() || item.name,
      });
      onApplied(next);
      toast("Applied");
    } catch (e) {
      toast((e as Error).message);
    }
  };

  return (
    <section className="verdict" aria-label="Suggestions from your Mac">
      <p>
        <span className="v-word">Your Mac suggests</span>
        {sug.status !== "ready" && <> · {statusMessage(sug.status)}</>}
      </p>
      {changes.length > 0 && (
        <ul style={{ listStyle: "none", paddingLeft: 0 }}>
          {changes.map((c) => (
            <li key={c.key}>
              <label style={{ display: "flex", gap: 8, alignItems: "center", minHeight: 32 }}>
                <input
                  type="checkbox"
                  checked={chosen.includes(c.key)}
                  onChange={() =>
                    setPicked(chosen.includes(c.key) ? chosen.filter((k) => k !== c.key) : [...chosen, c.key])
                  }
                />
                <span>
                  <strong>{c.label}:</strong> {c.value}
                  {c.current && <span className="muted"> (now {c.current})</span>}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <div className="row tight">
        {changes.length > 0 && (
          <button type="button" className="btn sm primary" onClick={apply} disabled={!chosen.length}>
            Apply
          </button>
        )}
        <button type="button" className="btn sm ghost" onClick={dismiss}>
          Dismiss
        </button>
      </div>
    </section>
  );
}
