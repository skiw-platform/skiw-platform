import { useEffect, useRef, useState, type KeyboardEvent, type SubmitEvent } from "react";

import { post, type Reply } from "../api";
import { content } from "../content";
import { aboutCode, Field, Message, refusal } from "../forms";
import { passkeySupported, round } from "../passkey";

type Props = {
  /** One of the server's listed purposes, for example `factor.change`. */
  purpose: string;
  /** The server's answer names when the confirmation stops counting. */
  onVerified: (until: string) => void;
  onCancel: () => void;
  /** The server no longer knows this user (stopped being active): the page goes to sign-in. */
  onSignedOut: () => void;
};

/**
 * Asks a signed-in person for a fresh authenticator code, or a passkey, before a sensitive action
 * (spec D7, AUTH-09). The passkey screens mount it for `factor.change` (DECISIONS "M3g-2a"). The
 * code and the credential live in this component only.
 */
export function StepUp({ purpose, onVerified, onCancel, onSignedOut }: Props) {
  const [code, setCode] = useState("");
  /** Only a refused code marks the field; every other message is a status (A11Y-03). */
  const [codeError, setCodeError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [offerPasskey, setOfferPasskey] = useState(passkeySupported);
  const codeRef = useRef<HTMLInputElement>(null);
  const passkeyRef = useRef<HTMLButtonElement>(null);
  /** Counts the failed passkey rounds: each one hands focus back to the button once it is enabled again. */
  const [retried, setRetried] = useState(0);
  /** This dialog's request in flight, code or passkey: Cancel, Escape and closing abort it at once, and
   * a late answer then calls nothing, even one that had already arrived (decision 6(d)). */
  const flight = useRef<AbortController | null>(null);

  useEffect(() => {
    codeRef.current?.focus();
    return () => { flight.current?.abort(); };
  }, []);

  useEffect(() => {
    if (retried > 0) passkeyRef.current?.focus();
  }, [retried]);

  function say(field: string | null, general: string | null) {
    setCodeError(field);
    setStatus(general);
  }

  /** Cancel stays available while either request is in flight, and stops it. */
  function cancel() {
    flight.current?.abort();
    onCancel();
  }

  /** The answers both routes share; false when the dialog stays open. */
  function settled({ status, body }: Reply): boolean {
    if (status === 200 && body["next"] === "verified" && typeof body["until"] === "string") onVerified(body["until"]);
    else if (status === 401 && body["error"] === "signed-out") onSignedOut();
    else return false;
    return true;
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const controller = new AbortController();
    flight.current = controller;
    setBusy(true);
    say(null, null);
    const answer = await post("/api/auth/stepup", { purpose, code }, controller.signal);
    if (controller.signal.aborted) return;
    setBusy(false);
    if (settled(answer)) return;
    setCode("");
    const words = refusal(answer.status, content.errors.codeWrong);
    if (aboutCode(answer.status)) say(words, null);
    else say(null, words);
    codeRef.current?.focus();
  }

  /** As at sign-in, a cancelled and a refused passkey get the same words. */
  async function passkey() {
    flight.current?.abort();
    const controller = new AbortController();
    flight.current = controller;
    setBusy(true);
    say(null, null);
    const done = await round("/api/auth/stepup/passkey", "/api/auth/stepup/passkey/confirm", controller.signal, { purpose });
    // A sent confirm runs to its answer (the token stays coherent); after Cancel it calls nothing.
    if (done === null || controller.signal.aborted) return;
    const { answer, outcome: result } = done;
    setBusy(false);
    if (settled(answer)) return;
    if (answer.status === 409 || result === "unsupported") {
      setOfferPasskey(false);
      say(null, result === "unsupported" ? content.passkeys.unsupported : content.stepUp.noPasskey);
      codeRef.current?.focus();
      return;
    }
    const failed = content.stepUp.passkeyFailed;
    say(null, result === "failed" || answer.status === 400 ? failed : refusal(answer.status, failed));
    setRetried((count) => count + 1);
  }

  /** Escape cancels; Tab and Shift-Tab wrap inside the dialog, since the page around it is inert (decision 6(d)). */
  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") cancel();
    if (event.key !== "Tab") return;
    const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("input, button:not(:disabled)"));
    if (document.activeElement !== (event.shiftKey ? controls[0] : controls.at(-1))) return;
    event.preventDefault();
    (event.shiftKey ? controls.at(-1) : controls[0])?.focus();
  }

  return (
    <section
      role="dialog"
      aria-modal="true"
      aria-labelledby="stepup-title"
      className="card"
      onKeyDown={keys}
    >
      <h2 id="stepup-title">{content.stepUp.title}</h2>
      <p>{content.stepUp.intro}</p>
      <form onSubmit={(event) => void submit(event)} className="form">
        <Field id="stepup-code" label={content.stepUp.label} type="text" value={code} onChange={setCode} autoComplete="one-time-code" inputMode="numeric" errorId={codeError ? "stepup-error" : undefined} inputRef={codeRef} />
        <Message id="stepup-error" text={codeError} />
        <Message id="stepup-status" text={status} />
        <div className="actions">
          <button type="submit" disabled={busy}>
            {busy ? content.stepUp.busy : content.stepUp.submit}
          </button>
          {offerPasskey ? (
            <button type="button" className="secondary" ref={passkeyRef} disabled={busy} onClick={() => void passkey()}>
              {content.stepUp.passkey}
            </button>
          ) : null}
          <button type="button" className="link" onClick={cancel}>
            {content.stepUp.cancel}
          </button>
        </div>
      </form>
    </section>
  );
}
