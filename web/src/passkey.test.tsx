import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { round } from "./passkey";
import { StepUp } from "./screens/StepUp";
import { sent, server, state, user, type Answer, type Call } from "./testkit";

const buffer = (...values: number[]) => new Uint8Array(values).buffer;

class FakeCredential {
  id = "-_8";
  rawId = buffer(0xfb, 0xff);
  type = "public-key";
  authenticatorAttachment = "platform";
  response = { clientDataJSON: buffer(1), authenticatorData: buffer(2), signature: buffer(3), userHandle: null };
  getClientExtensionResults = () => ({});
}

/** A fake `navigator.credentials` whose assertion succeeds, or fails with a DOMException name. */
function authenticator(failure?: "NotAllowedError" | "NotSupportedError") {
  const get = vi.fn<(init: CredentialRequestOptions) => Promise<unknown>>(() => (failure ? Promise.reject(new DOMException("no", failure)) : Promise.resolve(new FakeCredential())));
  vi.stubGlobal("PublicKeyCredential", FakeCredential);
  Object.defineProperty(navigator, "credentials", { value: { get }, configurable: true });
  return get;
}

const OPTIONS = { status: 200, body: { options: { challenge: "AAEC", allowCredentials: [{ id: "-_8", type: "public-key" }] } } };
const CREDENTIAL = {
  id: "-_8",
  rawId: "-_8",
  type: "public-key",
  authenticatorAttachment: "platform",
  clientExtensionResults: {},
  response: { clientDataJSON: "AQ", authenticatorData: "Ag", signature: "Aw" },
};
const UNTIL = "2026-11-15T10:05:00+00:00";
const paths = (calls: Call[]) => calls.map((call) => call.path);

function untouched() {
  expect(localStorage.length + sessionStorage.length).toBe(0);
  expect(document.cookie).toBe("");
  expect(window.history.length).toBe(1);
  expect(document.body.textContent).not.toContain("AAEC");
  // CSP: the page writes no inline style or script.
  expect(document.querySelectorAll("[style], script")).toHaveLength(0);
}

beforeEach(() => {
  document.head.innerHTML = '<meta name="csrf-token" content="t0">';
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "credentials");
});

describe("the browser passkey helper", () => {
  it("turns base64url options into bytes and sends the credential back as base64url JSON", async () => {
    const get = authenticator();
    const calls = server(OPTIONS, { status: 200, body: {} });
    const { outcome } = await round("/begin", "/confirm", { purpose: "p" });
    expect(outcome).toEqual({ credential: CREDENTIAL });
    const publicKey = get.mock.calls[0]?.[0].publicKey;
    expect([...new Uint8Array(publicKey?.challenge as ArrayBuffer)]).toEqual([0, 1, 2]);
    expect([...new Uint8Array(publicKey?.allowCredentials?.[0]?.id as ArrayBuffer)]).toEqual([0xfb, 0xff]);
    expect(paths(calls)).toEqual(["/begin", "/confirm"]);
    expect(sent(calls[1])).toEqual({ purpose: "p", credential: CREDENTIAL });
  });

  it.each([
    ["a cancel", "NotAllowedError", "failed"],
    ["no support", "NotSupportedError", "unsupported"],
  ] as const)("maps %s to a plain outcome and confirms nothing", async (_, name, outcome) => {
    authenticator(name);
    const calls = server(OPTIONS);
    expect((await round("/begin", "/confirm")).outcome).toBe(outcome);
    expect(calls).toHaveLength(1);
  });

  it("reads an assertion that resolves with nothing as a failure and confirms nothing", async () => {
    const get = authenticator();
    get.mockResolvedValueOnce(null);
    const calls = server(OPTIONS);
    expect((await round("/begin", "/confirm")).outcome).toBe("failed");
    expect(calls).toHaveLength(1);
  });

  it("says unsupported without WebAuthn and failed for malformed options; no options, no ceremony", async () => {
    server(OPTIONS, { status: 200, body: { options: { challenge: 7 } } }, { status: 409, body: { error: "no-passkey" } });
    expect((await round("/b", "/c")).outcome).toBe("unsupported");
    const get = authenticator();
    expect((await round("/b", "/c")).outcome).toBe("failed");
    const { answer, outcome } = await round("/b", "/c");
    expect([answer.status, outcome]).toEqual([409, null]);
    expect(get).not.toHaveBeenCalled();
  });
});

describe("the code screen's passkey", () => {
  async function codeScreen(...answers: Answer[]) {
    const calls = server(state("second_factor"), ...answers);
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: content.secondFactor.title });
    return calls;
  }

  it("is offered only with WebAuthn, and starts no ceremony until clicked", async () => {
    await codeScreen();
    expect(screen.queryByRole("button", { name: content.secondFactor.passkey })).toBeNull();
    cleanup();
    const get = authenticator();
    await codeScreen();
    expect(screen.getByRole("button", { name: content.secondFactor.passkey })).toBeTruthy();
    expect(get).not.toHaveBeenCalled();
  });

  it("signs in with the credential sent to its own route, with the CSRF token", async () => {
    authenticator();
    const calls = await codeScreen({ ...OPTIONS, body: { ...OPTIONS.body, csrf: "t2" } }, { status: 200, body: { next: "signed_in", csrf: "t3" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(paths(calls).slice(1)).toEqual(["/api/auth/second-factor/passkey", "/api/auth/second-factor/passkey/confirm"]);
    expect(sent(calls[2])).toEqual({ credential: CREDENTIAL });
    expect(calls[2]?.init.headers).toMatchObject({ "X-CSRFToken": "t2" });
    untouched();
  });

  it("gives a cancel and a refused passkey the same words, and the limit the code screen's", async () => {
    authenticator("NotAllowedError");
    await codeScreen(OPTIONS);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.secondFactor.passkeyFailed)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: content.secondFactor.title })).toBeTruthy();
    cleanup();
    authenticator();
    await codeScreen(OPTIONS, { status: 401, body: { error: "passkey-wrong" } }, OPTIONS, { status: 429, body: { error: "limited" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.secondFactor.passkeyFailed)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.errors.limited)).toBeTruthy();
    untouched();
  });

  it("goes back to sign-in when the pending login expired", async () => {
    authenticator();
    await codeScreen({ status: 401, body: { error: "login-expired" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.errors.expired)).toBeTruthy();
  });

  it("after no-passkey hides the button, says to use a code, and the code still signs in", async () => {
    const get = authenticator();
    const calls = await codeScreen({ status: 409, body: { error: "no-passkey" } }, { status: 200, body: { next: "signed_in", csrf: "t3" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.secondFactor.noPasskey)).toBeTruthy();
    expect(screen.queryByRole("button", { name: content.secondFactor.passkey })).toBeNull();
    const field = screen.getByLabelText(content.secondFactor.label);
    expect(document.activeElement).toBe(field);
    expect(field.getAttribute("aria-describedby")).toContain("code-error");
    expect(get).not.toHaveBeenCalled();
    await user.type(field, "123456");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(calls[2]?.path).toBe("/api/auth/second-factor");
  });

  it("hides the button and says so when the browser turns out to have no passkey support", async () => {
    authenticator("NotSupportedError");
    await codeScreen(OPTIONS);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    expect(await screen.findByText(content.passkeys.unsupported)).toBeTruthy();
    expect(screen.queryByRole("button", { name: content.secondFactor.passkey })).toBeNull();
  });
});

describe("the step-up dialog's passkey", () => {
  function dialog() {
    const handlers = { onVerified: vi.fn(), onCancel: vi.fn(), onSignedOut: vi.fn() };
    render(<StepUp purpose="factor.change" {...handlers} />);
    return handlers;
  }

  it("sends the purpose with the credential and reports the until", async () => {
    authenticator();
    const calls = server(OPTIONS, { status: 200, body: { next: "verified", until: UNTIL } });
    const { onVerified } = dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    await vi.waitFor(() => { expect(onVerified).toHaveBeenCalledWith(UNTIL); });
    expect(paths(calls)).toEqual(["/api/auth/stepup/passkey", "/api/auth/stepup/passkey/confirm"]);
    expect(sent(calls[1])).toEqual({ purpose: "factor.change", credential: CREDENTIAL });
    untouched();
  });

  it("gives a cancel and a refusal the same words, then hides the passkey after no-passkey", async () => {
    const get = authenticator();
    server(OPTIONS, { status: 401, body: { error: "passkey-wrong" } }, { status: 409, body: { error: "no-passkey" } });
    const { onVerified } = dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    expect(await screen.findByText(content.stepUp.passkeyFailed)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    expect(await screen.findByText(content.stepUp.noPasskey)).toBeTruthy();
    expect(screen.queryByRole("button", { name: content.stepUp.passkey })).toBeNull();
    expect(document.activeElement).toBe(screen.getByLabelText(content.stepUp.label));
    expect(get).toHaveBeenCalledTimes(1);
    expect(onVerified).not.toHaveBeenCalled();
    cleanup();
    authenticator("NotAllowedError");
    server(OPTIONS);
    dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    expect(await screen.findByText(content.stepUp.passkeyFailed)).toBeTruthy();
  });

  it("hands over to sign-in when the user is no longer active", async () => {
    authenticator();
    server(OPTIONS, { status: 401, body: { error: "signed-out" } });
    const { onSignedOut } = dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    await vi.waitFor(() => { expect(onSignedOut).toHaveBeenCalled(); });
  });
});

it("adds no animation, so there is no motion to reduce", () => {
  expect(readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8")).not.toMatch(/transition|animation/);
});
