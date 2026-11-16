// The browser half of a passkey assertion (plan M3 §3 M3g; registration joins in M3g-2a-2). The
// server's options arrive as py_webauthn JSON, binary fields in base64url; the credential goes back
// in the same form. Options, challenge and credential live only in the caller's call: nothing
// here stores, logs or keeps them.

import { post, type Reply } from "./api";

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
