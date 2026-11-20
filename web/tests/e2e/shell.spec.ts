import { resetOwnerData } from "./data";
import { expect, test } from "./fixtures";

test.beforeEach(resetOwnerData);

const PAGES = [
  { path: "/today", heading: "Your closet is empty" },
  { path: "/closet", heading: "Nothing here yet" },
  { path: "/outfits", heading: "No outfits yet" },
  { path: "/shop", heading: "Your wishlist is empty" },
  { path: "/spend", heading: "No prices yet" },
  { path: "/profile", heading: "Style photos" },
];

test("every route renders its empty state, with no “Claude” anywhere", async ({ page, signIn }) => {
  await signIn();
  for (const p of PAGES) {
    await page.goto(p.path);
    await expect(page.getByRole("heading", { name: p.heading })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(/claude/i);
  }
});

test("navigation: bottom tabs on phones, top tabs on desktop", async ({ page, signIn }, info) => {
  await signIn();
  const phone = info.project.name === "phone";
  const nav = page.locator(phone ? "nav.tabbar" : "nav.tabs-wide");
  await expect(nav).toBeVisible();
  await expect(page.locator(phone ? "nav.tabs-wide" : "nav.tabbar")).toBeHidden();
  await nav.getByRole("link", { name: "Outfits" }).click();
  await expect(page).toHaveURL(/\/outfits$/);
  await expect(nav.getByRole("link", { name: "Outfits" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("link", { name: "Style profile" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Style profile" })).toBeVisible();
});

test("shop tabs follow ?tab= and arrow keys", async ({ page, signIn }) => {
  await signIn("/shop?tab=hunts");
  await expect(page.getByRole("tab", { name: "Deal hunts" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "No hunts yet" })).toBeVisible();
  await page.getByRole("tab", { name: "Deal hunts" }).press("ArrowRight");
  await expect(page).toHaveURL(/tab=missing/);
  await expect(page.getByRole("tab", { name: "What’s missing" })).toBeFocused();
});

test("occasion picker: radiogroup with arrow keys, remembered on this device", async ({ page, signIn }) => {
  await signIn();
  const group = page.getByRole("radiogroup", { name: "Dressing for" });
  await group.getByRole("radio", { name: "office" }).click();
  await group.getByRole("radio", { name: "office" }).press("ArrowDown");
  await expect(group.getByRole("radio", { name: "college" })).toHaveAttribute("aria-checked", "true");
  await expect(group.getByRole("radio", { name: "college" })).toBeFocused();
  await page.reload();
  await expect(group.getByRole("radio", { name: "college" })).toHaveAttribute("aria-checked", "true");
});

test("dark mode follows the system setting", async ({ page, signIn }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await signIn();
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe("rgb(16, 19, 28)"); // --paper, dark
  await page.emulateMedia({ colorScheme: "light" });
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.body).backgroundColor))
    .toBe("rgb(230, 235, 241)");
});

test("PWA: manifest and Apple tags are served", async ({ page, request }) => {
  const res = await request.get("/manifest.webmanifest");
  expect(res.ok()).toBe(true);
  const m = await res.json();
  expect(m).toMatchObject({ name: "Closet", display: "standalone", start_url: "/today" });
  expect(m.icons.map((i: { sizes: string }) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
  expect((await request.get("/icons/icon-512.png")).ok()).toBe(true);
  await page.goto("/login");
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveAttribute("href", /apple-icon/);
  await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /viewport-fit=cover/);
});
