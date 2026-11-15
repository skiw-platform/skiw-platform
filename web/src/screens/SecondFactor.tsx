import { useEffect, useRef, useState, type SubmitEvent } from "react";

import { post, type Reply, type SessionState } from "../api";
import { content } from "../content";
import { aboutCode, Field, Message, refusal } from "../forms";
import { passkeySupported, round } from "../passkey";

type Props = { onNext: (state: SessionState, extra?: { notice: string }) => void };

export function SecondFactor({ onNext }: Props) {
  const [code, setCode] = useState("");
  /** Only a refused code marks the field; every other message is a status (A11Y-03). */
  const [codeError, setCodeError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [offerPasskey, setOfferPasskey] = useState(passkeySupported);
  const codeRef = useRef<HTMLInputElement>(null);
  /** The passkey round in flight; leaving the screen aborts it so a late answer does nothing. */
  const flight = useRef<AbortController | null>(null);

  useEffect(() => () => { flight.current?.abort(); }, []);

  function say(field: string | null, general: string | null) {
    setCodeError(field);
    setStatus(general);
  }

  /** The answers both routes share; false when the page stays on this step. */
  function moved({ status, body }: Reply): boolean {
    if (status === 200 && body["next"] === "signed_in") onNext("signed_in");
    else if (status === 401 && body["error"] === "login-expired") onNext("signed_out", { notice: content.errors.expired });
    else return false;
    return true;
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    say(null, null);
    const answer = await post("/api/auth/second-factor", { code });
    setBusy(false);
    if (moved(answer)) return;
    setCode("");
    const words = refusal(answer.status, content.errors.codeWrong);
    if (aboutCode(answer.status)) say(words, null);
    else say(null, words);
    codeRef.current?.focus();
  }

  /** A cancelled and a refused passkey get the same words: the screen never tells which. */
  async function passkey() {
    flight.current?.abort();
    const controller = new AbortController();
    flight.current = controller;
    setBusy(true);
    say(null, null);
    const done = await round("/api/auth/second-factor/passkey", "/api/auth/second-factor/passkey/confirm", controller.signal);
    if (done === null) return;
    const { answer, outcome: result } = done;
    setBusy(false);
    if (moved(answer)) return;
    if (answer.status === 409 || result === "unsupported") {
      setOfferPasskey(false);
      say(null, result === "unsupported" ? content.passkeys.unsupported : content.secondFactor.noPasskey);
      codeRef.current?.focus();
      return;
    }
    const failed = content.secondFactor.passkeyFailed;
    say(null, result === "failed" || answer.status === 400 ? failed : refusal(answer.status, failed));
  }

  function back() {
    flight.current?.abort();
    onNext("signed_out");
  }

  return (
    <>
      <h1>{content.secondFactor.title}</h1>
      <form onSubmit={(event) => void submit(event)} className="form">
        <Field id="code" label={content.secondFactor.label} type="text" value={code} onChange={setCode} autoComplete="one-time-code" help={content.secondFactor.help} errorId={codeError ? "code-error" : undefined} inputRef={codeRef} />
        <Message id="code-error" text={codeError} />
        <Message id="code-status" text={status} />
        <div className="actions">
          <button type="submit" disabled={busy}>
            {busy ? content.secondFactor.busy : content.secondFactor.submit}
          </button>
          {offerPasskey ? (
            <button type="button" className="secondary" disabled={busy} onClick={() => void passkey()}>
              {busy ? content.secondFactor.passkeyBusy : content.secondFactor.passkey}
            </button>
          ) : null}
        </div>
      </form>
      <p>
        <button type="button" className="link" onClick={back}>
          {content.secondFactor.back}
        </button>
      </p>
    </>
  );
}
