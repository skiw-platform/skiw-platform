import { fireEvent } from "@testing-library/react";
import { vi } from "vitest";

export type Answer = { status: number; body: Record<string, unknown> };
export type Call = { path: string; init: RequestInit };

/** Answers fetch() from a queue, in order, and records what the page sent. A promised answer
 * arrives when the test resolves it; the fake ignores the abort signal, as a slow network would. */
export function server(...answers: (Answer | Promise<Answer>)[]) {
  const calls: Call[] = [];
  const queue = [...answers];
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init: RequestInit) => {
      calls.push({ path, init });
      const next = queue.shift();
      if (next === undefined) return Promise.reject(new TypeError("offline"));
      return Promise.resolve(next).then((answer) => new Response(JSON.stringify(answer.body), { status: answer.status }));
    }),
  );
  return calls;
}

/** The JSON body of a recorded request. */
export const sent = (call: Call | undefined): unknown =>
  JSON.parse(typeof call?.init.body === "string" ? call.init.body : "null");

/** What a person does, as events: typing sets the field, a click presses the button. */
export const user = {
  type: (field: HTMLElement, text: string) => {
    fireEvent.change(field, { target: { value: text } });
    return Promise.resolve();
  },
  click: (button: HTMLElement) => {
    fireEvent.click(button);
    return Promise.resolve();
  },
};

export const state = (name: string): Answer => ({ status: 200, body: { state: name, csrf: "t1" } });
