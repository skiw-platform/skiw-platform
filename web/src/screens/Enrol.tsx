import { useRef, useState, type SubmitEvent } from "react";

import { post, type SessionState } from "../api";
import { content } from "../content";
import { leaveEnrol } from "../enrolLink";
import { Field, Message } from "../forms";

export type Setup = { secret: string; uri: string };
type Go = (kind: SessionState | "recovery", extra?: { notice?: string; setup?: Setup; codes?: string[] }) => void;

function expire(go: Go) {
  leaveEnrol();
  go("signed_out", { notice: content.setup.expired });
}

/** The setup key in groups of four so it is easy to read out and type. */
const grouped = (secret: string) => secret.replace(/(.{4})(?=.)/g, "$1 ");

function setupFrom(body: Record<string, unknown>): Setup | null {
  const { secret, uri } = body;
  return typeof secret === "string" && typeof uri === "string" ? { secret, uri } : null;
}

/** The invitation token goes in the body of this one POST and nowhere else. */
export function EnrolPassword({ token, go }: { token: string; go: Go }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const first = await post("/api/auth/enrol", { token, password });
    if (first.status === 200 && first.body["next"] === "enrol_factor") {
      const second = await post("/api/auth/enrol/totp", {});
      const setup = second.status === 200 ? setupFrom(second.body) : null;
      go("enrol_factor", setup ? { setup } : {});
      return;
    }
    setBusy(false);
    setPassword("");
    setError(first.status === 401 ? content.enrol.failed : first.status === 0 ? content.errors.network : content.errors.generic);
    passwordRef.current?.focus();
  }

  return (
    <>
      <h1>{content.enrol.title}</h1>
      <form onSubmit={(event) => void submit(event)} className="form">
        <Field id="new-password" label={content.enrol.password} type="password" value={password} onChange={setPassword} autoComplete="new-password" minLength={12} help={content.enrol.help} errorId={error ? "enrol-error" : undefined} inputRef={passwordRef} />
        <Message id="enrol-error" text={error} />
        <button type="submit" disabled={busy}>
          {busy ? content.enrol.busy : content.enrol.submit}
        </button>
      </form>
    </>
  );
}

export function EnrolMissing({ go }: { go: Go }) {
  return (
    <>
      <h1>{content.enrol.missingTitle}</h1>
      <p>{content.enrol.missing}</p>
      <p>
        <a href="/" onClick={(event) => {
            event.preventDefault();
            leaveEnrol();
            go("signed_out");
          }}>
          {content.enrol.toSignIn}
        </a>
      </p>
    </>
  );
}

/** The authenticator step. `setup` is missing after a reload: the key is shown only on request,
 * because asking replaces any earlier unconfirmed key. */
export function EnrolSetup({ setup: first, go }: { setup: Setup | null; go: Go }) {
  const [setup, setSetup] = useState<Setup | null>(first);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const codeRef = useRef<HTMLInputElement>(null);

  async function show() {
    setError(null);
    const { status, body } = await post("/api/auth/enrol/totp", {});
    const next = status === 200 ? setupFrom(body) : null;
    if (next) setSetup(next);
    else if (status === 401) expire(go);
    else setError(status === 0 ? content.errors.network : content.errors.generic);
  }

  async function confirm(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const { status, body } = await post("/api/auth/enrol/totp/confirm", { code });
    setBusy(false);
    const codes = body["recovery_codes"];
    if (status === 200 && body["next"] === "signed_in" && Array.isArray(codes)) {
      go("recovery", { codes: codes.map(String) });
      return;
    }
    if (status === 401 && body["error"] === "enrol-expired") {
      expire(go);
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
      <h1>{content.setup.title}</h1>
      {setup ? (
        <>
          <p>{content.setup.intro}</p>
          <p>
            {content.setup.keyLabel}: <code className="secret">{grouped(setup.secret)}</code>
          </p>
          <p>
            <a href={setup.uri}>{content.setup.open}</a>
          </p>
          <form onSubmit={(event) => void confirm(event)} className="form">
            <Field id="setup-code" label={content.setup.code} type="text" value={code} onChange={setCode} autoComplete="one-time-code" inputMode="numeric" errorId={error ? "setup-error" : undefined} inputRef={codeRef} />
            <Message id="setup-error" text={error} />
            <button type="submit" disabled={busy}>
              {busy ? content.setup.busy : content.setup.submit}
            </button>
          </form>
        </>
      ) : (
        <>
          <button type="button" onClick={() => void show()}>
            {content.setup.show}
          </button>
          <Message id="setup-error" text={error} />
        </>
      )}
    </>
  );
}
