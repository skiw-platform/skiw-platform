import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { logout } from "./api";
import { App } from "./App";
import { content } from "./content";
import { addPasskey, operation } from "./passkey";
import { later, sent, server, state, user, type Answer, type Call } from "./testkit";

const OLD = "6f1c1c1e-0000-4000-8000-000000000001";
const NEW = "6f1c1c1e-0000-4000-8000-000000000002";
const OTHER = "6f1c1c1e-0000-4000-8000-000000000003";
const buffer = (...values: number[]) => new Uint8Array(values).buffer;
const bytes = (value: unknown) => [...new Uint8Array(value as ArrayBuffer)];

class FakeCredential {
  id = "-_8";
  rawId = buffer(0xfb, 0xff);
  type = "public-key";
  authenticatorAttachment: string | null = null;
  response: Record<string, unknown> = { clientDataJSON: buffer(1), attestationObject: buffer(2), getTransports: () => ["internal"] };
  getClientExtensionResults = () => ({});
}

function authenticator(failure?: string) {
  const create = vi.fn<(init: CredentialCreationOptions) => Promise<unknown>>(() => (failure ? Promise.reject(new DOMException("no", failure)) : Promise.resolve(new FakeCredential())));
  vi.stubGlobal("PublicKeyCredential", FakeCredential);
  Object.defineProperty(navigator, "credentials", { value: { create }, configurable: true });
  return create;
}

const CREATION = {
  rp: { id: "localhost", name: "SKIW" },
  user: { id: "AAEC", name: "a@example.com", displayName: "A" },
  challenge: "-_8",
  pubKeyCredParams: [{ type: "public-key", alg: -7 }],
  timeout: 60000,
  excludeCredentials: [{ id: "AQ", type: "public-key", transports: ["internal"] }],
  authenticatorSelection: { residentKey: "preferred", userVerification: "required" },
  attestation: "none",
};
const OPTIONS: Answer = { status: 200, body: { options: CREATION } };
const CREDENTIAL = { id: "-_8", rawId: "-_8", type: "public-key", clientExtensionResults: {}, response: { clientDataJSON: "AQ", attestationObject: "Ag", transports: ["internal"] } };
const ADDED: Answer = { status: 200, body: { next: "added", factor_id: NEW, csrf: "t5" } };
const STEPUP: Answer = { status: 403, body: { error: "stepup-required" } };
const list = (...ids: string[]): Answer => ({ status: 200, body: { passkey: ids.map((id) => ({ id, created_at: null })) } });
const lost = () => {
  const answer = Promise.reject(new TypeError("lost"));
  answer.catch(() => undefined);
  return answer;
};
const paths = (calls: Call[]) => calls.map((call) => call.path).slice(2);
const token = (call: Call | undefined) => (call?.init.headers as Record<string, string> | undefined)?.["X-CSRFToken"];
const settle = async () => { for (let i = 0; i < 5; i += 1) await new Promise((done) => setTimeout(done, 0)); };
const addButton = () => screen.getByRole<HTMLButtonElement>("button", { name: content.security.add });
const heading = () => screen.getByRole("heading", { level: 1, name: content.security.title });
const signOutButton = () => screen.getByRole<HTMLButtonElement>("button", { name: content.signOut });
const link = (name: string) => screen.getByRole("link", { name });
const BEGIN = "/api/auth/factors/passkey";
const CONFIRM = "/api/auth/factors/passkey/confirm";

async function security(...answers: (Answer | Promise<Answer>)[]) {
  window.history.replaceState(null, "", "/#security");
  const calls = server(state("signed_in"), list(OLD), ...answers);
  render(<App />);
  await screen.findByRole("button", { name: content.security.add });
  return calls;
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

describe("adding a passkey", () => {
  it("turns only the three binary fields into bytes and sends exactly {credential}, then shows the list", async () => {
    const create = authenticator();
    const calls = await security(OPTIONS, ADDED, list(OLD, NEW));
    await user.click(addButton());
    await shows(content.security.addedNotice);
    const publicKey = create.mock.calls[0]?.[0].publicKey;
    expect(bytes(publicKey?.challenge)).toEqual([0xfb, 0xff]);
    expect(bytes(publicKey?.user.id)).toEqual([0, 1, 2]);
    expect(bytes(publicKey?.excludeCredentials?.[0]?.id)).toEqual([1]);
    expect({ ...publicKey, challenge: null, user: { ...publicKey?.user, id: null }, excludeCredentials: publicKey?.excludeCredentials?.map((item) => ({ ...item, id: null })) }).toEqual({
      ...CREATION,
      challenge: null,
      user: { ...CREATION.user, id: null },
      excludeCredentials: [{ ...CREATION.excludeCredentials[0], id: null }],
    });
    expect(create.mock.calls[0]?.[0].signal).toBeInstanceOf(AbortSignal);
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/factors"]);
    expect(sent(calls[3])).toEqual({ credential: CREDENTIAL });
    expect(calls[3]?.init.signal).toBeNull();
    expect(token(calls[3])).toBe("t1");
    expect(within(screen.getByRole("list", { name: content.security.listTitle })).getAllByRole("listitem")).toHaveLength(2);
    expect(document.activeElement).toBe(heading());
    expect(localStorage.length + sessionStorage.length).toBe(0);
    expect(document.body.textContent).not.toContain("-_8");
  });

  it("sends the attachment when there is one and leaves out transports the browser cannot give", async () => {
    const create = authenticator();
    const credential = new FakeCredential();
    credential.authenticatorAttachment = "platform";
    credential.response = { clientDataJSON: buffer(1), attestationObject: buffer(2) };
    create.mockResolvedValueOnce(credential);
    const calls = await security(OPTIONS, ADDED, list(OLD, NEW));
    await user.click(addButton());
    await shows(content.security.addedNotice);
    expect(sent(calls[3])).toEqual({ credential: { ...CREDENTIAL, authenticatorAttachment: "platform", response: { clientDataJSON: "AQ", attestationObject: "Ag" } } });
  });

  it.each([
    ["no challenge", { ...CREATION, challenge: undefined }],
    ["a numeric challenge", { ...CREATION, challenge: 7 }],
    ["no user", { ...CREATION, user: undefined }],
    ["no user id", { ...CREATION, user: { name: "a" } }],
    ["an exclude id that is not text", { ...CREATION, excludeCredentials: [{ id: 1, type: "public-key" }] }],
  ])("with %s prompts nothing and confirms nothing", async (_, options) => {
    const create = authenticator();
    const calls = await security({ status: 200, body: { options } });
    await user.click(addButton());
    await shows(content.security.notAdded);
    expect(create).not.toHaveBeenCalled();
    expect(paths(calls)).toEqual([BEGIN]);
  });

  it.each<[string, string | undefined, unknown, Answer[]]>([
    ["a cancel", "NotAllowedError", undefined, []],
    ["a timeout", "AbortError", undefined, []],
    ["a refusal", undefined, undefined, [{ status: 400, body: { error: "passkey-refused" } }]],
    ["no credential", undefined, null, []],
    ["no attestation", undefined, Object.assign(new FakeCredential(), { response: { clientDataJSON: buffer(1) } }), []],
  ])("gives %s the one not-added text and hands focus back to Add (AUTH-05)", async (_, failure, created, after) => {
    const create = authenticator(failure);
    if (created !== undefined) create.mockResolvedValueOnce(created);
    const calls = await security(OPTIONS, ...after);
    await user.click(addButton());
    await shows(content.security.notAdded);
    expect(document.activeElement).toBe(addButton());
    expect(addButton().disabled).toBe(false);
    expect(paths(calls)).toHaveLength(1 + after.length);
  });

  it("when the browser turns out to have no support, hides Add and moves focus to the heading", async () => {
    authenticator("NotSupportedError");
    await security(OPTIONS);
    await user.click(addButton());
    await shows(content.passkeys.unsupported);
    expect(screen.queryByRole("button", { name: content.security.add })).toBeNull();
    expect(document.activeElement).toBe(heading());
  });

  it("goes to sign-in when the server no longer knows the person", async () => {
    authenticator();
    await security({ status: 401, body: { error: "signed-out" } });
    await user.click(addButton());
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
  });

  it("starts one begin however often Add is pressed, and reads busy meanwhile", async () => {
    authenticator();
    const begin = later<Answer>();
    const calls = await security(begin.promise, ADDED, list(OLD, NEW));
    const add = addButton();
    fireEvent.click(add);
    fireEvent.click(add);
    await settle();
    expect(add.textContent).toBe(content.security.addBusy);
    expect(add.disabled).toBe(true);
    begin.resolve(OPTIONS);
    await shows(content.security.addedNotice);
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/factors"]);
  });
});

it("the runner itself ignores a second add while one runs (decision 6(d))", async () => {
  authenticator("NotAllowedError");
  const calls = server(OPTIONS);
  const first = addPasskey(new AbortController().signal);
  expect(await addPasskey(new AbortController().signal)).toBeNull();
  expect(await first).toEqual({ result: "failed" });
  expect(calls.map((call) => call.path)).toEqual([BEGIN]);
});

describe("the step-up dialog", () => {
  const VERIFIED: Answer = { status: 200, body: { next: "verified", until: "2026-11-17T07:00:00+00:00" } };
  const outside = () => [signOutButton(), link("Today"), heading(), addButton(), screen.getByRole("link", { name: content.skipLink })];
  const code = () => screen.getByLabelText(content.stepUp.label);

  let create: ReturnType<typeof authenticator> | undefined;

  async function dialog(...after: (Answer | Promise<Answer>)[]) {
    create = authenticator();
    const calls = await security(STEPUP, ...after);
    await user.click(addButton());
    await screen.findByRole("dialog", { name: content.stepUp.title });
    return calls;
  }

  async function verify() {
    await user.type(code(), "123456");
    await user.click(screen.getByRole("button", { name: content.stepUp.submit }));
  }

  it("opens on stepup-required with the page around it inert, then begins once more", async () => {
    const calls = await dialog(VERIFIED, OPTIONS, ADDED, list(OLD, NEW));
    expect(outside().filter((node) => node.closest("[inert]") === null)).toEqual([]);
    expect(code().closest("[inert]")).toBeNull();
    expect(document.activeElement).toBe(code());
    await verify();
    await shows(content.security.addedNotice);
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", BEGIN, CONFIRM, "/api/auth/factors"]);
    expect(sent(calls[3])).toEqual({ purpose: "factor.change", code: "123456" });
    expect(document.querySelector("[inert]")).toBeNull();
  });

  it("treats a second stepup-required as an error and asks no third time", async () => {
    const calls = await dialog(VERIFIED, STEPUP);
    await verify();
    await shows(content.errors.generic);
    await settle();
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", BEGIN]);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(addButton());
  });

  it("keeps Tab and Shift-Tab inside the dialog", async () => {
    await dialog();
    const cancel = screen.getByRole("button", { name: content.stepUp.cancel });
    cancel.focus();
    expect(fireEvent.keyDown(cancel, { key: "Tab" })).toBe(false);
    expect(document.activeElement).toBe(code());
    expect(fireEvent.keyDown(code(), { key: "Tab", shiftKey: true })).toBe(false);
    expect(document.activeElement).toBe(cancel);
    await user.click(cancel);
  });

  it.each(["Cancel", "Escape"])("%s closes it, sends nothing more and hands focus back to Add", async (exit) => {
    const calls = await dialog();
    if (exit === "Cancel") await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
    else fireEvent.keyDown(code(), { key: "Escape" });
    await settle();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(addButton());
    expect(document.querySelector("[inert]")).toBeNull();
    expect(paths(calls)).toEqual([BEGIN]);
  });

  it.each([
    ["Cancel", "verified", VERIFIED],
    ["Cancel", "signed-out", { status: 401, body: { error: "signed-out" } }],
    ["Cancel", "refused", { status: 400, body: { error: "code-wrong" } }],
    ["Escape", "verified", VERIFIED],
    ["Escape", "signed-out", { status: 401, body: { error: "signed-out" } }],
    ["Escape", "refused", { status: 400, body: { error: "code-wrong" } }],
  ] as [string, string, Answer][])("after %s, a late %s code answer does nothing", async (exit, _, late) => {
    const answer = later<Answer>();
    const calls = await dialog(answer.promise, OPTIONS, ADDED, list(OLD, NEW));
    await verify();
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup"]); });
    if (exit === "Cancel") await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
    else fireEvent.keyDown(code(), { key: "Escape" });
    expect(calls[3]?.init.signal?.aborted).toBe(true);
    answer.resolve(late);
    await settle();
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup"]);
    expect(create?.mock.calls).toHaveLength(0);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(heading()).toBeTruthy();
    expect(document.getElementById("security-status")?.textContent ?? "").toBe("");
    expect(document.activeElement).toBe(addButton());
    expect(addButton().disabled).toBe(false);
  });

  it("an old dialog's late answer does nothing to a reopened one", async () => {
    const answer = later<Answer>();
    const calls = await dialog(answer.promise, STEPUP);
    await verify();
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup"]); });
    await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
    await user.click(addButton());
    await screen.findByRole("dialog", { name: content.stepUp.title });
    answer.resolve(VERIFIED);
    await settle();
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", BEGIN]);
    expect(screen.getByRole("dialog", { name: content.stepUp.title })).toBeTruthy();
    expect(document.activeElement).toBe(code());
    await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
  });

  // In a browser the inert header cannot be clicked; the click stands for any sign-out while it is open.
  it.each(["Sign out", "leaving"])("%s while the confirmation is pending closes the dialog, and a late verification begins nothing", async (way) => {
    const answer = later<Answer>();
    const out = way === "Sign out" ? ["/api/auth/logout"] : [];
    const calls = await dialog(answer.promise, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await verify();
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup"]); });
    if (way === "Sign out") fireEvent.click(signOutButton());
    else window.location.hash = "";
    await screen.findByRole("heading", { level: 1, name: way === "Sign out" ? content.signIn.title : content.pageTitle });
    expect(screen.queryByRole("dialog")).toBeNull();
    answer.resolve(VERIFIED);
    await settle();
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/stepup", ...out]);
    expect(document.querySelector("[inert]")).toBeNull();
  });
});

describe("leaving and lost answers", () => {
  it.each(["begin", "prompt"] as const)("leaving while the %s is pending aborts it, even after a double press, and sends nothing", async (stage) => {
    const create = authenticator();
    const begin = later<Answer>();
    const prompt = later<unknown>();
    if (stage === "prompt") create.mockReturnValueOnce(prompt.promise);
    const calls = await security(stage === "begin" ? begin.promise : OPTIONS, ADDED);
    const add = addButton();
    fireEvent.click(add);
    fireEvent.click(add);
    if (stage === "prompt") await vi.waitFor(() => { expect(create).toHaveBeenCalled(); });
    window.location.hash = "";
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    expect(calls[2]?.init.signal?.aborted).toBe(true);
    begin.resolve(OPTIONS);
    prompt.resolve(new FakeCredential());
    await settle();
    expect(create).toHaveBeenCalledTimes(stage === "begin" ? 0 : 1);
    expect(paths(calls)).toEqual([BEGIN]);
    expect(screen.getByRole<HTMLButtonElement>("button", { name: content.signOut }).disabled).toBe(false);
  });

  it("a sent confirm finishes after leaving; Sign out waits for it, then uses its token", async () => {
    authenticator();
    const confirm = later<Answer>();
    const calls = await security(OPTIONS, confirm.promise, list(OLD, NEW), { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await user.click(addButton());
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, CONFIRM]); });
    window.location.hash = "";
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    const signOut = screen.getByRole<HTMLButtonElement>("button", { name: content.signOut });
    expect(signOut.disabled).toBe(true);
    await shows(content.finishing);
    expect(await logout()).toEqual({ status: 0, body: {} });
    expect(paths(calls)).toEqual([BEGIN, CONFIRM]);
    confirm.resolve(ADDED);
    await vi.waitFor(() => { expect(signOut.disabled).toBe(false); });
    expect(screen.queryByText(content.finishing)).toBeNull();
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    await user.click(signOut);
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/factors", "/api/auth/logout"]);
    expect(token(calls[5])).toBe("t5");
  });

  it("a departed screen ignores its add's result, even a signed-out confirm", async () => {
    authenticator();
    const confirm = later<Answer>();
    const calls = await security(OPTIONS, confirm.promise);
    await user.click(addButton());
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, CONFIRM]); });
    window.location.hash = "";
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    confirm.resolve({ status: 401, body: { error: "signed-out" } });
    await vi.waitFor(() => { expect(signOutButton().disabled).toBe(false); });
    expect(screen.getByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
  });

  it.each<[string, Answer | "lost"]>([
    ["a lost answer", "lost"],
    ["a server fault", { status: 502, body: {} }],
    ["an unreadable body", { status: 200, body: {} }],
    ["no token", { status: 200, body: { next: "added", factor_id: NEW } }],
    ["an empty token", { status: 200, body: { next: "added", factor_id: NEW, csrf: "" } }],
    ["no factor id", { status: 200, body: { next: "added", csrf: "t5" } }],
    ["a factor id that is not a UUID", { status: 200, body: { next: "added", factor_id: "x", csrf: "t5" } }],
  ])("after %s reads the session, then the list, and claims nothing even when a new id is listed", async (_, answer) => {
    authenticator();
    const calls = await security(OPTIONS, answer === "lost" ? lost() : answer, { status: 200, body: { state: "signed_in", csrf: "t6" } }, list(OLD, OTHER), STEPUP);
    await user.click(addButton());
    await shows(content.security.unconfirmed);
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(within(screen.getByRole("list", { name: content.security.listTitle })).getAllByRole("listitem")).toHaveLength(2);
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/session", "/api/auth/factors"]);
    expect(document.activeElement).toBe(addButton());
    await user.click(addButton());
    await screen.findByRole("dialog");
    expect(token(calls[6])).toBe("t6");
  });

  it.each<[string, Answer | "lost", Answer]>([
    ["an added passkey", ADDED, { status: 500, body: {} }],
    ["an added passkey", ADDED, list("x")],
    ["a lost answer", "lost", { status: 500, body: {} }],
    ["a lost answer", "lost", list("x")],
  ])("after %s, a list that cannot be read or trusted claims nothing", async (_, answer, read) => {
    authenticator();
    const session = answer === "lost" ? [state("signed_in")] : [];
    await security(OPTIONS, answer === "lost" ? lost() : answer, ...session, read);
    await user.click(addButton());
    await shows(content.security.listUnsure);
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(screen.queryByText(content.security.unconfirmed)).toBeNull();
    expect(screen.queryByRole("list", { name: content.security.listTitle })).toBeNull();
    expect(operation.busy()).toBe(false);
  });

  it("with the session unreadable too, sends no add and no logout until a session read works", async () => {
    authenticator();
    const FAULT: Answer = { status: 500, body: {} };
    const calls = await security(OPTIONS, lost(), FAULT, list(OLD), FAULT, FAULT, { status: 200, body: { state: "signed_in", csrf: "t7" } }, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await user.click(addButton());
    await shows(content.security.unconfirmed);
    await user.click(addButton());
    await shows(content.sessionUnsure);
    expect(document.activeElement).toBe(addButton());
    const signOut = screen.getByRole<HTMLButtonElement>("button", { name: content.signOut });
    expect(signOut.disabled).toBe(false);
    await user.click(signOut);
    await vi.waitFor(() => { expect(paths(calls)).toHaveLength(6); });
    await settle();
    expect(screen.getAllByText(content.sessionUnsure).length).toBeGreaterThan(0);
    expect(await logout()).toEqual({ status: 0, body: {} });
    await user.click(signOut);
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/session", "/api/auth/factors", "/api/auth/session", "/api/auth/session", "/api/auth/session", "/api/auth/logout"]);
    expect(token(calls[9])).toBe("t7");
  });

  it.each(["begin", "prompt"] as const)("Sign out while the %s is pending aborts it before logout, and no confirm follows", async (stage) => {
    const create = authenticator();
    const begin = later<Answer>();
    const prompt = later<unknown>();
    const out = later<Answer>();
    if (stage === "prompt") create.mockReturnValueOnce(prompt.promise);
    const calls = await security(stage === "begin" ? begin.promise : OPTIONS, out.promise);
    fireEvent.click(addButton());
    if (stage === "prompt") await vi.waitFor(() => { expect(create).toHaveBeenCalled(); });
    fireEvent.click(signOutButton());
    expect(calls[2]?.init.signal?.aborted).toBe(true);
    expect(paths(calls)).toEqual([BEGIN]);
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, "/api/auth/logout"]); });
    begin.resolve(OPTIONS);
    prompt.resolve(new FakeCredential());
    await settle();
    out.resolve({ status: 200, body: { next: "signed_out", csrf: "t9" } });
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    await settle();
    expect(paths(calls)).toEqual([BEGIN, "/api/auth/logout"]);
    expect(create).toHaveBeenCalledTimes(stage === "begin" ? 0 : 1);
  });

  it("while a logout is pending Add starts nothing, and once it fails Add works again", async () => {
    authenticator();
    const out = later<Answer>();
    const calls = await security(out.promise, { status: 200, body: { state: "signed_in", csrf: "t2" } }, STEPUP);
    fireEvent.click(signOutButton());
    await vi.waitFor(() => { expect(paths(calls)).toEqual(["/api/auth/logout"]); });
    await user.click(addButton());
    await settle();
    expect(paths(calls)).toEqual(["/api/auth/logout"]);
    out.resolve({ status: 500, body: {} });
    await shows(content.errors.generic);
    await user.click(addButton());
    await screen.findByRole("dialog");
    expect(paths(calls)).toEqual(["/api/auth/logout", "/api/auth/session", BEGIN]);
  });

  it("the Today and Security links keep this document during a sent confirm, and the page waits for the add", async () => {
    authenticator();
    const confirm = later<Answer>();
    const calls = await security(OPTIONS, confirm.promise, list(OLD), list(OLD, NEW));
    await user.click(addButton());
    await vi.waitFor(() => { expect(paths(calls)).toEqual([BEGIN, CONFIRM]); });
    const push = vi.spyOn(window.history, "pushState");
    expect(fireEvent.click(link("Today"))).toBe(false);
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    expect(window.location.href).toBe(`${window.location.origin}/`);
    expect(operation.phase()).toBe("sent");
    expect(signOutButton().disabled).toBe(true);
    await shows(content.finishing);
    expect(fireEvent.click(link("Security"))).toBe(false);
    await screen.findByText(content.security.loading);
    expect(push).toHaveBeenCalledTimes(2);
    window.history.back();
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    window.history.forward();
    await screen.findByText(content.security.loading);
    expect(paths(calls)).toEqual([BEGIN, CONFIRM]);
    confirm.resolve(ADDED);
    await shows(content.security.many(2));
    expect(paths(calls)).toEqual([BEGIN, CONFIRM, "/api/auth/factors", "/api/auth/factors"]);
    expect(screen.queryByText(content.security.addedNotice)).toBeNull();
    expect(document.activeElement).not.toBe(heading());
    expect(signOutButton().disabled).toBe(false);
    push.mockRestore();
  });

  it.each([{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }])("leaves a click with %o to the browser", async (init) => {
    authenticator();
    await security();
    const push = vi.spyOn(window.history, "pushState");
    expect(fireEvent.click(link("Security"), init)).toBe(true);
    expect(push).not.toHaveBeenCalled();
    push.mockRestore();
  });

  it.each<[string, Answer, Answer[], string]>([
    ["added", ADDED, [], content.security.addedNotice],
    ["unconfirmed", { status: 502, body: {} }, [state("signed_in")], content.security.unconfirmed],
  ])("keeps Add busy until the list read after %s has answered, with the logout gate already open", async (_, answer, session, words) => {
    authenticator();
    const read = later<Answer>();
    const calls = await security(OPTIONS, answer, ...session, read.promise);
    const add = addButton();
    fireEvent.click(add);
    await vi.waitFor(() => { expect(paths(calls)).toHaveLength(3 + session.length); });
    expect(add.disabled).toBe(true);
    fireEvent.click(add);
    expect(await addPasskey(new AbortController().signal)).toBeNull();
    expect(operation.phase()).toBe("idle");
    expect(signOutButton().disabled).toBe(false);
    read.resolve(list(OLD, NEW));
    await shows(words);
    expect(add.disabled).toBe(false);
    expect(paths(calls)).toHaveLength(3 + session.length);
  });
});
