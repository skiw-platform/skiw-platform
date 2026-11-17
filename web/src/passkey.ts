// The browser half of a passkey assertion and registration (plan M3 §3 M3g). The
// server's options arrive as py_webauthn JSON, binary fields in base64url; the credential goes back
// in the same form. Options, challenge and credential live only in the caller's call: nothing
// here stores, logs or keeps them.

import { get, hold, post, readSession, rotated, type Reply } from "./api";
import { content } from "./content";

/** What a ceremony gives: the credential as JSON, or a plain reason the screen can say. */
type Ceremony = { credential: Record<string, unknown> } | "failed" | "unsupported";

export function passkeySupported(): boolean {
  return typeof window.PublicKeyCredential === "function" && "credentials" in navigator;
}

function bytes(text: unknown): Uint8Array<ArrayBuffer> {
  if (typeof text !== "string") throw new TypeError("not base64url");
  const plain = atob(text.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(plain, (char) => char.charCodeAt(0));
}

function text(buffer: ArrayBuffer): string {
  const plain = String.fromCharCode(...new Uint8Array(buffer));
  return btoa(plain).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

type Json = Record<string, unknown>;
const ids = (list: unknown) => (Array.isArray(list) ? (list as Json[]).map((item) => ({ ...item, id: bytes(item["id"]) })) : []);

type Response = AuthenticatorResponse & {
  authenticatorData?: ArrayBuffer;
  signature?: ArrayBuffer;
  userHandle?: ArrayBuffer | null;
};

/** `extra` carries a registration's own fields; an attestation response has none of the assertion's. */
function encode(credential: PublicKeyCredential, extra: Json = {}): Json {
  const answer = credential.response as Response;
  const response: Json = { clientDataJSON: text(answer.clientDataJSON), ...extra };
  for (const key of ["authenticatorData", "signature", "userHandle"] as const) {
    const value = answer[key];
    if (value) response[key] = text(value);
  }
  return {
    id: credential.id,
    rawId: text(credential.rawId),
    type: credential.type,
    response,
    authenticatorAttachment: credential.authenticatorAttachment ?? undefined,
    clientExtensionResults: credential.getClientExtensionResults(),
  };
}

/** `navigator.credentials.get()` with the server's request options. A cancel, a timeout, a refusing
 * authenticator and malformed options all read as "failed". The cast: the server JSON is the shape
 * WebAuthn expects once its binary fields are bytes, and the browser checks the rest. */
async function assertion(options: Json, signal: AbortSignal): Promise<Ceremony> {
  if (!passkeySupported()) return "unsupported";
  try {
    const publicKey = {
      ...options,
      challenge: bytes(options["challenge"]),
      allowCredentials: ids(options["allowCredentials"]),
    } as unknown as PublicKeyCredentialRequestOptions;
    const credential = await navigator.credentials.get({ publicKey, signal });
    return credential instanceof window.PublicKeyCredential ? { credential: encode(credential) } : "failed";
  } catch (error) {
    return reason(error);
  }
}

const reason = (error: unknown): Ceremony => (error instanceof DOMException && error.name === "NotSupportedError" ? "unsupported" : "failed");

type Attested = AuthenticatorResponse & { attestationObject?: unknown; getTransports?: () => string[] };

/** `navigator.credentials.create()` with the server's creation options (spec M3g-2a-2 decision 5):
 * only `challenge`, `user.id` and each `excludeCredentials[].id` become bytes; the cast as above. */
async function registration(options: Json, signal: AbortSignal): Promise<Ceremony> {
  if (!passkeySupported()) return "unsupported";
  try {
    const user = options["user"] as Json;
    const publicKey = {
      ...options,
      challenge: bytes(options["challenge"]),
      user: { ...user, id: bytes(user["id"]) },
      excludeCredentials: ids(options["excludeCredentials"]),
    } as unknown as PublicKeyCredentialCreationOptions;
    const credential = await navigator.credentials.create({ publicKey, signal });
    if (!(credential instanceof window.PublicKeyCredential)) return "failed";
    const answer = credential.response as Attested;
    if (!(answer.attestationObject instanceof ArrayBuffer)) return "failed";
    const extra: Json = { attestationObject: text(answer.attestationObject) };
    if (typeof answer.getTransports === "function") extra["transports"] = answer.getTransports();
    return { credential: encode(credential, extra) };
  } catch (error) {
    return reason(error);
  }
}

/** One click's round: begin, the ceremony (an assertion unless `make` says otherwise), confirm. `answer` is the confirm's, or the begin's
 * when nothing reached confirm; `outcome` is null when the begin gave no options. */
type Round = { answer: Reply; outcome: Ceremony | null };

/** Read through a call: TypeScript would otherwise keep the first check's narrowing across the awaits. */
const left = (signal: AbortSignal): boolean => signal.aborted;

/**
 * Null when `signal` was aborted before confirm went out: nothing reached confirm, so the caller
 * just leaves; the signal also reaches the begin fetch and the browser prompt, which stop early.
 * A sent confirm is a commit boundary (AUTH-13): it carries no signal, but its answer can still be
 * lost, cut or malformed, so a caller whose signal is aborted by then reconciles with the server
 * (the code screen reads the session and signs a live one out, only with a token it saw). `onSent` runs as it goes.
 */
export async function round(
  begin: string,
  confirm: string,
  signal: AbortSignal,
  extra: Json = {},
  onSent: () => void = () => undefined,
  make: (options: Json, signal: AbortSignal) => Promise<Ceremony> = assertion,
): Promise<Round | null> {
  const begun = await post(begin, {}, signal);
  if (left(signal)) return null;
  const options = begun.body["options"];
  const usable = begun.status === 200 && typeof options === "object" && options !== null;
  const outcome = usable ? await make(options as Json, signal) : null;
  if (left(signal)) return null;
  if (outcome === null || typeof outcome !== "object") return { answer: begun, outcome };
  onSent();
  return { answer: await post(confirm, { ...extra, ...outcome }), outcome };
}

/** One of the person's own passkeys, as the factor list gives it. */
export type PasskeyEntry = { id: string; createdAt: string | null };
export type PasskeyRow = { id: string; text: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * The one reader of the factor list (spec decision 3), for the first load and every later read. A
 * valid answer is a 200 whose `passkey` array has, for each entry, a UUID `id` (unique in the answer)
 * and a `created_at` that is null or a date the browser can read. Unknown keys are ignored; anything
 * else is null, so no row, Add or Remove is ever built from it.
 */
export function parseFactors({ status, body }: Reply): PasskeyEntry[] | null {
  const list = body["passkey"];
  if (status !== 200 || !Array.isArray(list)) return null;
  const seen = new Set<string>();
  const entries: PasskeyEntry[] = [];
  for (const item of list as unknown[]) {
    if (typeof item !== "object" || item === null) return null;
    const { id, created_at: created } = item as Record<string, unknown>;
    if (typeof id !== "string" || !UUID.test(id) || seen.has(id.toLowerCase())) return null;
    if (created !== null && (typeof created !== "string" || !Number.isFinite(Date.parse(created)))) return null;
    seen.add(id.toLowerCase());
    entries.push({ id, createdAt: created });
  }
  return entries;
}

const when = new Intl.DateTimeFormat("en-GB", {
  timeZone: content.timeZone,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** Row text that tells every passkey apart: its added time, numbered " (n)" where two read the same (decision 3). */
export function passkeyRows(entries: PasskeyEntry[]): PasskeyRow[] {
  const texts = entries.map((entry) => (entry.createdAt === null ? content.security.unknown : `${content.security.added} ${when.format(new Date(entry.createdAt))}`));
  const total = new Map<string, number>();
  for (const text of texts) total.set(text, (total.get(text) ?? 0) + 1);
  const count = new Map<string, number>();
  return entries.map((entry, index) => {
    const text = texts[index] ?? "";
    const number = (count.get(text) ?? 0) + 1;
    count.set(text, number);
    return { id: entry.id, text: (total.get(text) ?? 1) > 1 ? `${text} (${String(number)})` : text };
  });
}

/** The factor list as rows, null when it cannot be trusted (decision 3), or the session is gone. */
export async function readPasskeys(): Promise<PasskeyRow[] | null | "signed-out"> {
  const reply = await get("/api/auth/factors");
  if (reply.status === 401) return "signed-out";
  const entries = parseFactors(reply);
  return entries === null ? null : passkeyRows(entries);
}

/**
 * The one factor operation (spec M3g-2a-2 decision 6), kept here so that it outlives the screen
 * that started it. `phase` is the token gate: a sent change waiting for its answer, or one whose
 * answer and session read both failed, so the token may be stale until a read succeeds. `working`
 * is the person's operation, from Add or Remove until its list read has answered; the gate opens
 * before that.
 */
type Phase = "idle" | "sent" | "unresolved";
let phase: Phase = "idle";
let working = false;
/** The running operation's own controller, so Sign out can stop it before anything is sent (6(a)). */
let flight: AbortController | null = null;
let leaving = false;
const watchers = new Set<() => void>();

function enter(next: Phase, busy = working) {
  phase = next;
  working = busy;
  hold(next !== "idle");
  for (const watch of watchers) watch();
}

export const operation = {
  subscribe: (watch: () => void) => {
    watchers.add(watch);
    return () => { watchers.delete(watch); };
  },
  phase: (): Phase => phase,
  /** While true every factor control is off and a repeated activation does nothing (decision 6(d)). */
  busy: (): boolean => working,
};

/** Sign out has begun: no operation starts, and a running one stops if nothing is sent yet, until `stay`. */
export function leave(): void {
  leaving = true;
  flight?.abort();
}

export function stay(): void {
  leaving = false;
}

/** For Sign out: false while a sent change is unreconciled, or while its session cannot be read (6(e)). */
export async function trusted(): Promise<boolean> {
  if (phase === "sent") return false;
  if (phase === "idle") return true;
  if ((await readSession()) === null) return false;
  if (operation.phase() === "unresolved") enter("idle");
  return true;
}

/** What an add tells its screen; null when the screen left before anything was sent, or another operation runs. */
export type Added = "added" | "unconfirmed" | "stepup" | "failed" | "unsupported" | "signed-out" | "offline" | "error" | "unsure";
/** An add's result and, after a sent confirm, the list read it waited for. */
export type Adding = { result: Added; rows?: Awaited<ReturnType<typeof readPasskeys>> };

function begun({ status, body }: Reply): Added {
  if (status === 403 && body["error"] === "stepup-required") return "stepup";
  if (status === 401 && body["error"] === "signed-out") return "signed-out";
  return status === 0 ? "offline" : "error";
}

/** A sent confirm's answer: what may be claimed, and whether the token is trusted again (6(b), 6(f)).
 * Only the exact success shape with this attempt's factor id is "added"; a refusal is definite; anything
 * else is "unconfirmed" whatever the list later shows, and the session read decides the token. */
async function settle(answer: Reply): Promise<[Added, boolean]> {
  const { status, body } = answer;
  if (status >= 400 && status < 500 && typeof body["error"] === "string") return [status === 401 && body["error"] === "signed-out" ? "signed-out" : "failed", true];
  const id = body["factor_id"];
  const exact = typeof id === "string" && UUID.test(id) && typeof body["csrf"] === "string" && body["csrf"] !== "";
  if (exact && (await rotated(answer, "added", "signed_in"))) return ["added", true];
  return ["unconfirmed", (await readSession()) !== null];
}

/** Runs one operation at a time (6(d)): null when another runs or Sign out has begun. `signal` stops
 * it only before its mutation is sent; a sent one always runs to its answer and reconciles. */
async function operate<T>(signal: AbortSignal, run: (signal: AbortSignal) => Promise<T | null>): Promise<T | null> {
  if (working || leaving) return null;
  const own = new AbortController();
  signal.addEventListener("abort", () => { own.abort(); });
  flight = own;
  enter(phase, true);
  try {
    return await run(own.signal);
  } finally {
    flight = null;
    enter(operation.phase(), false);
  }
}

/** After an unresolved change: false while its session still cannot be read, so no protected POST goes out (6(b)). */
async function reread(signal: AbortSignal): Promise<boolean> {
  if ((await readSession(signal)) === null) return false;
  enter("idle");
  return true;
}

/** Begin, the creation ceremony and confirm with exactly `{credential}`, then the list read. */
export const addPasskey = (signal: AbortSignal): Promise<Adding | null> => operate(signal, adding);

async function adding(signal: AbortSignal): Promise<Adding | null> {
  if (phase === "unresolved" && !(await reread(signal))) return { result: "unsure" };
  if (signal.aborted) return null;
  const done = await round("/api/auth/factors/passkey", "/api/auth/factors/passkey/confirm", signal, {}, () => { enter("sent"); }, registration);
  if (done === null) return null;
  const { answer, outcome } = done;
  if (outcome === null || typeof outcome !== "object") return { result: outcome ?? begun(answer) };
  const [result, reconciled] = await settle(answer);
  enter(reconciled ? "idle" : "unresolved");
  return result === "added" || result === "unconfirmed" ? { result, rows: await readPasskeys() } : { result };
}

/** What a remove tells its screen (decision 7); "unconfirmed" only when its list read failed too. */
export type Removed = "removed" | "not-removed" | "gone" | "unconfirmed" | "stepup" | "signed-out" | "error" | "unsure";
export type Removing = { result: Removed; rows?: Awaited<ReturnType<typeof readPasskeys>> };

/** A sent remove's answer (6(b), 6(f)): only the exact success shape is "removed"; a refusal is definite;
 * anything else is "unconfirmed" until the list read, and the session read decides the token. */
async function removal(answer: Reply): Promise<[Removed, boolean]> {
  const { status, body } = answer;
  const error = body["error"];
  if (status >= 400 && status < 500 && typeof error === "string") {
    if (status === 403 && error === "stepup-required") return ["stepup", true];
    if (status === 401 && error === "signed-out") return ["signed-out", true];
    return [(status === 404 && error === "not-found") || (status === 409 && error === "last-factor") ? "gone" : "error", true];
  }
  const exact = typeof body["csrf"] === "string" && body["csrf"] !== "";
  if (exact && (await rotated(answer, "removed", "signed_in"))) return ["removed", true];
  return ["unconfirmed", (await readSession()) !== null];
}

/** `POST /api/auth/factors/passkey/remove {id}`, then the list read. After an unconfirmed answer the
 * selected id decides (6(f)): absent from a parsed list is removed, present is not removed. */
export const removePasskey = (id: string, signal: AbortSignal): Promise<Removing | null> => operate(signal, (own) => removing(id, own));

async function removing(id: string, signal: AbortSignal): Promise<Removing | null> {
  if (phase === "unresolved" && !(await reread(signal))) return { result: "unsure" };
  if (signal.aborted) return null;
  enter("sent");
  const [result, reconciled] = await removal(await post("/api/auth/factors/passkey/remove", { id }));
  enter(reconciled ? "idle" : "unresolved");
  if (result !== "removed" && result !== "gone" && result !== "unconfirmed") return { result };
  const rows = await readPasskeys();
  if (result !== "unconfirmed" || !Array.isArray(rows)) return { result, rows };
  return { result: rows.some((row) => row.id === id) ? "not-removed" : "removed", rows };
}
