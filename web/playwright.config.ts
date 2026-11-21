import { defineConfig, devices } from "@playwright/test";

// E2E runs against the local Supabase stack (`supabase start`) and the worker in --fake mode.
// Serial: both viewports share one owner account and one worker row.
const PORT = 3100;

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  globalSetup: "./tests/e2e/global-setup.ts",
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: "retain-on-failure" },
  projects: [
    {
      name: "phone",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } },
  ],
  webServer: {
    command: `pnpm build && pnpm start -p ${PORT} -H 127.0.0.1`,
    url: `http://127.0.0.1:${PORT}/login`,
    timeout: 180_000,
    reuseExistingServer: !process.env.CI,
    env: { ALLOWED_EMAIL: "owner@closet.test", NEXT_PUBLIC_FAKE_DETECTOR: "1" }, // fake detector: e2e build only
  },
});
