// The one place the page talks to the server (plan M3 §3 M3i). The CSRF token starts in the
// shell's <meta name="csrf-token"> and is replaced by the `csrf` of every auth answer, because
// sign-in and sign-out rotate it (AUTH-13).

export type Reply = { status: number; body: Record<string, unknown> };

const NETWORK: Reply = { status: 0, body: {} };

let token = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')?.content ?? "";

function keepToken(body: Record<string, unknown>): void {
  if (typeof body["csrf"] === "string") {
    token = body["csrf"];
  }
}

async function run(path: string, init: RequestInit): Promise<Reply> {
  try {
    const response = await fetch(path, { ...init, cache: "no-store", credentials: "same-origin" });
    const parsed: unknown = await response.json().catch(() => ({}));
    const body = typeof parsed === "object" && parsed !== null ? (parsed as Record<string, unknown>) : {};
    keepToken(body);
    return { status: response.status, body };
  } catch {
    return NETWORK;
  }
}

export function post(path: string, body: Record<string, string>): Promise<Reply> {
  return run(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify(body),
  });
}

export function get(path: string): Promise<Reply> {
  return run(path, { method: "GET" });
}

export type SessionState = "signed_out" | "signed_in" | "second_factor" | "enrol_factor";

const STATES: readonly string[] = ["signed_out", "signed_in", "second_factor", "enrol_factor"];

/** What the server says this browser is. Anything unexpected reads as signed out. */
export async function sessionState(): Promise<SessionState> {
  const { status, body } = await get("/api/auth/session");
  const state = body["state"];
  return status === 200 && typeof state === "string" && STATES.includes(state)
    ? (state as SessionState)
    : "signed_out";
}
