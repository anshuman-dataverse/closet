import { describe, expect, it } from "vitest";
import { sameHostUrl } from "./redirect";

const req = (headers: Record<string, string>, url = "http://localhost:3000/x") => ({
  headers: new Headers(headers),
  nextUrl: new URL(url),
});

describe("sameHostUrl", () => {
  it("uses the Host header the browser sent", () => {
    expect(sameHostUrl(req({ host: "127.0.0.1:3100" }), "/login?next=%2Fcloset").href).toBe(
      "http://127.0.0.1:3100/login?next=%2Fcloset",
    );
  });
  it("prefers forwarded host and proto (Vercel)", () => {
    expect(
      sameHostUrl(
        req({ host: "internal", "x-forwarded-host": "closet.vercel.app", "x-forwarded-proto": "https" }),
        "/today",
      ).href,
    ).toBe("https://closet.vercel.app/today");
  });
});
