// The browser half of a passkey assertion (plan M3 §3 M3g; registration joins in M3g-2a-2). The
// server's options arrive as py_webauthn JSON, binary fields in base64url; the credential goes back
// in the same form. Options, challenge and credential live only in the caller's call: nothing
// here stores, logs or keeps them.

import { post, type Reply } from "./api";
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

function encode(credential: PublicKeyCredential): Json {
  const answer = credential.response as Response;
  const response: Json = { clientDataJSON: text(answer.clientDataJSON) };
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
    return error instanceof DOMException && error.name === "NotSupportedError" ? "unsupported" : "failed";
  }
}

/** One click's round: begin, the assertion, confirm. `answer` is the confirm's, or the begin's
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
): Promise<Round | null> {
  const begun = await post(begin, {}, signal);
  if (left(signal)) return null;
  const options = begun.body["options"];
  const usable = begun.status === 200 && typeof options === "object" && options !== null;
  const outcome = usable ? await assertion(options as Json, signal) : null;
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
