import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

test("healthz answers ok", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.status()).toBe(200);
  expect(await response.text()).toBe("ok");
});

test("shell has one main, one h1 and a named nav", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("lang", "en-MY");
});

test("no horizontal overflow at this width", async ({ page }) => {
  await page.goto("/");
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("keyboard: first Tab reaches the skip link and Enter moves focus to main", async ({
  page,
}) => {
  await page.goto("/");
  // React replaces the static shell on load; wait so the first Tab is not lost to the swap.
  await page.waitForLoadState("networkidle");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});

test("axe finds no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("no console errors or page errors", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  expect(problems).toEqual([]);
});

async function shellText(page: Page) {
  return page.evaluate(() => ({
    nav: [...document.querySelectorAll("nav[aria-label='Primary'] a")].map((a) => a.textContent),
    h1: [...document.querySelectorAll("h1")].map((h) => h.textContent),
    h2: [...document.querySelectorAll("h2")].map((h) => h.textContent),
    body: document.querySelector("main p")?.textContent,
  }));
}

test("server HTML and the React shell show the same content", async ({ browser, baseURL }) => {
  const plain = await browser.newContext({ javaScriptEnabled: false });
  const noJs = await plain.newPage();
  await noJs.goto(baseURL ?? "/");
  const withoutJs = await shellText(noJs);
  await plain.close();

  const rich = await browser.newContext();
  const js = await rich.newPage();
  await js.goto(baseURL ?? "/");
  await js.waitForLoadState("networkidle");
  const withJs = await shellText(js);
  await rich.close();

  expect(withoutJs).toEqual(withJs);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  test("keeps navigation, one main, one h1 and the empty state", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "Nothing here yet" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Today" })).toHaveAttribute("href", "/");
  });
});
