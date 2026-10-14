import { fileURLToPath, pathToFileURL } from "node:url";

import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The page Caddy serves with status 503 when the app is down (infra/host/caddy/maintenance.html).
// It is a static file, so it is opened straight from disk; the HTTP side (503, Retry-After, HSTS)
// is covered by the live edge tests (infra/host/tests/test_edge_live.py).
const PAGE = pathToFileURL(
  fileURLToPath(new URL("../../infra/host/caddy/maintenance.html", import.meta.url)),
).href;

const WIDTHS = [360, 768, 1280];

test("has one main, one h1, a title and a language", async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.locator("html")).toHaveAttribute("lang", "en-MY");
  await expect(page).toHaveTitle(/SKIW/);
});

for (const width of WIDTHS) {
  test(`no horizontal overflow and readable text at ${String(width)}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await page.goto(PAGE);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    await expect(page.getByRole("heading", { name: "SKIW is being updated" })).toBeInViewport();
    await expect(page.getByText("Please try again in a minute.")).toBeInViewport();
  });
}

test("axe finds no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto(PAGE);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("uses no scripts and loads nothing from the network", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto(PAGE);
  await page.waitForLoadState("networkidle");
  expect(requests).toEqual([PAGE]);
  await expect(page.locator("script")).toHaveCount(0);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("still shows the message", async ({ page }) => {
    await page.goto(PAGE);
    await expect(page.getByRole("heading", { name: "SKIW is being updated" })).toBeVisible();
  });
});

test("no console errors or page errors", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  await page.goto(PAGE);
  expect(problems).toEqual([]);
});
