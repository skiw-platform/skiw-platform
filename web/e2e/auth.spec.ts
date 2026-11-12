import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function openSignIn(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
}

test("a signed-out visitor gets the sign-in form, with no navigation", async ({ page }) => {
  await openSignIn(page);
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
  await expect(page.locator("main")).toHaveCount(1);
});

test("the sign-in form has no horizontal overflow and no axe violations", async ({ page }) => {
  await openSignIn(page);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(AA).analyze();
  expect(results.violations).toEqual([]);
});

test("keyboard only: skip link, email, password, then the button submits", async ({ page }) => {
  await openSignIn(page);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.type("nobody@example.com");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await page.keyboard.type("not-the-password");
  await page.keyboard.press("Enter");
  await expect(page.getByText("The email or password is not right.")).toBeVisible();
});

test("a wrong sign-in is announced, linked to the field, clears the password and keeps focus there", async ({
  page,
}) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { cspViolations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  await openSignIn(page);
  await page.getByLabel("Email").fill("nobody@example.com");
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Continue" }).click();
  const message = page.getByText("The email or password is not right.");
  await expect(message).toBeVisible();
  await expect(message).toHaveAttribute("aria-live", "polite");
  const password = page.getByLabel("Password");
  await expect(password).toHaveValue("");
  await expect(password).toBeFocused();
  await expect(password).toHaveAttribute("aria-describedby", /sign-in-error/);
  await expect(page.getByLabel("Email")).toHaveValue("nobody@example.com");
  const results = await new AxeBuilder({ page }).withTags(AA).analyze();
  expect(results.violations).toEqual([]);
  expect(problems).toEqual([]);
  expect(
    await page.evaluate(() => (window as unknown as { cspViolations: string[] }).cspViolations),
  ).toEqual([]);
});

test("the longest email and password the form takes do not break the layout", async ({ page }) => {
  await openSignIn(page);
  await page.getByLabel("Email").fill(`${"a".repeat(60)}@${"b".repeat(60)}.example.com`);
  await page.getByLabel("Password").fill("p".repeat(200));
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("the session route says signed out, and a reload keeps the sign-in form", async ({ page }) => {
  const answer = await page.request.get("/api/auth/session");
  expect(answer.status()).toBe(200);
  expect(await answer.json()).toMatchObject({ state: "signed_out" });
  await openSignIn(page);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
});

test("/enrol serves the app too, without sending the fragment to the server", async ({ page }) => {
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("/enrol#some-token");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect(requests.some((url) => url.includes("some-token"))).toBe(false);
});
