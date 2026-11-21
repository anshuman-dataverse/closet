import path from "node:path";
import { expect, test } from "./fixtures";

const F = (n: string) => path.join(__dirname, "fixtures", n);

test.describe("public palette checker", () => {
  test("works signed out, calibrates with white paper, and uploads nothing", async ({ page }) => {
    const bodies: number[] = [];
    page.on("request", (r) => bodies.push((r.postDataBuffer() ?? Buffer.alloc(0)).length));
    await page.goto("/colors");
    await expect(page).toHaveURL(/\/colors$/); // no sign-in redirect
    await expect(page.getByRole("heading", { level: 1, name: "Find your colors" })).toBeVisible();
    await expect(page.getByText("Your photos stay on this device. Nothing is uploaded or saved.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Use this in my profile" })).toHaveCount(0);

    await page.getByTestId("face-input").setInputFiles(F("colors-warm-paper.png"));
    // An auto-detected paper is outlined and must be confirmed before it's used.
    await expect(page.getByTestId("paper-outline")).toBeVisible();
    await expect(page.getByRole("button", { name: "See my colors" })).toHaveCount(0);
    await page.getByRole("button", { name: "Yes, that’s the paper" }).click();
    await expect(page.getByText("✓ White paper confirmed. Color cast corrected.")).toBeVisible();
    await page.getByRole("button", { name: "See my colors" }).click();
    const result = page.getByRole("region", { name: "Your colors" });
    await expect(result.getByTestId("confidence")).toHaveText(/(Medium|High) confidence/);
    await expect(result.getByRole("list", { name: "Why this result" })).toContainText("Calibrated with white paper");
    expect(
      await result.getByRole("list", { name: "Your best colors" }).getByRole("listitem").count(),
    ).toBeGreaterThanOrEqual(6);
    await expect(result.getByLabel("Face shape tips")).toContainText("Oval");

    await result.getByLabel("Undertone").selectOption("warm");
    await expect(result.locator(".pills")).toContainText("Warm undertone");
    expect(Math.max(0, ...bodies)).toBeLessThan(1024); // photos never leave the device
  });

  test("without paper: asks for it, allows skipping, and lowers confidence", async ({ page }) => {
    await page.goto("/colors");
    await page.getByTestId("face-input").setInputFiles(F("colors-no-paper.png"));
    await expect(page.getByText(/No white paper found/)).toBeVisible();
    await expect(page.getByRole("button", { name: "See my colors" })).toHaveCount(0);
    await page.getByRole("button", { name: "Continue without paper" }).click();
    await page.getByRole("button", { name: "See my colors" }).click();
    // Low confidence is not presented as an answer.
    const notYet = page.getByRole("region", { name: "Not reliable yet" });
    await expect(notYet).toContainText("we’re not showing it as your result");
    await expect(notYet.getByRole("list", { name: "Why this result" })).toContainText("Not calibrated");
    await expect(page.getByRole("region", { name: "Your colors" })).toHaveCount(0);
    await notYet.getByRole("button", { name: "Show a tentative result anyway" }).click();
    const tentative = page.getByRole("region", { name: "Tentative colors" });
    await expect(tentative.getByTestId("confidence")).toHaveText("Low confidence");
    await expect(tentative).toContainText("treat this as a guess, not a result");
  });

  test("rejects a photo with more than one face", async ({ page }) => {
    await page.goto("/colors");
    await page.getByTestId("face-input").setInputFiles(F("colors-two-faces.png"));
    await expect(page.getByRole("alert").filter({ hasText: "Retake" })).toContainText(
      "Retake: More than one face found. Use a photo with just you.",
    );
  });

  test("dark mode renders the page", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/colors");
    expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgb(16, 19, 28)");
  });
});
