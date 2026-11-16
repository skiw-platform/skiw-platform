import { fireEvent } from "@testing-library/react";
import { vi } from "vitest";

export type Answer = { status: number; body: Record<string, unknown> };
export type Call = { path: string; init: RequestInit };
/** An answer whose status (and, in a browser, its Set-Cookie) arrives at once while its JSON body
 * waits for `body`: the server has already acted, the page has not read it yet. */
export type Held = { status: number; body: Promise<Record<string, unknown>> };

const encoder = new TextEncoder();
function respond(answer: Answer | Held): Response {
  const { status, body } = answer;
  if (!(body instanceof Promise)) return new Response(JSON.stringify(body), { status });
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      controller.enqueue(encoder.encode(JSON.stringify(await body)));
      controller.close();
    },
  });
  return new Response(stream, { status });
}

/** Answers fetch() from a queue, in order, and records what the page sent. A promised answer
 * arrives when the test resolves it, a held one sends its status first and its body later; the
 * fake ignores the abort signal, so tests assert which requests carry one. */
export function server(...answers: (Answer | Held | Promise<Answer>)[]) {
  const calls: Call[] = [];
  const queue = [...answers];
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init: RequestInit) => {
      calls.push({ path, init });
      const next = queue.shift();
      if (next === undefined) return Promise.reject(new TypeError("offline"));
      return Promise.resolve(next).then(respond);
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
