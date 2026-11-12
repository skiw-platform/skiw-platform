import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { invite, totp } from "./seed";

const AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const PASSWORD = "a long enough password 1";

async function clean(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AA).analyze();
  expect(results.violations).toEqual([]);
}

async function signIn(page: Page, email: string) {
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Enter your code" })).toBeVisible();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("navigation")).toHaveCount(0);
}

test("an invited user enrols, signs out, and signs in with the app and then with a recovery code", async ({
  page,
}, info) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  await page.addInitScript(() => {
    const seen: string[] = [];
    Object.assign(window, { cspViolations: seen });
    document.addEventListener("securitypolicyviolation", (event) => {
      seen.push(`${event.violatedDirective} ${event.blockedURI}`);
    });
  });
  const email = `e2e-${info.project.name}-${Date.now().toString(36)}@example.test`;
  const token = invite(email, "E2E User");

  // The invitation: password, then the authenticator, then the recovery codes (shown once).
  await page.goto(`/enrol#${token}`);
  await expect(page.getByRole("heading", { level: 1, name: "Create your password" })).toBeVisible();
  expect(new URL(page.url()).hash).toBe("");
  await page.getByLabel("New password").fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Set up your authenticator" })).toBeVisible();
  const secret = ((await page.locator(".secret").textContent()) ?? "").replace(/\s/g, "");
  expect(secret).toMatch(/^[A-Z2-7]{16,}$/);
  await clean(page);

  await page.getByLabel("Code from the app").fill("000000");
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByText("That code is not right")).toBeVisible();
  await expect(page.getByLabel("Code from the app")).toBeFocused();
  await page.getByLabel("Code from the app").fill(totp(secret));
  await page.getByRole("button", { name: "Confirm" }).click();

  await expect(page.getByRole("heading", { level: 1, name: "Save your recovery codes" })).toBeVisible();
  const codes = (await page.getByRole("list", { name: "Recovery codes" }).locator("li").allTextContents()).map(
    (code) => code.trim(),
  );
  expect(codes).toHaveLength(10);
  expect(new Set(codes).size).toBe(10);
  await clean(page);
  await page.reload();
  // Shown once: after a reload the codes are gone and the user is already signed in.
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await expect(page.getByText(codes[0] ?? "missing")).toHaveCount(0);
  // The invitation is over, so the address is the ordinary one (PR 151 review R1 P1 #1).
  expect(new URL(page.url()).pathname).toBe("/");
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await clean(page);

  // Sign out, then back in with the authenticator code (the next 30-second step: the server
  // never takes a code twice).
  await signOut(page);
  await signIn(page, email);
  await clean(page);
  await page.getByLabel("Code").fill("000000");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("That code is not right")).toBeVisible();
  await expect(page.getByLabel("Code")).toBeFocused();
  await page.getByLabel("Code").fill(totp(secret, 1));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();

  // A recovery code signs in once.
  await signOut(page);
  await signIn(page, email);
  await page.getByLabel("Code").fill(codes[0] ?? "missing");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await signOut(page);
  await signIn(page, email);
  await page.getByLabel("Code").fill(codes[0] ?? "missing");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("That code is not right")).toBeVisible();

  // A reload on the code step keeps it (the pending login is on the server).
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Enter your code" })).toBeVisible();

  // The browser logs each refused code as a console error: exactly the three this test sent
  // (a wrong setup code, a wrong sign-in code, a recovery code used twice) and nothing else.
  const refused = problems.filter((text) => text.includes("status of 401"));
  expect(refused).toHaveLength(3);
  expect(problems.filter((text) => !text.includes("status of 401"))).toEqual([]);
  expect(
    await page.evaluate(() => (window as unknown as { cspViolations: string[] }).cspViolations),
  ).toEqual([]);
});

test("an invitation link works once", async ({ page }, info) => {
  const email = `e2e-once-${info.project.name}-${Date.now().toString(36)}@example.test`;
  const token = invite(email, "E2E Once");
  await page.goto(`/enrol#${token}`);
  await page.getByLabel("New password").fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Set up your authenticator" })).toBeVisible();
  // Another browser context uses the same link after the password was set: refused.
  const other = await page.context().browser()?.newContext();
  const again = await other?.newPage();
  await again?.goto(`${new URL(page.url()).origin}/enrol#${token}`);
  await again?.getByLabel("New password").fill("another long password 2");
  await again?.getByRole("button", { name: "Continue" }).click();
  await expect(again?.getByText(/That did not work/) ?? page.locator("never")).toBeVisible();
  await other?.close();
});

test("the done button on the recovery codes leaves the invitation for Today", async ({ page }, info) => {
  const email = `e2e-done-${info.project.name}-${Date.now().toString(36)}@example.test`;
  await page.goto(`/enrol#${invite(email, "E2E Done")}`);
  await page.getByLabel("New password").fill(PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();
  const secret = ((await page.locator(".secret").textContent()) ?? "").replace(/\s/g, "");
  await page.getByLabel("Code from the app").fill(totp(secret));
  await page.getByRole("button", { name: "Confirm" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Save your recovery codes" })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe("/enrol");
  await page.getByRole("button", { name: "I have saved my codes" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe("/");
  await clean(page);
});
