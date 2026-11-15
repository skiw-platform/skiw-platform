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

/** `signal` lets a caller abandon the request; an aborted fetch reads as NETWORK, so the caller checks it. */
export function post(path: string, body: Record<string, unknown>, signal: AbortSignal | null = null): Promise<Reply> {
  return run(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": token },
    body: JSON.stringify(body),
    signal,
  });
}

/** POST /api/auth/logout with the current token (AUTH-13); its answer's `csrf` replaces the token. */
export function logout(): Promise<Reply> {
  return post("/api/auth/logout", {});
}

export function get(path: string): Promise<Reply> {
  return run(path, { method: "GET" });
}

export type SessionState = "signed_out" | "signed_in" | "second_factor" | "enrol_factor";

const STATES: readonly string[] = ["signed_out", "signed_in", "second_factor", "enrol_factor"];

/** What the server says this browser is, or null when the answer was unreadable. A read also
 * takes the current CSRF token from its body, so it re-synchronises the page with the server. */
export async function readSession(): Promise<SessionState | null> {
  const { status, body } = await get("/api/auth/session");
  const state = body["state"];
  return status === 200 && typeof state === "string" && STATES.includes(state) ? (state as SessionState) : null;
}

/** What the server says this browser is. Anything unexpected reads as signed out. */
export async function sessionState(): Promise<SessionState> {
  return (await readSession()) ?? "signed_out";
}

/**
 * Signs out and proves it (AUTH-13). A logout whose answer is exactly the signed-out shape (status
 * 200, `next: "signed_out"`, a rotated token) is proof; any other answer (lost, truncated, malformed,
 * refused) is checked against the server's own session state, which
 * also brings the token up to date. Anything else means signed-out is unproven: callers keep the
 * signed-in screen and its sign-out button as the retry.
 */
export async function signOut(): Promise<"signed_out" | "offline" | "failed"> {
  const { status, body } = await logout();
  if (status === 200 && body["next"] === "signed_out" && typeof body["csrf"] === "string" && body["csrf"] !== "") return "signed_out";
  if ((await readSession()) === "signed_out") return "signed_out";
  return status === 0 ? "offline" : "failed";
}
