import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { post, readSession } from "./api";
import { operation } from "./passkey";
import { later, sent, server, state, user, type Answer, type Call } from "./testkit";

const A = "6f1c1c1e-0000-4000-8000-000000000001";
const B = "6f1c1c1e-0000-4000-8000-000000000002";
const TEXT: Record<string, string> = { [A]: "Passkey, added time unknown (1)", [B]: "Passkey, added time unknown (2)" };
const REMOVE = "/api/auth/factors/passkey/remove";
const REMOVED: Answer = { status: 200, body: { next: "removed", csrf: "t5" } };
const STEPUP: Answer = { status: 403, body: { error: "stepup-required" } };
const VERIFIED: Answer = { status: 200, body: { next: "verified", until: "2026-11-17T07:00:00+00:00" } };
const list = (...ids: string[]): Answer => ({ status: 200, body: { passkey: ids.map((id) => ({ id, created_at: null })) } });
const lost = () => {
  const answer = Promise.reject(new TypeError("lost"));
  answer.catch(() => undefined);
  return answer;
};
const paths = (calls: Call[]) => calls.map((call) => call.path).slice(2);
const token = (call: Call | undefined) => (call?.init.headers as Record<string, string> | undefined)?.["X-CSRFToken"];
const settle = async () => { for (let i = 0; i < 5; i += 1) await new Promise((done) => setTimeout(done, 0)); };
const removeOf = (id: string) => screen.getByRole<HTMLButtonElement>("button", { name: `Remove ${TEXT[id] ?? ""}` });
const asking = (id: string) => screen.getByRole("group", { name: `Remove ${TEXT[id] ?? ""}?` });
const confirm = (id: string) => within(asking(id)).getByRole<HTMLButtonElement>("button", { name: content.security.remove });
const heading = () => screen.getByRole("heading", { level: 1, name: content.security.title });
const signOut = () => screen.getByRole<HTMLButtonElement>("button", { name: content.signOut });
const controls = () => screen.getAllByRole<HTMLButtonElement>("button").filter((button) => button.closest("section") !== null);

async function security(...answers: (Answer | Promise<Answer>)[]) {
  window.history.replaceState(null, "", "/#security");
  const calls = server(state("signed_in"), list(A, B), ...answers);
  render(<App />);
  await screen.findByRole("button", { name: `Remove ${TEXT[B] ?? ""}` });
  return calls;
}

async function removing(id: string) {
  await user.click(removeOf(id));
  await user.click(confirm(id));
}

async function shows(text: string) {
  expect((await screen.findByText(text)).getAttribute("aria-live")).toBe("polite");
}

beforeEach(() => {
  document.head.innerHTML = '<meta name="csrf-token" content="t0">';
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("removing a passkey", () => {
  it("asks first, one row at a time, then sends that row's id and shows the list", async () => {
    const calls = await security(REMOVED, list(B));
    await user.click(removeOf(B));
    expect(asking(B)).toBeTruthy();
    expect(document.activeElement).toBe(within(asking(B)).getByRole("button", { name: content.security.cancel }));
    await user.click(removeOf(A));
    expect(screen.getAllByRole("group")).toHaveLength(1);
    expect(paths(calls)).toEqual([]);
    await user.click(confirm(A));
    await shows(content.security.removedNotice);
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/factors"]);
    expect(sent(calls[2])).toEqual({ id: A });
    expect(calls[2]?.init.signal).toBeNull();
    expect(token(calls[2])).toBe("t1");
    expect(screen.getAllByRole("button", { name: /^Remove / })).toHaveLength(1);
    expect(document.activeElement).toBe(heading());
  });

  it.each(["Cancel", "Escape"])("%s closes the question, sends nothing and hands focus back to that row's Remove", async (exit) => {
    const calls = await security();
    await user.click(removeOf(B));
    const cancel = within(asking(B)).getByRole("button", { name: content.security.cancel });
    if (exit === "Cancel") await user.click(cancel);
    else fireEvent.keyDown(cancel, { key: "Escape" });
    expect(screen.queryByRole("group")).toBeNull();
    expect(document.activeElement).toBe(removeOf(B));
    expect(paths(calls)).toEqual([]);
  });

  it("keeps every list control off until the list read after the remove, with the logout gate open by then", async () => {
    const answer = later<Answer>();
    const read = later<Answer>();
    const calls = await security(answer.promise, read.promise);
    await user.click(removeOf(A));
    const yes = confirm(A);
    await user.click(yes);
    expect(yes.textContent).toBe(content.security.removeBusy);
    expect(controls().every((button) => button.disabled)).toBe(true);
    expect(signOut().disabled).toBe(true);
    await shows(content.finishing);
    answer.resolve(REMOVED);
    await vi.waitFor(() => { expect(paths(calls)).toEqual([REMOVE, "/api/auth/factors"]); });
    expect(controls().every((button) => button.disabled)).toBe(true);
    expect(operation.phase()).toBe("idle");
    expect(signOut().disabled).toBe(false);
    read.resolve(list(B));
    await shows(content.security.removedNotice);
    expect(controls().every((button) => !button.disabled)).toBe(true);
  });

  it.each<[string, Answer]>([
    ["404 not-found", { status: 404, body: { error: "not-found" } }],
    ["409 last-factor", { status: 409, body: { error: "last-factor" } }],
  ])("on %s says it is no longer there and shows the list read after it", async (_, answer) => {
    const calls = await security(answer, list(B));
    await removing(A);
    await shows(content.security.gone);
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/factors"]);
    expect(document.activeElement).toBe(heading());
  });

  it.each<[string, Answer | "lost"]>([
    ["a lost answer", "lost"],
    ["a server fault", { status: 502, body: {} }],
    ["an unreadable body", { status: 200, body: {} }],
    ["no token", { status: 200, body: { next: "removed" } }],
    ["an empty token", { status: 200, body: { next: "removed", csrf: "" } }],
  ])("after %s reads the session, then decides by the row's id in the list", async (_, answer) => {
    const reply = () => (answer === "lost" ? lost() : answer);
    const calls = await security(reply(), { status: 200, body: { state: "signed_in", csrf: "t6" } }, list(A, B), reply(), state("signed_in"), list(B));
    await removing(A);
    await shows(content.security.notRemoved);
    expect(document.activeElement).toBe(removeOf(A));
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/session", "/api/auth/factors"]);
    await removing(A);
    expect(token(calls[5])).toBe("t6");
    await shows(content.security.removedNotice);
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/session", "/api/auth/factors", REMOVE, "/api/auth/session", "/api/auth/factors"]);
  });

  it.each<[string, Answer | "lost"]>([
    ["an exact answer", REMOVED],
    ["a lost answer", "lost"],
  ])("after %s, a list that cannot be read claims nothing", async (_, answer) => {
    await security(answer === "lost" ? lost() : answer, ...(answer === "lost" ? [state("signed_in")] : []), list("x"));
    await removing(A);
    await shows(content.security.listUnsure);
    expect(screen.queryByText(content.security.removedNotice)).toBeNull();
    expect(screen.queryByText(content.security.notRemoved)).toBeNull();
  });
});

describe("the step-up dialog from Remove", () => {
  async function verify() {
    await user.type(await screen.findByLabelText(content.stepUp.label), "123456");
    await user.click(screen.getByRole("button", { name: content.stepUp.submit }));
  }

  it("opens on stepup-required with the page inert, then removes once more", async () => {
    const calls = await security(STEPUP, VERIFIED, REMOVED, list(B));
    await removing(A);
    await screen.findByRole("dialog", { name: content.stepUp.title });
    expect(signOut().closest("[inert]")).not.toBeNull();
    expect(removeOf(B).closest("[inert]")).not.toBeNull();
    await verify();
    await shows(content.security.removedNotice);
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/stepup", REMOVE, "/api/auth/factors"]);
    expect(sent(calls[4])).toEqual({ id: A });
    expect(document.querySelector("[inert]")).toBeNull();
  });

  it("treats a second stepup-required as an error and asks no third time", async () => {
    const calls = await security(STEPUP, VERIFIED, STEPUP);
    await removing(A);
    await verify();
    await shows(content.errors.generic);
    await settle();
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/stepup", REMOVE]);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(removeOf(A));
  });

  it("Cancel returns focus to that row's Remove, and a late verification removes nothing", async () => {
    const answer = later<Answer>();
    const calls = await security(STEPUP, answer.promise);
    await removing(A);
    await verify();
    await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
    answer.resolve(VERIFIED);
    await settle();
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/stepup"]);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(removeOf(A));
  });
});

describe("Sign out before the remove is sent", () => {
  it("while a logout is pending, Remove sends nothing", async () => {
    const out = later<Answer>();
    const calls = await security(out.promise);
    fireEvent.click(signOut());
    await removing(A);
    await settle();
    expect(paths(calls)).toEqual(["/api/auth/logout"]);
    out.resolve({ status: 200, body: { next: "signed_out", csrf: "t9" } });
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
  });

  // Review Round 1 (PR 165): the cancelled operation's own session read, older than the logout,
  // neither replaces the logout's token nor sends anything, whether it was aborted or ignored that.
  it.each([
    ["Remove", "ignores the abort"],
    ["Remove", "is aborted"],
    ["Remove", "answers before the logout"],
    ["Add", "ignores the abort"],
    ["Add", "is aborted"],
    ["Add", "answers before the logout"],
  ])("Sign out during %s's session re-read: the older read that %s keeps the logout's token", async (control, ending) => {
    const create = vi.fn(() => Promise.resolve(null));
    vi.stubGlobal("PublicKeyCredential", vi.fn());
    Object.defineProperty(navigator, "credentials", { value: { create }, configurable: true });
    const reread = later<Answer>();
    const check = later<Answer>();
    const calls = await security(lost(), { status: 500, body: {} }, list(A, B), reread.promise, check.promise, { status: 200, body: { next: "signed_out", csrf: "t9" } });
    await removing(A);
    await shows(content.security.notRemoved);
    if (control === "Remove") await removing(A);
    else await user.click(screen.getByRole("button", { name: content.security.add }));
    fireEvent.click(signOut());
    expect(calls[5]?.init.signal?.aborted).toBe(true);
    if (ending === "answers before the logout") {
      reread.resolve(state("signed_in"));
      await settle();
    }
    check.resolve(state("signed_in"));
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    if (ending === "is aborted") reread.reject(new DOMException("aborted", "AbortError"));
    else reread.resolve({ status: 200, body: { state: "signed_in", csrf: "t6" } });
    await settle();
    expect(paths(calls)).toEqual([REMOVE, "/api/auth/session", "/api/auth/factors", "/api/auth/session", "/api/auth/session", "/api/auth/logout"]);
    expect(create).not.toHaveBeenCalled();
    expect(operation.phase()).toBe("idle");
    await post("/api/next", {});
    expect(paths(calls).at(-1)).toBe("/api/next");
    expect(token(calls.at(-1))).toBe("t9");
  });
});

describe("a read older than a POST", () => {
  it.each(["before it was sent", "while it was in flight"])("that started %s reads as lost and keeps no token", async (when) => {
    const read = later<Answer>();
    const out = later<Answer>();
    const calls = server(...(when === "before it was sent" ? [read.promise, out.promise] : [out.promise, read.promise]));
    const first = when === "before it was sent" ? readSession() : post("/api/auth/logout", {});
    const second = when === "before it was sent" ? post("/api/auth/logout", {}) : readSession();
    out.resolve({ status: 200, body: { next: "signed_out", csrf: "t9" } });
    await (when === "before it was sent" ? second : first);
    read.resolve({ status: 200, body: { state: "signed_in", csrf: "t6" } });
    expect(await (when === "before it was sent" ? first : second)).toBeNull();
    await post("/api/next", {});
    expect(token(calls[2])).toBe("t9");
  });
});
