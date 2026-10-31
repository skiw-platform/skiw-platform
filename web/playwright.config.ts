import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env["CI"],
  reporter: process.env["CI"] ? "github" : "list",
  // localhost, not 127.0.0.1: WebAuthn (M3) refuses an IP address as RP ID and allows http only
  // for localhost.
  use: { baseURL: process.env["E2E_BASE_URL"] ?? "http://localhost:8000" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
});
