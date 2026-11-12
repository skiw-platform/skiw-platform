import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { content } from "./content";
import { StepUp } from "./screens/StepUp";
import { sent, server, user } from "./testkit";

const UNTIL = "2026-11-13T10:05:00+00:00";

function open() {
  const handlers = { onVerified: vi.fn(), onCancel: vi.fn(), onSignedOut: vi.fn() };
  render(<StepUp purpose="factor.change" {...handlers} />);
  return handlers;
}

async function enter(text: string) {
  await user.type(screen.getByLabelText(content.stepUp.label), text);
  await user.click(screen.getByRole("button", { name: content.stepUp.submit }));
}

describe("step-up dialog", () => {
  beforeEach(() => {
    document.head.innerHTML = '<meta name="csrf-token" content="t0">';
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("is a named modal dialog that puts focus in the code field", () => {
    server();
    open();
    const dialog = screen.getByRole("dialog", { name: content.stepUp.title });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement).toBe(screen.getByLabelText(content.stepUp.label));
  });

  it("sends the purpose and the code, and reports when the confirmation stops counting", async () => {
    const calls = server({ status: 200, body: { next: "verified", until: UNTIL } });
    const { onVerified } = open();
    await enter("123456");
    await vi.waitFor(() => { expect(onVerified).toHaveBeenCalledWith(UNTIL); });
    expect(calls[0]?.path).toBe("/api/auth/stepup");
    expect(sent(calls[0])).toEqual({ purpose: "factor.change", code: "123456" });
  });

  it.each([
    [401, { error: "code-wrong" }, content.errors.codeWrong],
    [429, { error: "limited" }, content.errors.limited],
    [400, { error: "invalid" }, content.errors.invalid],
    [500, {}, content.errors.generic],
  ])("on %i says so, clears the code and keeps focus there", async (status, body, text) => {
    server({ status, body });
    const { onVerified } = open();
    await enter("123456");
    expect(await screen.findByText(text)).toBeTruthy();
    const field = screen.getByLabelText(content.stepUp.label);
    expect((field as HTMLInputElement).value).toBe("");
    expect(document.activeElement).toBe(field);
    expect(field.getAttribute("aria-describedby")).toContain("stepup-error");
    expect(onVerified).not.toHaveBeenCalled();
  });

  it("says so when the server cannot be reached", async () => {
    server();
    open();
    await enter("123456");
    expect(await screen.findByText(content.errors.network)).toBeTruthy();
  });

  it("hands over to sign-in when the user is no longer active", async () => {
    server({ status: 401, body: { error: "signed-out" } });
    const { onSignedOut } = open();
    await enter("123456");
    await vi.waitFor(() => { expect(onSignedOut).toHaveBeenCalled(); });
  });

  it("cancels with the button and with Escape", async () => {
    server();
    const { onCancel } = open();
    await user.click(screen.getByRole("button", { name: content.stepUp.cancel }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(2);
  });

  it("does not keep the code after a wrong answer", async () => {
    server({ status: 401, body: { error: "code-wrong" } });
    open();
    await enter("654321");
    await screen.findByText(content.errors.codeWrong);
    expect(document.body.textContent).not.toContain("654321");
    expect(window.sessionStorage.length + window.localStorage.length).toBe(0);
  });
});
