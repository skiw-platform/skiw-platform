import { useEffect, useRef, useState } from "react";

import { get } from "../api";
import { content } from "../content";
import { Message } from "../forms";
import { parseFactors, passkeyRows, type PasskeyRow } from "../passkey";

type Load = { kind: "loading" } | { kind: "error" } | { kind: "ready"; rows: PasskeyRow[] };

type Props = {
  /** The server no longer knows this person: the page goes to sign-in. */
  onSignedOut: () => void;
};

/**
 * The person's own passkeys, read from the server on every visit and kept in this component only
 * (spec M3g-2a-2, decisions 3 and 8). Add and Remove come in the next PRs.
 */
export function Security({ onSignedOut }: Props) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [status, setStatus] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retryRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let live = true;
    void get("/api/auth/factors").then((reply) => {
      if (!live) return;
      if (reply.status === 401) {
        onSignedOut();
        return;
      }
      const entries = parseFactors(reply);
      if (entries === null) {
        setLoad({ kind: "error" });
        setStatus(content.security.loadError);
        return;
      }
      setLoad({ kind: "ready", rows: passkeyRows(entries) });
      setStatus(entries.length === 0 ? content.security.empty : entries.length === 1 ? content.security.one : content.security.many(entries.length));
    });
    return () => {
      live = false;
    };
  }, [attempt, onSignedOut]);

  // The failed load leaves one way forward, so focus goes to it (spec 5.1).
  useEffect(() => {
    if (load.kind === "error") retryRef.current?.focus();
  }, [load]);

  function retry() {
    setLoad({ kind: "loading" });
    setStatus(null);
    setAttempt((count) => count + 1);
  }

  return (
    <>
      <h1>{content.security.title}</h1>
      <section className="card" aria-labelledby="passkeys-title" aria-busy={load.kind === "loading"}>
        <h2 id="passkeys-title">{content.security.listTitle}</h2>
        <p>{content.security.intro}</p>
        {load.kind === "loading" ? <p role="status">{content.security.loading}</p> : null}
        {load.kind === "error" ? (
          <div className="actions">
            <button type="button" className="secondary" ref={retryRef} onClick={retry}>
              {content.security.retry}
            </button>
          </div>
        ) : null}
        {load.kind === "ready" && load.rows.length === 0 ? <p>{content.security.empty}</p> : null}
        {load.kind === "ready" && load.rows.length > 0 ? (
          <ul className="rows" aria-label={content.security.listTitle}>
            {load.rows.map((row) => (
              <li key={row.id}>{row.text}</li>
            ))}
          </ul>
        ) : null}
      </section>
      <Message id="security-status" text={status} />
    </>
  );
}
