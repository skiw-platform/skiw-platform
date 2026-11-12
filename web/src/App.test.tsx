import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { sent, server, state, user } from "./testkit";

describe("first render", () => {
  it("equals the static markup in the shell template, so hydration has nothing to repair", () => {
    const html = readFileSync(resolve(process.cwd(), "../app/shell/templates/shell/shell.html"), "utf8");
    const root = /<div id="root">(.*)<\/div>\n\s*<script/s.exec(html)?.[1];
    expect(renderToStaticMarkup(<App />)).toBe(root);
  });
});

describe("App", () => {
  beforeEach(() => {
    document.head.innerHTML = '<meta name="csrf-token" content="t0">';
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the sign-in form when signed out, with one main, one h1 and labelled fields", async () => {
    server(state("signed_out"));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getByLabelText(content.signIn.email)).toBeTruthy();
    expect(screen.getByLabelText(content.signIn.password)).toBeTruthy();
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("offers a skip link that targets the main landmark", () => {
    server(state("signed_out"));
    render(<App />);
    expect(screen.getByRole("link", { name: content.skipLink }).getAttribute("href")).toBe("#main");
    expect(screen.getByRole("main").getAttribute("id")).toBe("main");
  });

  it("goes to the code step after a right password and sends the CSRF token it was given", async () => {
    const calls = server(state("signed_out"), { status: 200, body: { next: "second_factor", csrf: "t2" } });
    render(<App />);
    await user.type(await screen.findByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.secondFactor.title })).toBeTruthy();
    const login = calls[1];
    expect(login?.path).toBe("/api/auth/login");
    expect(login?.init.headers).toMatchObject({ "X-CSRFToken": "t1" });
    expect(sent(login)).toEqual({ email: "a@example.com", password: "pw" });
    expect(screen.getByRole("main")).toBe(document.activeElement);
  });

  it("says the same thing for any wrong sign-in, clears the password and keeps the email", async () => {
    server(state("signed_out"), { status: 401, body: { error: "login-failed" } });
    render(<App />);
    await user.type(await screen.findByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "wrong");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    const message = await screen.findByText(content.errors.loginFailed);
    expect(message.getAttribute("aria-live")).toBe("polite");
    const password = screen.getByLabelText<HTMLInputElement>(content.signIn.password);
    expect(password.value).toBe("");
    expect(password.getAttribute("aria-describedby")).toBe(message.id);
    expect(screen.getByLabelText<HTMLInputElement>(content.signIn.email).value).toBe("a@example.com");
    expect(password).toBe(document.activeElement);
  });

  it.each([
    [429, {}, content.errors.limited],
    [500, {}, content.errors.generic],
  ])("shows a plain message for a %i on sign-in", async (status, body, text) => {
    server(state("signed_out"), { status, body });
    render(<App />);
    await user.type(await screen.findByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    expect(await screen.findByText(text)).toBeTruthy();
  });

  it("says so when the server cannot be reached", async () => {
    server(state("signed_out"));
    render(<App />);
    await user.type(await screen.findByLabelText(content.signIn.email), "a@example.com");
    await user.type(screen.getByLabelText(content.signIn.password), "pw");
    await user.click(screen.getByRole("button", { name: content.signIn.submit }));
    expect(await screen.findByText(content.errors.network)).toBeTruthy();
  });

  it("signs in with a code, then shows Today with a nav and a sign-out button", async () => {
    server(state("second_factor"), { status: 200, body: { next: "signed_in", csrf: "t2" } });
    render(<App />);
    await user.type(await screen.findByLabelText(content.secondFactor.label), "123456");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: content.navLabel })).toBeTruthy();
    expect(screen.getByRole("button", { name: content.signOut })).toBeTruthy();
  });

  it("names the code field's help and, on a wrong code, clears it and keeps the step", async () => {
    server(state("second_factor"), { status: 401, body: { error: "code-wrong" } });
    render(<App />);
    const field = await screen.findByLabelText<HTMLInputElement>(content.secondFactor.label);
    expect(field.getAttribute("aria-describedby")).toContain("code-help");
    await user.type(field, "000000");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByText(content.errors.codeWrong)).toBeTruthy();
    expect(field.value).toBe("");
    expect(screen.getByRole("heading", { level: 1, name: content.secondFactor.title })).toBeTruthy();
  });

  it("returns to sign-in with a notice when the pending login has expired", async () => {
    server(state("second_factor"), { status: 401, body: { error: "login-expired" } });
    render(<App />);
    await user.type(await screen.findByLabelText(content.secondFactor.label), "123456");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(screen.getByText(content.errors.expired)).toBeTruthy();
  });

  it("signs out with the CSRF token it holds and shows the sign-in form again", async () => {
    const calls = server(state("signed_in"), { status: 200, body: { next: "signed_out", csrf: "t9" } });
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(calls[1]?.path).toBe("/api/auth/logout");
    expect(calls[1]?.init.headers).toMatchObject({ "X-CSRFToken": "t1" });
    expect(sent(calls[1])).toEqual({});
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("stays signed in and says so when sign-out cannot reach the server", async () => {
    server(state("signed_in"));
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    expect(await screen.findByText(content.errors.network)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
  });

  it("reads an unknown state, or any non-200 answer, as signed out", async () => {
    server({ status: 200, body: { state: "admin", csrf: "t" } });
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    cleanup();
    server({ status: 403, body: { state: "signed_in", csrf: "t" } });
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
  });

  it("does not take focus on first load, only after the person acts", async () => {
    server(state("signed_out"));
    render(<App />);
    await screen.findByRole("heading", { level: 1, name: content.signIn.title });
    expect(document.activeElement).toBe(document.body);
  });

  it("does not treat a 200 without next: signed_in as a sign-in", async () => {
    server(state("second_factor"), { status: 200, body: { csrf: "t2" } });
    render(<App />);
    await user.type(await screen.findByLabelText(content.secondFactor.label), "123456");
    await user.click(screen.getByRole("button", { name: content.secondFactor.submit }));
    expect(await screen.findByText(content.errors.generic)).toBeTruthy();
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("shows sign-in, not an error, when sign-out finds the session already gone (idle)", async () => {
    server(state("signed_in"), { status: 401, body: { error: "idle" } });
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    expect(await screen.findByRole("heading", { level: 1, name: content.signIn.title })).toBeTruthy();
    expect(screen.queryByText(content.errors.generic)).toBeNull();
  });

  it("disables the sign-out button and says so while the request runs", async () => {
    let calls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => {
        calls += 1;
        return calls === 1
          ? Promise.resolve(new Response(JSON.stringify({ state: "signed_in", csrf: "t1" }), { status: 200 }))
          : new Promise<Response>(() => undefined);
      }),
    );
    render(<App />);
    await user.click(await screen.findByRole("button", { name: content.signOut }));
    const busy = await screen.findByRole("button", { name: content.signOutBusy });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    await user.click(busy);
    expect(calls).toBe(2);
  });

  it("treats a server that cannot be read as signed out, never as signed in", async () => {
    server({ status: 500, body: {} });
    render(<App />);
    await waitFor(() => { expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(content.signIn.title); });
  });
});
