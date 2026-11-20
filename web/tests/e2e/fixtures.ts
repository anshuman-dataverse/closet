import { test as base, expect, type Page } from "@playwright/test";
import { signInPath } from "./admin";
import { OWNER } from "./env";

// Every test fails on console errors or uncaught exceptions (SPEC 11: "No console errors").
export const test = base.extend<{ consoleErrors: string[]; signIn: (next?: string) => Promise<void> }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: string[] = [];
      page.on("console", (m) => {
        if (m.type() === "error") errors.push(m.text());
      });
      page.on("pageerror", (e) => errors.push(e.message));
      await use(errors);
      expect(errors, "console errors").toEqual([]);
    },
    { auto: true },
  ],
  signIn: async ({ page }, use) => {
    await use(async (next = "/today") => {
      await page.goto(await signInPath(OWNER.email, next));
      await expect(page).toHaveURL(new RegExp(`${next.replace("?", "\\?")}$`));
    });
  },
});

export { expect };
export type { Page };
