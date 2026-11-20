import { describe, expect, it } from "vitest";
import { isAllowedEmail, safeNext } from "./auth";

describe("isAllowedEmail", () => {
  it("matches ignoring case and spaces", () => {
    expect(isAllowedEmail(" Me@Example.com ", "me@example.com")).toBe(true);
  });
  it("rejects other emails", () => {
    expect(isAllowedEmail("friend@example.com", "me@example.com")).toBe(false);
  });
  it("fails closed when ALLOWED_EMAIL is unset or blank", () => {
    expect(isAllowedEmail("me@example.com", undefined)).toBe(false);
    expect(isAllowedEmail("me@example.com", "  ")).toBe(false);
    expect(isAllowedEmail("", "")).toBe(false);
  });
});

describe("safeNext", () => {
  it("keeps same-site paths", () => expect(safeNext("/closet")).toBe("/closet"));
  it("blocks open redirects", () => {
    for (const bad of ["https://evil.test", "//evil.test", "/\\evil.test", "", null]) {
      expect(safeNext(bad)).toBe("/today");
    }
  });
});
