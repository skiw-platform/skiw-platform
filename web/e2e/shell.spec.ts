import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("healthz answers ok", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.status()).toBe(200);
  expect(await response.text()).toBe("ok");
});

test("the browser keeps the __Host-csrftoken cookie and sends it back", async ({
  page,
  context,
}) => {
  const csrfCookie = async () =>
    (await context.cookies()).find((cookie) => cookie.name === "__Host-csrftoken");
  const response = await page.goto("/");
  const setCookie = (await response?.headerValues("set-cookie")) ?? [];
  expect(setCookie.some((value) => value.startsWith("__Host-csrftoken="))).toBe(true);
  const first = await csrfCookie();
  expect(first).toMatchObject({ secure: true, httpOnly: true, sameSite: "Strict", path: "/" });
  await page.reload();
  // Django mints a new secret when the request carries no cookie, so an equal value proves the
  // browser sent it back.
  expect((await csrfCookie())?.value).toBe(first?.value);
});

test("shell has one main and one h1", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveCount(1);
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
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Skip to content" });
  await expect(skip).toBeFocused();
  await expect(skip).toBeInViewport();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});

test("keyboard focus survives a slow client start", async ({ page }) => {
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/assets/*.js", async (route) => {
    await gate;
    await route.continue();
  });
  await page.goto("/", { waitUntil: "commit" });
  const skip = page.getByRole("link", { name: "Skip to content" });
  await skip.waitFor();
  await page.keyboard.press("Tab");
  await expect(skip).toBeFocused();
  release();
  await page.waitForLoadState("networkidle");
  await expect(skip).toBeFocused();
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

test("the content security policy blocks nothing on the shell", async ({ page }) => {
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { cspViolations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  const script = page.waitForResponse((r) => /\/assets\/[^/]+\.js$/.test(r.url()) && r.ok());
  const response = await page.goto("/");
  expect(response?.headers()["content-security-policy"]).toContain("'strict-dynamic'");
  await script;
  await page.waitForLoadState("networkidle");
  const violations = await page.evaluate(
    () => (window as unknown as { cspViolations: string[] }).cspViolations,
  );
  expect(violations).toEqual([]);
});

test.describe("without JavaScript", () => {
  test.use({ javaScriptEnabled: false });

  // Signing in needs JavaScript: the login routes answer JSON (DECISIONS M3i-1), so the static page
  // is only the loading state.
  test("serves the loading state with one main and one h1", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("main")).toHaveCount(1);
    await expect(page.locator("h1")).toHaveText("Loading");
    await expect(page.getByRole("link", { name: "Skip to content" })).toHaveAttribute("href", "#main");
  });
});
