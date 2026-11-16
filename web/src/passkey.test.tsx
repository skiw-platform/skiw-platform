import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { round } from "./passkey";
import { SecondFactor } from "./screens/SecondFactor";
import { StepUp } from "./screens/StepUp";
import { sent, server, state, user, type Answer, type Call, type Held } from "./testkit";

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
const SIGNED_IN = { status: 200, body: { next: "signed_in", csrf: "t3" } };
const VERIFIED = { status: 200, body: { next: "verified", until: UNTIL } };
const paths = (calls: Call[]) => calls.map((call) => call.path);
const live = () => new AbortController().signal;
const settle = async () => { for (let i = 0; i < 5; i += 1) await new Promise((done) => setTimeout(done, 0)); };

/** A promise the test resolves when it chooses: a slow network or a person slow at the prompt. */
function later<T>() {
  let give: (value: T) => void = () => undefined;
  let fail: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((done, bad) => { give = done; fail = bad; });
  return { promise, resolve: (value: T) => { give(value); }, reject: (reason: unknown) => { fail(reason); } };
}

/** A status is announced politely and never marks the code field (A11Y-03). */
function announced(text: string, label: string) {
  const message = screen.getByText(text);
  expect(message.getAttribute("aria-live")).toBe("polite");
  const field = screen.getByLabelText(label);
  expect(field.getAttribute("aria-invalid")).toBeNull();
  expect(field.getAttribute("aria-describedby") ?? "").not.toMatch(/error|status/);
}

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
    const { outcome } = await round("/begin", "/confirm", live(), { purpose: "p" }) ?? {};
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
    expect((await round("/begin", "/confirm", live()))?.outcome).toBe(outcome);
    expect(calls).toHaveLength(1);
  });

  it("reads an assertion that resolves with nothing as a failure and confirms nothing", async () => {
    const get = authenticator();
    get.mockResolvedValueOnce(null);
    const calls = server(OPTIONS);
    expect((await round("/begin", "/confirm", live()))?.outcome).toBe("failed");
    expect(calls).toHaveLength(1);
  });

  it("says unsupported without WebAuthn and failed for malformed options; no options, no ceremony", async () => {
    server(OPTIONS, { status: 200, body: { options: { challenge: 7 } } }, { status: 409, body: { error: "no-passkey" } });
    expect((await round("/b", "/c", live()))?.outcome).toBe("unsupported");
    const get = authenticator();
    expect((await round("/b", "/c", live()))?.outcome).toBe("failed");
    const done = await round("/b", "/c", live());
    expect([done?.answer.status, done?.outcome]).toEqual([409, null]);
    expect(get).not.toHaveBeenCalled();
  });

  it("hands its signal to fetch and to the prompt, and answers null once it is aborted", async () => {
    const get = authenticator();
    const calls = server(OPTIONS, { status: 200, body: {} });
    const controller = new AbortController();
    const prompt = later<unknown>();
    get.mockReturnValueOnce(prompt.promise);
    const done = round("/begin", "/confirm", controller.signal);
    await vi.waitFor(() => { expect(get).toHaveBeenCalled(); });
    expect(calls[0]?.init.signal).toBe(controller.signal);
    expect(get.mock.calls[0]?.[0].signal).toBe(controller.signal);
    controller.abort();
    prompt.resolve(new FakeCredential());
    expect(await done).toBeNull();
    expect(calls).toHaveLength(1);
  });

  it("sends confirm without the signal and runs it to its answer even when aborted meanwhile", async () => {
    authenticator();
    const body = later<Record<string, unknown>>();
    const calls = server(OPTIONS, { status: 200, body: body.promise });
    const controller = new AbortController();
    let wentOut = 0;
    const done = round("/begin", "/confirm", controller.signal, {}, () => { wentOut += 1; });
    await vi.waitFor(() => { expect(calls).toHaveLength(2); });
    expect(wentOut).toBe(1);
    expect(calls[1]?.init.signal).toBeNull();
    controller.abort();
    body.resolve({ next: "signed_in", csrf: "t3" });
    expect((await done)?.answer).toEqual({ status: 200, body: { next: "signed_in", csrf: "t3" } });
  });
});

describe("the code screen's passkey", () => {
  async function codeScreen(...answers: (Answer | Held | Promise<Answer>)[]) {
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

  it.each<[string, "NotAllowedError" | undefined, Answer[]]>([
    ["a cancel", "NotAllowedError", [OPTIONS]],
    ["a refusal", undefined, [OPTIONS, { status: 401, body: { error: "passkey-wrong" } }]],
    ["the limit", undefined, [OPTIONS, { status: 429, body: { error: "limited" } }]],
    ["a lost answer", undefined, [OPTIONS]],
  ])("after %s, focus goes back to the passkey button, enabled again", async (_, failure, answers) => {
    authenticator(failure);
    await codeScreen(...answers);
    const button = screen.getByRole<HTMLButtonElement>("button", { name: content.secondFactor.passkey });
    await user.click(button);
    await vi.waitFor(() => { expect(document.activeElement).toBe(button); });
    expect(button.disabled).toBe(false);
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
    announced(content.secondFactor.noPasskey, content.secondFactor.label);
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

  it.each([
    ["a cancel", "NotAllowedError", [OPTIONS], content.secondFactor.passkeyFailed],
    ["a refusal", undefined, [OPTIONS, { status: 401, body: { error: "passkey-wrong" } }], content.secondFactor.passkeyFailed],
    ["no passkey", undefined, [{ status: 409, body: { error: "no-passkey" } }], content.secondFactor.noPasskey],
    ["no support", "NotSupportedError", [OPTIONS], content.passkeys.unsupported],
    ["the limit", undefined, [OPTIONS, { status: 429, body: { error: "limited" } }], content.errors.limited],
    ["no network", undefined, [], content.errors.network],
  ] as const)("announces %s as a status that leaves the code field unmarked", async (_, failure, answers, text) => {
    authenticator(failure);
    await codeScreen(...answers);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    await screen.findByText(text);
    announced(text, content.secondFactor.label);
  });

  it.each(["begin", "prompt"] as const)("going back while the %s is pending sends no confirm and moves nothing later", async (stage) => {
    const get = authenticator();
    const begin = later<Answer>();
    const prompt = later<unknown>();
    if (stage === "prompt") get.mockReturnValueOnce(prompt.promise);
    const calls = await codeScreen(stage === "begin" ? begin.promise : OPTIONS, SIGNED_IN);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    await vi.waitFor(() => { expect(calls).toHaveLength(2); });
    if (stage === "prompt") await vi.waitFor(() => { expect(get).toHaveBeenCalled(); });
    const back = screen.getByRole<HTMLButtonElement>("button", { name: content.secondFactor.back });
    expect(back.disabled).toBe(false);
    await user.click(back);
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    begin.resolve(OPTIONS);
    prompt.resolve(new FakeCredential());
    await settle();
    expect(get).toHaveBeenCalledTimes(stage === "begin" ? 0 : 1);
    expect(calls).toHaveLength(2);
    expect(screen.getByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(screen.queryByRole("heading", { level: 1, name: content.pageTitle })).toBeNull();
  });

  /** The code screen with its passkey confirm sent and its body held: the server has signed in. */
  async function confirmSent(...after: (Answer | Promise<Answer>)[]) {
    return confirmSentAs(200, ...after);
  }
  async function confirmSentAs(status: number, ...after: (Answer | Promise<Answer>)[]) {
    authenticator();
    const body = later<Record<string, unknown>>();
    const held: Held = { status, body: body.promise };
    const calls = await codeScreen(OPTIONS, held, ...after);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    await vi.waitFor(() => { expect(calls).toHaveLength(3); });
    expect(calls[2]?.init.signal).toBeNull();
    return { calls, body };
  }
  const titled = (name: string) => screen.queryByRole("heading", { level: 1, name });

  it("going back after confirm went out signs that sign-in out, then shows sign-in with a usable token", async () => {
    const logout = later<Answer>();
    const { calls, body } = await confirmSent(logout.promise);
    const back = screen.getByRole<HTMLButtonElement>("button", { name: content.secondFactor.back });
    await user.click(back);
    expect(back.disabled).toBe(false);
    expect(back.textContent).toBe(content.signOutBusy);
    expect(titled(content.signIn.title)).toBeNull();
    body.resolve({ next: "signed_in", csrf: "t3" });
    await vi.waitFor(() => { expect(calls).toHaveLength(4); });
    expect(calls[3]?.path).toBe("/api/auth/logout");
    expect(calls[3]?.init.headers).toMatchObject({ "X-CSRFToken": "t3" });
    await settle();
    expect(titled(content.signIn.title)).toBeNull();
    expect(titled(content.pageTitle)).toBeNull();
    logout.resolve({ status: 200, body: { next: "signed_out", csrf: "t9" } });
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(titled(content.pageTitle)).toBeNull();
    await user.type(screen.getByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    await vi.waitFor(() => { expect(calls).toHaveLength(5); });
    expect(calls[4]?.path).toBe("/api/auth/login");
    expect(calls[4]?.init.headers).toMatchObject({ "X-CSRFToken": "t9" });
  });

  it.each([
    ["cannot reach the server", []],
    ["fails", [{ status: 500, body: {} }]],
  ] as const)("if that logout %s, shows the signed-in state, not sign-in over a live session", async (_, answers) => {
    const { calls, body } = await confirmSent(...answers);
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ next: "signed_in", csrf: "t3" });
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(screen.getByRole("button", { name: content.signOut })).toBeTruthy();
    expect(titled(content.signIn.title)).toBeNull();
    expect(paths(calls).slice(-2)).toEqual(["/api/auth/logout", "/api/auth/session"]);
  });

  it("a confirm whose body never arrives is checked against the server before sign-in shows", async () => {
    const { calls, body } = await confirmSent({ status: 200, body: { state: "signed_in", csrf: "t4" } }, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.reject(new TypeError("cut"));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(paths(calls).slice(-2)).toEqual(["/api/auth/session", "/api/auth/logout"]);
    expect(calls[4]?.init.headers).toMatchObject({ "X-CSRFToken": "t4" });
  });

  it("a logout whose body is lost is checked against the server, and the next login carries its token", async () => {
    const { calls, body } = await confirmSent({ status: 200, body: {} }, { status: 200, body: { state: "signed_out", csrf: "t7" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ next: "signed_in", csrf: "t3" });
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(paths(calls).slice(-2)).toEqual(["/api/auth/logout", "/api/auth/session"]);
    await user.type(screen.getByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    await vi.waitFor(() => { expect(calls).toHaveLength(6); });
    expect(calls[5]?.init.headers).toMatchObject({ "X-CSRFToken": "t7" });
  });

  it.each(["second_factor", "enrol_factor"] as const)("a confirm that never arrived, with the server at %s, goes to sign-in and never shows Today", async (name) => {
    const { calls, body } = await confirmSent({ status: 200, body: { state: name, csrf: "t5" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.reject(new TypeError("cut"));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(titled(content.pageTitle)).toBeNull();
    expect(paths(calls).slice(-1)).toEqual(["/api/auth/session"]);
  });

  it("a confirm that never arrived and a session that cannot be read sends no logout and keeps Today", async () => {
    const { calls, body } = await confirmSent({ status: 500, body: {} });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.reject(new TypeError("cut"));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(titled(content.signIn.title)).toBeNull();
    expect(paths(calls).slice(3)).toEqual(["/api/auth/session"]);
  });

  it.each([
    ["no token", { state: "signed_out" }],
    ["an empty token", { state: "signed_out", csrf: "" }],
  ] as const)("a session answer with %s is not proof: Today stays and no logout is sent with a stale token", async (_, answer) => {
    const { calls, body } = await confirmSent({ status: 200, body: answer });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.reject(new TypeError("cut"));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(titled(content.signIn.title)).toBeNull();
    expect(paths(calls).slice(3)).toEqual(["/api/auth/session"]);
  });

  it("a confirm success with an empty token is ambiguous: the session is read, not logged out with a stale token", async () => {
    const { calls, body } = await confirmSent({ status: 200, body: { state: "signed_out", csrf: "t7" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ next: "signed_in", csrf: "" });
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(paths(calls).slice(3)).toEqual(["/api/auth/session"]);
  });

  it.each(["second_factor", "enrol_factor"] as const)("a signed-in read, a refused logout, then %s on the follow-up read goes to sign-in", async (name) => {
    const { calls, body } = await confirmSent({ status: 200, body: { state: "signed_in", csrf: "t4" } }, { status: 403, body: {} }, { status: 200, body: { state: name, csrf: "t6" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.reject(new TypeError("cut"));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(titled(content.pageTitle)).toBeNull();
    expect(paths(calls).slice(-3)).toEqual(["/api/auth/session", "/api/auth/logout", "/api/auth/session"]);
    expect(calls[4]?.init.headers).toMatchObject({ "X-CSRFToken": "t4" });
  });

  it("a status-200 confirm without next is not trusted: the session is read, then logged out, before sign-in", async () => {
    const { calls, body } = await confirmSent({ status: 200, body: { state: "signed_in", csrf: "t4" } }, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ csrf: "t3" });
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(paths(calls).slice(-2)).toEqual(["/api/auth/session", "/api/auth/logout"]);
    expect(calls[4]?.init.headers).toMatchObject({ "X-CSRFToken": "t4" });
  });

  it("a status-200 logout without next is re-checked against the server before sign-in", async () => {
    const { calls, body } = await confirmSent({ status: 200, body: { csrf: "t8" } }, { status: 200, body: { state: "signed_in", csrf: "t8" } });
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ next: "signed_in", csrf: "t3" });
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(titled(content.signIn.title)).toBeNull();
    expect(paths(calls).slice(-2)).toEqual(["/api/auth/logout", "/api/auth/session"]);
  });

  it("going back after a confirm that signed nothing in shows sign-in without a logout", async () => {
    const { calls, body } = await confirmSentAs(401);
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    body.resolve({ error: "passkey-wrong" });
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(calls).toHaveLength(3);
  });

  it("unmounted after confirm went out, it still signs that sign-in out and moves nothing", async () => {
    authenticator();
    const body = later<Record<string, unknown>>();
    const calls = server(OPTIONS, { status: 200, body: body.promise }, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    const onNext = vi.fn();
    const { unmount } = render(<SecondFactor onNext={onNext} />);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    await vi.waitFor(() => { expect(calls).toHaveLength(2); });
    unmount();
    body.resolve({ next: "signed_in", csrf: "t3" });
    await vi.waitFor(() => { expect(calls).toHaveLength(3); });
    expect(calls[2]?.path).toBe("/api/auth/logout");
    expect(calls[2]?.init.headers).toMatchObject({ "X-CSRFToken": "t3" });
    await settle();
    expect(onNext).not.toHaveBeenCalled();
  });

  it("a passkey refused before going back leaves nothing to wait for", async () => {
    authenticator();
    const calls = server(OPTIONS, { status: 401, body: { error: "passkey-wrong" } });
    const onNext = vi.fn();
    render(<SecondFactor onNext={onNext} />);
    await user.click(screen.getByRole("button", { name: content.secondFactor.passkey }));
    await screen.findByText(content.secondFactor.passkeyFailed);
    await user.click(screen.getByRole("button", { name: content.secondFactor.back }));
    expect(onNext.mock.calls).toEqual([["signed_out"]]);
    expect(calls).toHaveLength(2);
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

  it.each<[string, "NotAllowedError" | undefined, Answer[]]>([
    ["a cancel", "NotAllowedError", [OPTIONS]],
    ["a refusal", undefined, [OPTIONS, { status: 401, body: { error: "passkey-wrong" } }]],
    ["the limit", undefined, [OPTIONS, { status: 429, body: { error: "limited" } }]],
  ])("after %s, focus goes back to the passkey button, enabled again", async (_, failure, answers) => {
    authenticator(failure);
    server(...answers);
    dialog();
    const button = screen.getByRole<HTMLButtonElement>("button", { name: content.stepUp.passkey });
    await user.click(button);
    await vi.waitFor(() => { expect(document.activeElement).toBe(button); });
    expect(button.disabled).toBe(false);
  });

  it("hands over to sign-in when the user is no longer active", async () => {
    authenticator();
    server(OPTIONS, { status: 401, body: { error: "signed-out" } });
    const { onSignedOut } = dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    await vi.waitFor(() => { expect(onSignedOut).toHaveBeenCalled(); });
  });

  it.each([
    ["a cancel", "NotAllowedError", [OPTIONS], content.stepUp.passkeyFailed],
    ["a refusal", undefined, [OPTIONS, { status: 401, body: { error: "passkey-wrong" } }], content.stepUp.passkeyFailed],
    ["no passkey", undefined, [{ status: 409, body: { error: "no-passkey" } }], content.stepUp.noPasskey],
    ["no support", "NotSupportedError", [OPTIONS], content.passkeys.unsupported],
    ["the limit", undefined, [OPTIONS, { status: 429, body: { error: "limited" } }], content.errors.limited],
    ["no network", undefined, [], content.errors.network],
  ] as const)("announces %s as a status that leaves the code field unmarked", async (_, failure, answers, text) => {
    authenticator(failure);
    server(...answers);
    dialog();
    await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
    await screen.findByText(text);
    announced(text, content.stepUp.label);
  });

  const STAGES = ["begin", "prompt", "confirm"] as const;
  const EXITS = ["Cancel", "Escape", "unmount"] as const;
  it.each(STAGES.flatMap((stage) => EXITS.map((exit) => [stage, exit] as const)))(
    "with the %s pending, %s makes its late answer do nothing",
    async (stage, exit) => {
      const get = authenticator();
      const begin = later<Answer>();
      const prompt = later<unknown>();
      const confirm = later<Answer>();
      if (stage === "prompt") get.mockReturnValueOnce(prompt.promise);
      const calls = server(stage === "begin" ? begin.promise : OPTIONS, stage === "confirm" ? confirm.promise : VERIFIED);
      const handlers = { onVerified: vi.fn(), onCancel: vi.fn(), onSignedOut: vi.fn() };
      const { unmount } = render(<StepUp purpose="factor.change" {...handlers} />);
      await user.click(screen.getByRole("button", { name: content.stepUp.passkey }));
      await vi.waitFor(() => { expect(calls).toHaveLength(stage === "confirm" ? 2 : 1); });
      if (stage === "prompt") await vi.waitFor(() => { expect(get).toHaveBeenCalled(); });
      const cancel = screen.getByRole<HTMLButtonElement>("button", { name: content.stepUp.cancel });
      expect(cancel.disabled).toBe(false);
      if (exit === "Cancel") await user.click(cancel);
      else if (exit === "Escape") fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
      else unmount();
      begin.resolve(OPTIONS);
      prompt.resolve(new FakeCredential());
      confirm.resolve(VERIFIED);
      await settle();
      expect(get).toHaveBeenCalledTimes(stage === "begin" ? 0 : 1);
      expect(calls).toHaveLength(stage === "confirm" ? 2 : 1);
      if (stage === "confirm") expect(calls[1]?.init.signal).toBeNull();
      expect(handlers.onVerified).not.toHaveBeenCalled();
      expect(handlers.onSignedOut).not.toHaveBeenCalled();
      expect(handlers.onCancel).toHaveBeenCalledTimes(exit === "unmount" ? 0 : 1);
    },
  );
});

it("adds no animation, so there is no motion to reduce", () => {
  expect(readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8")).not.toMatch(/transition|animation/);
});
