import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { parseFactors, passkeyRows } from "./passkey";
import { later, server, state, user, type Answer } from "./testkit";

const A = "6f1c1c1e-0000-4000-8000-000000000001";
const B = "6f1c1c1e-0000-4000-8000-000000000002";
const C = "6f1c1c1e-0000-4000-8000-000000000003";
const ok = (passkey: unknown): Answer => ({ status: 200, body: { totp: [{ id: "x" }], passkey, recovery_left: 5 } });
const reply = (passkey: unknown) => ok(passkey);

describe("the factor list parser", () => {
  it("accepts empty lists, a null date and keys it does not know", () => {
    expect(parseFactors(reply([]))).toEqual([]);
    expect(parseFactors({ status: 200, body: { passkey: [{ id: A, created_at: null, extra: 1 }], other: true } })).toEqual([{ id: A, createdAt: null }]);
    expect(parseFactors(reply([{ id: A, created_at: "2026-11-16T06:05:00Z" }, { id: B.toUpperCase(), created_at: "2026-11-16T06:05:00+00:00" }]))).toHaveLength(2);
  });

  it.each([
    ["a refused status", { status: 403, body: { passkey: [] } }],
    ["no passkey list", { status: 200, body: {} }],
    ["a passkey list that is not an array", reply({ id: A })],
    ["an entry that is not an object", reply(["x"])],
    ["a null entry", reply([null])],
    ["an entry without an id", reply([{ created_at: null }])],
    ["an empty id", reply([{ id: "", created_at: null }])],
    ["a numeric id", reply([{ id: 7, created_at: null }])],
    ["an id that is not a UUID", reply([{ id: "not-a-uuid", created_at: null }])],
    ["a repeated id", reply([{ id: A, created_at: null }, { id: A, created_at: null }])],
    ["a repeated id in another case", reply([{ id: A, created_at: null }, { id: A.toUpperCase(), created_at: null }])],
    ["a missing date", reply([{ id: A }])],
    ["a numeric date", reply([{ id: A, created_at: 1 }])],
    ["a date nobody can read", reply([{ id: A, created_at: "yesterday" }])],
  ])("rejects %s", (_, answer) => {
    expect(parseFactors(answer)).toBeNull();
  });
});

describe("the row text", () => {
  const rows = (...dates: (string | null)[]) => passkeyRows(dates.map((createdAt, index) => ({ id: `id${String(index)}`, createdAt }))).map((row) => row.text);

  it("reads the time in Malaysia time, 24-hour, to the minute", () => {
    expect(rows("2026-11-16T06:05:00Z")).toEqual(["Passkey, added 16 Nov 2026, 14:05"]);
  });

  it("crosses the date line and the year line, and reads midnight as 00", () => {
    expect(rows("2026-11-15T16:05:00Z", "2026-12-31T16:00:00Z", "2026-03-01T03:09:59Z")).toEqual([
      "Passkey, added 16 Nov 2026, 00:05",
      "Passkey, added 1 Jan 2027, 00:00",
      "Passkey, added 1 Mar 2026, 11:09",
    ]);
  });

  it("says when the time is unknown", () => {
    expect(rows(null)).toEqual(["Passkey, added time unknown"]);
  });

  it("numbers rows that would read the same, in the server's order, and leaves the others alone", () => {
    expect(rows("2026-11-16T06:05:01Z", "2026-11-16T06:05:59Z", null, "2026-11-16T07:00:00Z", null, null)).toEqual([
      "Passkey, added 16 Nov 2026, 14:05 (1)",
      "Passkey, added 16 Nov 2026, 14:05 (2)",
      "Passkey, added time unknown (1)",
      "Passkey, added 16 Nov 2026, 15:00",
      "Passkey, added time unknown (2)",
      "Passkey, added time unknown (3)",
    ]);
  });
});

describe("the Security page", () => {
  beforeEach(() => {
    document.head.innerHTML = '<meta name="csrf-token" content="t0">';
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    window.history.replaceState(null, "", "/");
  });

  const open = (hash = "#security") => { window.history.replaceState(null, "", `/${hash}`); };
  const current = () => screen.getAllByRole("link").filter((link) => link.getAttribute("aria-current") === "page").map((link) => link.textContent);
  const factors = (calls: { path: string }[]) => calls.filter((call) => call.path === "/api/auth/factors");

  it("opens from the address: loading first, then one text per passkey and a polite count", async () => {
    open();
    const slow = later<Answer>();
    const calls = server(state("signed_in"), slow.promise);
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.security.title })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toBe(content.security.loading);
    expect(current()).toEqual(["Security"]);
    slow.resolve(ok([{ id: A, created_at: "2026-11-16T06:05:00Z" }, { id: B, created_at: "2026-11-16T06:05:20Z" }, { id: C, created_at: null }]));
    const list = await screen.findByRole("list", { name: content.security.listTitle });
    const texts = ["Passkey, added 16 Nov 2026, 14:05 (1)", "Passkey, added 16 Nov 2026, 14:05 (2)", "Passkey, added time unknown"];
    expect(Array.from(list.querySelectorAll("li > span")).map((item) => item.textContent)).toEqual(texts);
    expect(screen.getByText("3 passkeys.").getAttribute("aria-live")).toBe("polite");
    expect(screen.queryByRole("status")).toBeNull();
    expect(calls[1]).toMatchObject({ path: "/api/auth/factors" });
    expect(calls[1]?.init.method ?? "GET").toBe("GET");
    // Each Remove is named by its row, so no two read the same (decision 7).
    expect(screen.getAllByRole("button", { name: /^Remove / })).toHaveLength(3);
    for (const text of texts) expect(screen.getAllByRole("button", { name: `Remove ${text}` })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: content.security.add })).toBeNull();
  });

  it("says when there are none, and counts one in the singular", async () => {
    open();
    server(state("signed_in"), ok([]));
    render(<App />);
    expect(await screen.findAllByText(content.security.empty)).toHaveLength(2);
    expect(screen.queryByRole("list", { name: content.security.listTitle })).toBeNull();
    cleanup();
    server(state("signed_in"), ok([{ id: A, created_at: null }]));
    render(<App />);
    expect(await screen.findByText(content.security.one)).toBeTruthy();
  });

  it.each([
    ["an unreadable list", { status: 500, body: {} }],
    ["a list that cannot be trusted", ok([{ id: "x", created_at: null }])],
    ["a lost answer", undefined],
  ])("on %s shows the error with a Try again that takes focus, and builds nothing from it", async (_, answer) => {
    open();
    const calls = answer ? server(state("signed_in"), answer, ok([{ id: A, created_at: null }])) : server(state("signed_in"));
    render(<App />);
    const retry = await screen.findByRole("button", { name: content.security.retry });
    expect(screen.getByText(content.security.loadError).getAttribute("aria-live")).toBe("polite");
    expect(document.activeElement).toBe(retry);
    expect(screen.queryByRole("list", { name: content.security.listTitle })).toBeNull();
    if (!answer) return;
    await user.click(retry);
    expect(await screen.findByText("Passkey, added time unknown")).toBeTruthy();
    expect(factors(calls)).toHaveLength(2);
    expect(screen.queryByText(content.security.loadError)).toBeNull();
  });

  it("goes to sign-in, with the timed-out notice, when the server says the session is gone", async () => {
    open();
    server(state("signed_in"), { status: 401, body: { error: "signed-out" } });
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(screen.getByText(content.errors.expired)).toBeTruthy();
    expect(window.location.hash).toBe("");
  });

  it("does not read the list on Today, and marks only Today as the current page", async () => {
    open("");
    const calls = server(state("signed_in"));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(current()).toEqual(["Today"]);
    expect(factors(calls)).toHaveLength(0);
    expect(screen.getByRole("link", { name: "Security" }).getAttribute("href")).toBe("/#security");
    expect(screen.getByRole("link", { name: "Today" }).getAttribute("href")).toBe("/");
  });

  it("treats any other hash as Today and leaves the address alone", async () => {
    open("#elsewhere");
    server(state("signed_in"));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(window.location.hash).toBe("#elsewhere");
  });

  it("follows Back and Forward between the two addresses", async () => {
    open("");
    const calls = server(state("signed_in"), ok([]), ok([]));
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: content.pageTitle });
    window.location.hash = "#security";
    expect(await screen.findByRole("heading", { level: 1, name: content.security.title })).toBeTruthy();
    expect(current()).toEqual(["Security"]);
    window.history.back();
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(current()).toEqual(["Today"]);
    window.history.forward();
    expect(await screen.findByRole("heading", { level: 1, name: content.security.title })).toBeTruthy();
    expect(factors(calls)).toHaveLength(2);
  });

  it("keeps a signed-out visitor's address, so a sign-in lands on Security", async () => {
    open();
    server(state("signed_out"), { status: 200, body: { next: "second_factor", csrf: "t2" } }, { status: 200, body: { next: "signed_in", csrf: "t3" } }, ok([]));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(window.location.hash).toBe("#security");
    await user.type(screen.getByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    await user.type(await screen.findByLabelText(content.secondFactor.label), "123456");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.security.title })).toBeTruthy();
  });

  it("clears the hash on sign-out, so the next person starts on Today", async () => {
    open();
    server(state("signed_in"), ok([]), { status: 200, body: { next: "signed_out", csrf: "t9" } }, state("signed_in"));
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/");
  });

  it("shows a failed sign-out on the Security page too", async () => {
    open();
    server(state("signed_in"), ok([]), { status: 500, body: {} }, { status: 500, body: {} });
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    await waitFor(() => { expect(screen.getByText(content.errors.generic)).toBeTruthy(); });
    expect(screen.getByRole("heading", { level: 1, name: content.security.title })).toBeTruthy();
  });
});
