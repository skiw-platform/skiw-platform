import { randomUUID } from "node:crypto";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { Authenticator } from "./authenticator";
import { enrolToCodes, totp } from "./seed";

const AA = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const ROW = /^Passkey, added \d{1,2} [A-Z][a-z]{2} \d{4}, \d{2}:\d{2}$/;

async function clean(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AA).analyze();
  expect(results.violations).toEqual([]);
}

type Live = { mounted: string[]; changed: string[] };

/**
 * Records what each `aria-live` region says. A region that enters the page already holding text is
 * `mounted` (screen readers commonly skip it); text written into a region that was already there
 * is `changed`, the case they announce. This reads the DOM a screen reader watches; it does not run
 * one.
 */
async function watchLiveRegions(page: Page) {
  await page.addInitScript(() => {
    const live = { mounted: [] as string[], changed: [] as string[] };
    const last = new WeakMap<Element, string>();
    Object.assign(window, { live });
    new MutationObserver(() => {
      for (const region of document.querySelectorAll("[aria-live]")) {
        const text = region.textContent.trim();
        if (!last.has(region)) {
          if (text !== "") live.mounted.push(text);
        } else if (text !== "" && text !== last.get(region)) {
          live.changed.push(text);
        }
        last.set(region, text);
      }
    }).observe(document, { subtree: true, childList: true, characterData: true });
  });
  return () => page.evaluate(() => (window as unknown as { live: Live }).live);
}

test("a new user adds a passkey on the offer, then adds and removes one on Security", async ({ page }, info) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") problems.push(message.text());
  });
  const live = await watchLiveRegions(page);
  const device = await Authenticator.attach(page);

  const secret = await enrolToCodes(page, `e2e-passkey-${info.project.name}-${randomUUID()}@example.test`, "E2E Passkey");
  await page.getByRole("button", { name: "I have saved my codes" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Add a passkey?" })).toBeVisible();
  await clean(page);

  // The offer: enrolment counted as a fresh step-up, so no dialog; Today says it once.
  await page.getByRole("button", { name: "Add a passkey" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Today" })).toBeVisible();
  await expect(page.locator("#today-status")).toHaveText("Passkey added");
  expect(await device.held()).toEqual([expect.objectContaining({ rpId: "localhost", isResidentCredential: true })]);
  expect((await live()).changed).toContain("Passkey added");
  expect((await live()).mounted).not.toContain("Passkey added");
  await clean(page);

  // The skip link moves focus, not the page, so the notice stays; the Security link changes the page.
  await page.getByRole("link", { name: "Skip to content" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("main")).toBeFocused();
  await expect(page.locator("#today-status")).toHaveText("Passkey added");
  await page.getByRole("link", { name: "Security" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Security" })).toBeVisible();
  await expect(page.locator("#today-status")).toHaveText("");
  const rows = page.getByRole("list", { name: "Passkeys" }).locator("li > span");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toHaveText(ROW);
  await clean(page);

  // The added passkey re-issued the session, so the next change asks again: a code (the next
  // 30-second step, as enrolment used this one), with the page behind the dialog inert.
  const add = page.getByRole("button", { name: "Add a passkey" });
  await add.click();
  const dialog = page.getByRole("dialog", { name: "Confirm it is you" });
  await expect(dialog.getByLabel("Code from the app")).toBeFocused();
  await expect(page.locator("nav[inert]")).toHaveCount(1);
  await clean(page);
  await dialog.getByLabel("Code from the app").fill(totp(secret, 1));
  await dialog.getByRole("button", { name: "Confirm" }).click();
  // The same device again: the server lists its credential to exclude, so the browser refuses.
  await expect(page.locator("#security-status")).toHaveText("The passkey was not added. Try again.");
  await expect(add).toBeFocused();
  await expect(rows).toHaveCount(1);

  // A second device adds a second passkey.
  await device.replace();
  await add.click();
  await expect(page.locator("#security-status")).toHaveText("Passkey added");
  await expect(rows).toHaveCount(2);
  await expect(page.getByRole("heading", { level: 1, name: "Security" })).toBeFocused();
  await clean(page);

  // Remove the second, by its own name, after the question.
  const second = (await rows.nth(1).textContent()) ?? "missing";
  await page.getByRole("button", { name: `Remove ${second}` }).click();
  const question = page.getByRole("group", { name: `Remove ${second}?` });
  await expect(question.getByRole("button", { name: "Cancel" })).toBeFocused();
  await clean(page);
  await question.getByRole("button", { name: "Remove" }).click();
  // Asked again (the add re-issued the session); this time the second device answers.
  await dialog.getByRole("button", { name: "Use a passkey instead" }).click();
  await expect(page.locator("#security-status")).toHaveText("Passkey removed");
  await expect(rows).toHaveCount(1);
  await expect(page.getByRole("heading", { level: 1, name: "Security" })).toBeFocused();
  expect((await live()).changed).toEqual(expect.arrayContaining(["Passkey added", "Passkey removed"]));
  expect((await live()).mounted).not.toEqual(expect.arrayContaining(["Passkey removed"]));

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  // The browser logs each 403 stepup-required: the two asks above, and nothing else.
  expect(problems.filter((text) => text.includes("status of 403"))).toHaveLength(2);
  expect(problems.filter((text) => !text.includes("status of 403"))).toEqual([]);
});
