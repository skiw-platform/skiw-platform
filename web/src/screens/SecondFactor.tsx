import { useRef, useState, type SubmitEvent } from "react";

import { post, type SessionState } from "../api";
import { content } from "../content";
import { Field, Message } from "../forms";

type Props = { onNext: (state: SessionState, notice?: string) => void };

export function SecondFactor({ onNext }: Props) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { status, body } = await post("/api/auth/second-factor", { code });
    setBusy(false);
    if (status === 200 && body["next"] === "signed_in") {
      onNext("signed_in");
      return;
    }
    if (status === 401 && body["error"] === "login-expired") {
      onNext("signed_out", content.errors.expired);
      return;
    }
    setCode("");
    setError(
      status === 401 ? content.errors.codeWrong : status === 429 ? content.errors.limited : status === 400 ? content.errors.invalid : status === 0 ? content.errors.network : content.errors.generic,
    );
    codeRef.current?.focus();
  }

  return (
    <>
      <h1>{content.secondFactor.title}</h1>
      <form onSubmit={(event) => void submit(event)} className="form">
        <Field id="code" label={content.secondFactor.label} type="text" value={code} onChange={setCode} autoComplete="one-time-code" help={content.secondFactor.help} errorId={error ? "code-error" : undefined} inputRef={codeRef} />
        <Message id="code-error" text={error} />
        <button type="submit" disabled={busy}>
          {busy ? content.secondFactor.busy : content.secondFactor.submit}
        </button>
      </form>
      <p>
        <button type="button" className="link" onClick={() => { onNext("signed_out"); }}>
          {content.secondFactor.back}
        </button>
      </p>
    </>
  );
}
