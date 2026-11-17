import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";

import { content } from "../content";
import { Message } from "../forms";
import { addPasskey, operation, passkeySupported, readPasskeys, type Added, type PasskeyRow } from "../passkey";
import { StepUp } from "./StepUp";

type Load = { kind: "loading" } | { kind: "error" } | { kind: "ready"; rows: PasskeyRow[] };

type Props = {
  /** The server no longer knows this person: the page goes to sign-in. */
  onSignedOut: () => void;
  /** The step-up dialog opened or closed: everything outside it is inert meanwhile (decision 6(d)). */
  onModal: (open: boolean) => void;
};

const count = (total: number) => (total === 0 ? content.security.empty : total === 1 ? content.security.one : content.security.many(total));

/** The words for an add that added nothing; one text for every failed ceremony or refusal (AUTH-05). */
const FAILED: Partial<Record<Added, string>> = {
  failed: content.security.notAdded,
  offline: content.errors.network,
  unsure: content.sessionUnsure,
};

/**
 * The person's own passkeys, read from the server on every visit and kept in this component only,
 * and Add (spec M3g-2a-2, decisions 3 to 8). The add itself runs in `passkey.ts`, so a sent one
 * finishes after this screen is gone; this screen then shows nothing of it.
 */
export function Security({ onSignedOut, onModal }: Props) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [status, setStatus] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [canAdd, setCanAdd] = useState(passkeySupported);
  const [stepUp, setStepUp] = useState(false);
  /** Where focus goes once the render it waits for is in the page (decision 8). */
  const [focus, setFocus] = useState<{ to: "heading" | "add" } | null>(null);
  const retryRef = useRef<HTMLButtonElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const addRef = useRef<HTMLButtonElement>(null);
  /** This screen's add; leaving aborts it, which stops it only before confirm is sent. */
  const flight = useRef<AbortController | null>(null);
  const busy = useSyncExternalStore(operation.subscribe, operation.busy, operation.busy);
  /** An add from an earlier visit is still running: the list is read once it has finished (6(d)). */
  const [waiting, setWaiting] = useState(busy);
  if (waiting && !busy) setWaiting(false);

  useEffect(() => () => { flight.current?.abort(); }, []);

  // Before paint, so the dialog never shows over a page that can still take focus.
  useLayoutEffect(() => {
    onModal(stepUp);
    return () => { onModal(false); };
  }, [stepUp, onModal]);

  // In the commit that shows the words, so focus and status arrive together.
  useLayoutEffect(() => {
    if (focus !== null) (focus.to === "heading" ? headingRef : addRef).current?.focus();
  }, [focus]);

  function show(rows: PasskeyRow[] | null, words: string) {
    setLoad(rows === null ? { kind: "error" } : { kind: "ready", rows });
    setStatus(words);
  }

  useEffect(() => {
    if (waiting) return;
    let live = true;
    void readPasskeys().then((rows) => {
      if (!live) return;
      if (rows === "signed-out") onSignedOut();
      else show(rows, rows === null ? content.security.loadError : count(rows.length));
    });
    return () => {
      live = false;
    };
  }, [attempt, onSignedOut, waiting]);

  // The failed load leaves one way forward, so focus goes to it (spec 5.1).
  useLayoutEffect(() => {
    if (load.kind === "error") retryRef.current?.focus();
  }, [load]);

  function retry() {
    setLoad({ kind: "loading" });
    setStatus(null);
    setAttempt((total) => total + 1);
  }

  function say(words: string, to: "heading" | "add") {
    setStatus(words);
    setFocus({ to });
  }

  /** `again` after a verified step-up: a second stepup-required is an error, never another dialog (decision 4). */
  async function add(again: boolean) {
    const controller = new AbortController();
    flight.current = controller;
    const gone = () => controller.signal.aborted;
    setStatus(null);
    const done = await addPasskey(controller.signal);
    if (done === null || gone()) return;
    const { result, rows } = done;
    if (result === "signed-out") {
      onSignedOut();
    } else if (result === "stepup" && !again) {
      setStepUp(true);
    } else if (result === "unsupported") {
      setCanAdd(false);
      say(content.passkeys.unsupported, "heading");
    } else if (rows !== undefined) {
      if (rows === "signed-out") onSignedOut();
      else if (rows === null) show(null, content.security.listUnsure);
      else {
        show(rows, result === "added" ? content.security.addedNotice : content.security.unconfirmed);
        setFocus({ to: result === "added" ? "heading" : "add" });
      }
    } else {
      say(FAILED[result] ?? content.errors.generic, "add");
    }
  }

  return (
    <>
      <h1 tabIndex={-1} ref={headingRef} inert={stepUp}>
        {content.security.title}
      </h1>
      <section className="card" aria-labelledby="passkeys-title" aria-busy={load.kind === "loading"} inert={stepUp}>
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
        {load.kind === "ready" && canAdd ? (
          <div className="actions">
            <button type="button" ref={addRef} disabled={busy} onClick={() => void add(false)}>
              {busy ? content.security.addBusy : content.security.add}
            </button>
          </div>
        ) : null}
      </section>
      {stepUp ? (
        <StepUp
          purpose="factor.change"
          onVerified={() => {
            setStepUp(false);
            // A verification that answers after this screen has gone starts nothing.
            if (flight.current?.signal.aborted === false) void add(true);
          }}
          onCancel={() => {
            setStepUp(false);
            setFocus({ to: "add" });
          }}
          onSignedOut={onSignedOut}
        />
      ) : null}
      <Message id="security-status" text={status} />
    </>
  );
}
