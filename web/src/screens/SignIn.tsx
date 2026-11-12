import { useRef, useState, type SubmitEvent } from "react";

import { post, type SessionState } from "../api";
import { content } from "../content";
import { Field, Message } from "../forms";

type Props = { notice: string | null; onNext: (state: SessionState) => void };

export function SignIn({ notice, onNext }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(notice);
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { status, body } = await post("/api/auth/login", { email, password });
    setBusy(false);
    if (status === 200 && body["next"] === "second_factor") {
      onNext("second_factor");
      return;
    }
    setPassword("");
    setError(
      status === 401 ? content.errors.loginFailed : status === 429 ? content.errors.limited : status === 0 ? content.errors.network : content.errors.generic,
    );
    passwordRef.current?.focus();
  }

  return (
    <>
      <h1>{content.signIn.title}</h1>
      <form onSubmit={(event) => void submit(event)} className="form">
        <Field id="email" label={content.signIn.email} type="email" value={email} onChange={setEmail} autoComplete="username" errorId={error ? "sign-in-error" : undefined} />
        <Field id="password" label={content.signIn.password} type="password" value={password} onChange={setPassword} autoComplete="current-password" errorId={error ? "sign-in-error" : undefined} inputRef={passwordRef} />
        <Message id="sign-in-error" text={error} />
        <button type="submit" disabled={busy}>
          {busy ? content.signIn.busy : content.signIn.submit}
        </button>
      </form>
    </>
  );
}
