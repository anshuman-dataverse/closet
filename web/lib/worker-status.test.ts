import { describe, expect, it } from "vitest";
import { isOffline, OFFLINE_AFTER_MS, readCapabilities, seenAgo } from "./worker-status";

const NOW = Date.parse("2026-11-20T12:00:00Z");
const ago = (ms: number) => new Date(NOW - ms).toISOString();

describe("isOffline", () => {
  it("is online within 2 minutes", () => {
    expect(isOffline(ago(30_000), NOW)).toBe(false);
    expect(isOffline(ago(OFFLINE_AFTER_MS), NOW)).toBe(false);
  });
  it("is offline after 2 minutes", () => expect(isOffline(ago(OFFLINE_AFTER_MS + 1), NOW)).toBe(true));
  it("is offline with no heartbeat or a bad timestamp", () => {
    expect(isOffline(null, NOW)).toBe(true);
    expect(isOffline("not a date", NOW)).toBe(true);
  });
});

describe("readCapabilities", () => {
  it("only trusts literal true", () => {
    expect(readCapabilities({ searxng: true, ollama: "yes" })).toEqual({ searxng: true, ollama: false, openai: false });
    expect(readCapabilities(null)).toEqual({ searxng: false, ollama: false, openai: false });
  });
});

describe("seenAgo", () => {
  it("reads naturally", () => {
    expect(seenAgo(ago(10_000), NOW)).toBe("just now");
    expect(seenAgo(ago(60_000), NOW)).toBe("1 minute ago");
    expect(seenAgo(ago(5 * 60_000), NOW)).toBe("5 minutes ago");
    expect(seenAgo(ago(3 * 3_600_000), NOW)).toBe("3 hours ago");
    expect(seenAgo(null, NOW)).toBe("never");
  });
});
