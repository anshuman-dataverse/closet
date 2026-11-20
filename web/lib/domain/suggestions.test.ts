import { describe, expect, it } from "vitest";
import {
  applyChanges,
  mergeSuggestions,
  parseSuggestion,
  type SuggestableForm,
  statusMessage,
  suggestionChanges,
  touchedFromValues,
} from "./suggestions";

const RAW = {
  name: "Navy oxford shirt",
  category: "Tops",
  type: "oxford shirt",
  color_name: "Navy",
  color_hex: "#1F2A48",
  pattern: "solid",
  formality: 3,
  warmth: "light",
  occasions: ["office", "college", "gym"],
  status: "ready",
  confidence: 0.8,
};
const blank: SuggestableForm = {
  name: "",
  category: "Tops",
  type: "",
  color_name: "",
  pattern: "",
  occasions: [],
  formality: "",
  warmth: "",
};

describe("parseSuggestion", () => {
  it("keeps valid fields and drops junk", () => {
    const s = parseSuggestion(RAW)!;
    expect(s.color_hex).toBe("#1f2a48");
    expect(s.occasions).toEqual(["office", "college"]);
    expect(parseSuggestion({ ...RAW, category: "Hats" })).toBeNull();
    expect(parseSuggestion(null)).toBeNull();
    expect(parseSuggestion({ ...RAW, formality: 9 })!.formality).toBeNull();
  });
});

describe("mergeSuggestions", () => {
  const s = parseSuggestion(RAW)!;
  it("fills untouched fields only", () => {
    const { form, filled } = mergeSuggestions({ ...blank, name: "My shirt" }, new Set(["name"]), s);
    expect(form.name).toBe("My shirt");
    expect(form.type).toBe("Oxford shirt");
    expect(form.color_name).toBe("Navy");
    expect(form.occasions).toEqual(["office", "college"]);
    expect(form.formality).toBe("3");
    expect(filled).not.toContain("name");
  });
  it("not clothing changes nothing", () => {
    const nc = parseSuggestion({ ...RAW, status: "not_clothing" })!;
    expect(mergeSuggestions(blank, new Set(), nc).form).toEqual(blank);
  });
  it("editing: existing values count as touched", () => {
    const current = { ...blank, name: "Work shirt", color_name: "Blue" };
    const { form } = mergeSuggestions(current, touchedFromValues(current), s);
    expect(form.name).toBe("Work shirt");
    expect(form.color_name).toBe("Blue");
    expect(form.pattern).toBe("solid");
  });
  it("messages", () => {
    expect(statusMessage("unsure")).toBe("Not sure about this one. Check the type.");
    expect(statusMessage("not_clothing")).toBe("That doesn’t look like clothing. Try another photo.");
  });
});

describe("review box", () => {
  const s = parseSuggestion(RAW)!;
  it("lists only real changes and flags empty fields", () => {
    const ch = suggestionChanges({ ...blank, name: "Navy oxford shirt", color_name: "Blue" }, s);
    expect(ch.map((c) => c.key)).toEqual(["type", "color_name", "pattern", "occasions", "formality", "warmth"]);
    expect(ch.find((c) => c.key === "color_name")).toMatchObject({ current: "Blue", value: "Navy", empty: false });
    expect(ch.find((c) => c.key === "type")!.empty).toBe(true);
  });
  it("applies chosen keys", () => {
    const f = applyChanges({ ...blank, color_name: "Blue" }, s, ["type"]);
    expect(f.type).toBe("Oxford shirt");
    expect(f.color_name).toBe("Blue");
  });
});
