import { useEffect, useRef, useState, type KeyboardEvent, type SubmitEvent } from "react";

import { post } from "../api";
import { content } from "../content";
import { Field, Message } from "../forms";

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
 * Asks a signed-in person for a fresh authenticator code before a sensitive action (spec D7,
 * AUTH-09). No screen uses it yet: the M3 actions it guards have no screens, and the later
 * modules that do import this one (DECISIONS "M3i-3"). The code lives in this component only.
 */
export function StepUp({ purpose, onVerified, onCancel, onSignedOut }: Props) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    codeRef.current?.focus();
  }, []);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { status, body } = await post("/api/auth/stepup", { purpose, code });
    setBusy(false);
    if (status === 200 && body["next"] === "verified" && typeof body["until"] === "string") {
      onVerified(body["until"]);
      return;
    }
    if (status === 401 && body["error"] === "signed-out") {
      onSignedOut();
      return;
    }
    setCode("");
    setError(
      status === 401
        ? content.errors.codeWrong
        : status === 429
          ? content.errors.limited
          : status === 400
            ? content.errors.invalid
            : status === 0
              ? content.errors.network
              : content.errors.generic,
    );
    codeRef.current?.focus();
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
          <button type="button" className="link" onClick={onCancel}>
            {content.stepUp.cancel}
          </button>
        </div>
      </form>
    </section>
  );
}
