import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { forgetToken } from "./enrolLink";
import { later, sent, server, state, user, type Answer, type Call } from "./testkit";

const NEW = "6f1c1c1e-0000-4000-8000-000000000002";
const OTHER = "6f1c1c1e-0000-4000-8000-000000000003";
const ENROLLED: Answer = { status: 200, body: { next: "enrol_factor", csrf: "t2" } };
const SETUP: Answer = { status: 200, body: { secret: "JBSWY3DPEHPK3PXP", uri: "otpauth://totp/SKIW:a?secret=JBSWY3DPEHPK3PXP" } };
const CODES: Answer = { status: 200, body: { next: "signed_in", recovery_codes: ["AAAA-1"], csrf: "t3" } };
const OPTIONS: Answer = { status: 200, body: { options: { rp: { id: "localhost", name: "SKIW" }, user: { id: "AAEC", name: "a", displayName: "A" }, challenge: "-_8" } } };
const ADDED: Answer = { status: 200, body: { next: "added", factor_id: NEW, csrf: "t5" } };
const STEPUP: Answer = { status: 403, body: { error: "stepup-required" } };
const list = (...ids: string[]): Answer => ({ status: 200, body: { passkey: ids.map((id) => ({ id, created_at: null })) } });
const BEGIN = "/api/auth/factors/passkey";
const CONFIRM = "/api/auth/factors/passkey/confirm";
/** The requests after enrolment: the offer itself reads nothing before Add. */
const paths = (calls: Call[]) => calls.map((call) => call.path).slice(4);
const settle = async () => { for (let i = 0; i < 5; i += 1) await new Promise((done) => setTimeout(done, 0)); };
const addButton = () => screen.getByRole<HTMLButtonElement>("button", { name: content.security.add });
const skipButton = () => screen.getByRole<HTMLButtonElement>("button", { name: content.offer.skip });

class FakeCredential {
  id = "-_8";
  rawId = new Uint8Array([0xfb, 0xff]).buffer;
  type = "public-key";
  authenticatorAttachment = null;
  response = { clientDataJSON: new Uint8Array([1]).buffer, attestationObject: new Uint8Array([2]).buffer };
  getClientExtensionResults = () => ({});
}

function authenticator(failure?: string) {
  const create = vi.fn<(init: CredentialCreationOptions) => Promise<unknown>>(() => (failure ? Promise.reject(new DOMException("no", failure)) : Promise.resolve(new FakeCredential())));
  vi.stubGlobal("PublicKeyCredential", FakeCredential);
  Object.defineProperty(navigator, "credentials", { value: { create }, configurable: true });
  return create;
}

/** Enrols a new person up to the recovery codes, then presses Done. */
async function enrol(...answers: (Answer | Promise<Answer>)[]) {
  forgetToken();
  window.history.replaceState(null, "", "/enrol#tok-123");
  const calls = server(state("signed_out"), ENROLLED, SETUP, CODES, ...answers);
  render(<App />);
  await user.type(await screen.findByLabelText(content.enrol.password), "a long enough password");
  await user.click(screen.getByRole("button", { name: content.enrol.submit }));
  await user.type(await screen.findByLabelText(content.setup.code), "123456");
  await user.click(screen.getByRole("button", { name: content.setup.submit }));
  await user.click(await screen.findByRole("button", { name: content.recovery.done }));
  return calls;
}

async function offered(...answers: (Answer | Promise<Answer>)[]) {
  const calls = await enrol(...answers);
  await screen.findByRole("heading", { level: 1, name: content.offer.title });
  return calls;
}

async function today() {
  await screen.findByRole("heading", { level: 1, name: content.pageTitle });
}

async function shows(text: string) {
  const message = await screen.findByText(text);
  expect(message.getAttribute("aria-live")).toBe("polite");
}

beforeEach(() => {
  document.head.innerHTML = '<meta name="csrf-token" content="t0">';
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "credentials");
  window.history.replaceState(null, "", "/");
});

describe("the passkey offer after enrolment", () => {
  it("is skipped silently where the browser has no WebAuthn", async () => {
    const calls = await enrol();
    await today();
    expect(screen.queryByRole("heading", { name: content.offer.title })).toBeNull();
    expect(paths(calls)).toEqual([]);
  });

  it("is offered with Add and Skip where WebAuthn exists, and reads nothing first", async () => {
    authenticator();
    const calls = await offered();
    expect(addButton().disabled).toBe(false);
    expect(skipButton()).toBeTruthy();
    expect(window.location.pathname).toBe("/");
    expect(document.body.textContent).not.toContain("AAAA-1");
    expect(paths(calls)).toEqual([]);
  });

  it("Skip goes to Today and sends nothing", async () => {
    authenticator();
    const calls = await offered();
    await user.click(skipButton());
    await today();
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(paths(calls)).toEqual([]);
  });

  it("a successful add goes to Today with the notice, which leaves with the page", async () => {
    const create = authenticator();
    const calls = await offered(OPTIONS, ADDED, list(NEW), list(NEW));
    await user.click(addButton());
    await today();
    await shows(content.security.addedNotice);
    expect(create).toHaveBeenCalledTimes(1);
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/factors"]);
    expect(calls[4]?.init.headers).toMatchObject({ "X-CSRFToken": "t3" });
    expect(Object.keys(sent(calls[5]) as object)).toEqual(["credential"]);
    fireEvent.click(screen.getByRole("link", { name: "Security" }));
    await screen.findByText(content.security.one);
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
  });

  it.each([["a cancel", "NotAllowedError"], ["a timeout", "AbortError"]])("after %s stays, says not added, and hands focus back to Add", async (_, failure) => {
    authenticator(failure);
    const calls = await offered(OPTIONS);
    await user.click(addButton());
    await shows(content.security.notAdded);
    expect(screen.getByRole("heading", { level: 1, name: content.offer.title })).toBeTruthy();
    expect(document.activeElement).toBe(addButton());
    expect(addButton().disabled).toBe(false);
    expect(skipButton()).toBeTruthy();
    expect(paths(calls)).toEqual([BEGIN]);
  });

  it("a refused confirm stays with the same words and focus on Add", async () => {
    authenticator();
    await offered(OPTIONS, { status: 400, body: { error: "passkey-refused" } });
    await user.click(addButton());
    await shows(content.security.notAdded);
    expect(document.activeElement).toBe(addButton());
  });

  it("when support goes at run time, hides Add and moves focus to Skip", async () => {
    authenticator("NotSupportedError");
    await offered(OPTIONS);
    await user.click(addButton());
    await shows(content.passkeys.unsupported);
    expect(screen.queryByRole("button", { name: content.security.add })).toBeNull();
    expect(document.activeElement).toBe(skipButton());
  });

  it("an ambiguous add stays on the offer with the list, claims nothing and sends no second add", async () => {
    authenticator();
    const calls = await offered(OPTIONS, { status: 502, body: {} }, state("signed_in"), list(OTHER));
    await user.click(addButton());
    await shows(content.security.unconfirmed);
    expect(screen.getByRole("heading", { level: 1, name: content.offer.title })).toBeTruthy();
    expect(within(screen.getByRole("list", { name: content.security.listTitle })).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(document.activeElement).toBe(addButton());
    expect(addButton().disabled).toBe(false);
    expect(skipButton()).toBeTruthy();
    await settle();
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/session", "/api/auth/factors"]);
  });

  it("a list that cannot be read after the add stays on the offer and claims nothing", async () => {
    authenticator();
    await offered(OPTIONS, ADDED, { status: 500, body: {} });
    await user.click(addButton());
    await shows(content.security.listUnsure);
    expect(screen.getByRole("heading", { level: 1, name: content.offer.title })).toBeTruthy();
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(screen.queryByRole("list", { name: content.security.listTitle })).toBeNull();
  });

  it("asks for a step-up when the server wants one, with the offer inert, then adds once more", async () => {
    authenticator();
    const verified: Answer = { status: 200, body: { next: "verified", until: "2026-11-19T07:00:00+00:00" } };
    const calls = await offered(STEPUP, verified, OPTIONS, ADDED, list(NEW));
    await user.click(addButton());
    await screen.findByRole("dialog", { name: content.stepUp.title });
    expect([addButton(), skipButton(), screen.getByRole("heading", { level: 1 })].every((node) => node.closest("[inert]") !== null)).toBe(true);
    await user.type(screen.getByLabelText(content.stepUp.label), "123456");
    await user.click(screen.getByRole("button", { name: content.stepUp.submit }));
    await today();
    await shows(content.security.addedNotice);
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", BEGIN, CONFIRM, "/api/auth/factors"]);
  });

  it("treats a second stepup-required as an error and asks no third time", async () => {
    authenticator();
    const calls = await offered(STEPUP, { status: 200, body: { next: "verified", until: "2026-11-19T07:00:00+00:00" } }, STEPUP);
    await user.click(addButton());
    await user.type(await screen.findByLabelText(content.stepUp.label), "123456");
    await user.click(screen.getByRole("button", { name: content.stepUp.submit }));
    await shows(content.errors.generic);
    await settle();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(addButton());
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", BEGIN]);
  });

  it("Cancel in the step-up dialog returns focus to Add", async () => {
    authenticator();
    await offered(STEPUP);
    await user.click(addButton());
    await user.click(await screen.findByRole("button", { name: content.stepUp.cancel }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(addButton());
    expect(document.querySelector("[inert]")).toBeNull();
  });

  it("Skip while the begin is pending aborts it and nothing more is sent", async () => {
    const create = authenticator();
    const begin = later<Answer>();
    const calls = await offered(begin.promise, ADDED);
    const add = addButton();
    fireEvent.click(add);
    await vi.waitFor(() => { expect(add.textContent).toBe(content.security.addBusy); });
    expect(add.disabled).toBe(true);
    expect(skipButton().disabled).toBe(false);
    await user.click(skipButton());
    await today();
    expect(calls[4]?.init.signal?.aborted).toBe(true);
    begin.resolve(OPTIONS);
    await settle();
    expect(create).not.toHaveBeenCalled();
    expect(paths(calls)).toEqual([BEGIN]);
  });
});
