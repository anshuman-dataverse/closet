import { signInPath } from "./admin";
import { STRANGER } from "./env";
import { expect, test } from "./fixtures";

test("signed-out visitors land on sign in", async ({ page }) => {
  await page.goto("/closet");
  await expect(page).toHaveURL(/\/login\?next=%2Fcloset$/);
  await expect(page.getByLabel("Email")).toBeVisible();
});

test("any email gets the same reply, and the code step appears", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("someone-else@example.test");
  await page.getByRole("button", { name: "Email me a sign-in link" }).click();
  await expect(page.getByText("Check your email for a sign-in link and a 6-digit code.")).toBeVisible();
  await expect(page.getByLabel("6-digit code")).toBeVisible();
});

test("a valid link for someone who isn't the owner is refused on the server", async ({ page }) => {
  await page.goto(await signInPath(STRANGER.email));
  await expect(page).toHaveURL(/\/login\?error=not-allowed$/);
  await expect(page.locator("p.err")).toHaveText(/can’t use this closet/);
  await page.goto("/today");
  await expect(page).toHaveURL(/\/login/);
});

test("the owner signs in, deep links survive, and sign out works", async ({ page, signIn }) => {
  await signIn("/spend");
  await expect(page.getByRole("heading", { level: 1, name: "Spend" })).toBeVisible();
  await page.goto("/profile");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
