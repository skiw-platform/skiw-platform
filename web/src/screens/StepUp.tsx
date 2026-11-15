import { useEffect, useRef, useState, type KeyboardEvent, type SubmitEvent } from "react";

import { post, type Reply } from "../api";
import { content } from "../content";
import { Field, Message, refusal } from "../forms";
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [offerPasskey, setOfferPasskey] = useState(passkeySupported);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    codeRef.current?.focus();
  }, []);

  /** The answers both routes share; false when the dialog stays open. */
  function settled({ status, body }: Reply): boolean {
    if (status === 200 && body["next"] === "verified" && typeof body["until"] === "string") onVerified(body["until"]);
    else if (status === 401 && body["error"] === "signed-out") onSignedOut();
    else return false;
    return true;
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const answer = await post("/api/auth/stepup", { purpose, code });
    setBusy(false);
    if (settled(answer)) return;
    setCode("");
    setError(refusal(answer.status, content.errors.codeWrong));
    codeRef.current?.focus();
  }

  /** As at sign-in, a cancelled and a refused passkey get the same words. */
  async function passkey() {
    setBusy(true);
    setError(null);
    const { answer, outcome: result } = await round("/api/auth/stepup/passkey", "/api/auth/stepup/passkey/confirm", { purpose });
    setBusy(false);
    if (settled(answer)) return;
    if (answer.status === 409 || result === "unsupported") {
      setOfferPasskey(false);
      setError(result === "unsupported" ? content.passkeys.unsupported : content.stepUp.noPasskey);
      codeRef.current?.focus();
      return;
    }
    const failed = content.stepUp.passkeyFailed;
    setError(result === "failed" || answer.status === 400 ? failed : refusal(answer.status, failed));
  }

  function keys(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") onCancel();
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
        <Field id="stepup-code" label={content.stepUp.label} type="text" value={code} onChange={setCode} autoComplete="one-time-code" inputMode="numeric" errorId={error ? "stepup-error" : undefined} inputRef={codeRef} />
        <Message id="stepup-error" text={error} />
        <div className="actions">
          <button type="submit" disabled={busy}>
            {busy ? content.stepUp.busy : content.stepUp.submit}
          </button>
          {offerPasskey ? (
            <button type="button" className="secondary" disabled={busy} onClick={() => void passkey()}>
              {content.stepUp.passkey}
            </button>
          ) : null}
          <button type="button" className="link" onClick={onCancel}>
            {content.stepUp.cancel}
          </button>
        </div>
      </form>
    </section>
  );
}
