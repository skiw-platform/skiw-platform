import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { content } from "./content";
import { forgetToken } from "./enrolLink";
import { sent, server, state, user } from "./testkit";

const SETUP = { status: 200, body: { secret: "JBSWY3DPEHPK3PXP", uri: "otpauth://totp/SKIW:a?secret=JBSWY3DPEHPK3PXP" } };
const ENROLLED = { status: 200, body: { next: "enrol_factor", csrf: "t2" } };

function open(url: string) {
  forgetToken();
  window.history.replaceState(null, "", url);
}

async function enterPassword(text: string) {
  await user.type(await screen.findByLabelText(content.enrol.password), text);
  await user.click(screen.getByRole("button", { name: content.enrol.submit }));
}

describe("enrolment", () => {
  beforeEach(() => {
    document.head.innerHTML = '<meta name="csrf-token" content="t0">';
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    open("/");
  });

  it("removes the token from the address bar and sends it only in the POST body", async () => {
    open("/enrol#tok-123");
    const calls = server(state("signed_out"), ENROLLED, SETUP);
    render(<App />);
    await enterPassword("a long enough password");
    expect(window.location.hash).toBe("");
    expect(window.location.pathname).toBe("/enrol");
    expect(sent(calls[1])).toEqual({ token: "tok-123", password: "a long enough password" });
    expect(calls.map((call) => call.path).join(" ")).not.toContain("tok-123");
    expect(JSON.stringify(sent(calls[2]))).not.toContain("tok-123");
    expect(calls[1]?.init.headers).toMatchObject({ "X-CSRFToken": "t1" });
  });

  it("shows the setup key in groups, a link for the app and a code field, then the recovery codes", async () => {
    open("/enrol#tok-123");
    server(state("signed_out"), ENROLLED, SETUP, {
      status: 200,
      body: { next: "signed_in", recovery_codes: ["AAAA-1", "BBBB-2"], csrf: "t3" },
    });
    render(<App />);
    await enterPassword("a long enough password");
    expect(await screen.findByRole("heading", { level: 1, name: content.setup.title })).toBeTruthy();
    expect(screen.getByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
    expect(screen.getByRole("link", { name: content.setup.open }).getAttribute("href")).toMatch(/^otpauth:\/\//);
    await user.type(screen.getByLabelText(content.setup.code), "123456");
    await user.click(screen.getByRole("button", { name: content.setup.submit }));
    expect(await screen.findByRole("heading", { level: 1, name: content.recovery.title })).toBeTruthy();
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(["AAAA-1", "BBBB-2"]);
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("copies the codes, says so, and drops them once the person continues", async () => {
    open("/enrol#tok-123");
    server(state("signed_out"), ENROLLED, SETUP, {
      status: 200,
      body: { next: "signed_in", recovery_codes: ["AAAA-1", "BBBB-2"], csrf: "t3" },
    });
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    render(<App />);
    await enterPassword("a long enough password");
    await user.type(await screen.findByLabelText(content.setup.code), "123456");
    await user.click(screen.getByRole("button", { name: content.setup.submit }));
    await user.click(await screen.findByRole("button", { name: content.recovery.copy }));
    expect(await screen.findByText(content.recovery.copied)).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith("AAAA-1\nBBBB-2");
    // The codes are shown once: the page keeps them nowhere that outlives the screen.
    for (const store of [sessionStorage, localStorage]) {
      for (let i = 0; i < store.length; i += 1) {
        expect(store.getItem(store.key(i) ?? "")).not.toContain("AAAA-1");
      }
    }
    await user.click(screen.getByRole("button", { name: content.recovery.done }));
    expect(await screen.findByRole("heading", { level: 1, name: content.pageTitle })).toBeTruthy();
    expect(document.body.textContent).not.toContain("AAAA-1");
    expect(window.location.pathname).toBe("/");
  });

  it("says so when copying is not possible", async () => {
    open("/enrol#tok-123");
    server(state("signed_out"), ENROLLED, SETUP, {
      status: 200,
      body: { next: "signed_in", recovery_codes: ["AAAA-1"], csrf: "t3" },
    });
    vi.stubGlobal("navigator", {});
    render(<App />);
    await enterPassword("a long enough password");
    await user.type(await screen.findByLabelText(content.setup.code), "123456");
    await user.click(screen.getByRole("button", { name: content.setup.submit }));
    await user.click(await screen.findByRole("button", { name: content.recovery.copy }));
    expect(await screen.findByText(content.recovery.copyFailed)).toBeTruthy();
  });

  it("asks the person to try again on a refusal, clears the password and keeps the link usable", async () => {
    open("/enrol#tok-123");
    const calls = server(state("signed_out"), { status: 401, body: { error: "enrol-failed" } }, ENROLLED, SETUP);
    render(<App />);
    await enterPassword("short");
    const message = await screen.findByText(content.enrol.failed);
    const field = screen.getByLabelText<HTMLInputElement>(content.enrol.password);
    expect(field.value).toBe("");
    expect(field.getAttribute("aria-describedby")).toContain(message.id);
    expect(field.getAttribute("minlength")).toBe("12");
    await enterPassword("a long enough password");
    expect(await screen.findByRole("heading", { level: 1, name: content.setup.title })).toBeTruthy();
    expect(sent(calls[2])).toMatchObject({ token: "tok-123" });
  });

  it("says the link is incomplete when /enrol has no token, and offers sign-in", async () => {
    open("/enrol");
    server(state("signed_out"));
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: content.enrol.missingTitle })).toBeTruthy();
    expect(screen.queryByLabelText(content.enrol.password)).toBeNull();
    await user.click(screen.getByRole("link", { name: content.enrol.toSignIn }));
    expect(await screen.findByLabelText(content.signIn.email)).toBeTruthy();
  });

  it("after a reload, shows the setup key only on request", async () => {
    open("/enrol");
    const calls = server(state("enrol_factor"), SETUP);
    render(<App />);
    const button = await screen.findByRole("button", { name: content.setup.show });
    expect(calls).toHaveLength(1);
    await user.click(button);
    expect(await screen.findByText("JBSW Y3DP EHPK 3PXP")).toBeTruthy();
    expect(calls[1]?.path).toBe("/api/auth/enrol/totp");
  });

  it("keeps the step on a wrong code and goes back to sign-in with a notice when the enrolment expired", async () => {
    open("/enrol#tok-123");
    server(state("signed_out"), ENROLLED, SETUP, { status: 401, body: { error: "code-wrong" } }, {
      status: 401,
      body: { error: "enrol-expired" },
    });
    render(<App />);
    await enterPassword("a long enough password");
    await user.type(await screen.findByLabelText(content.setup.code), "000000");
    await user.click(screen.getByRole("button", { name: content.setup.submit }));
    expect(await screen.findByText(content.errors.codeWrong)).toBeTruthy();
    await user.type(screen.getByLabelText(content.setup.code), "111111");
    await user.click(screen.getByRole("button", { name: content.setup.submit }));
    expect(await screen.findByText(content.setup.expired)).toBeTruthy();
  });
});
