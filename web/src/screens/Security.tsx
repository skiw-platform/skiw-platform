import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";

import { content } from "../content";
import { Message } from "../forms";
import { addPasskey, operation, passkeySupported, readPasskeys, removePasskey, type Added, type PasskeyRow, type Removed } from "../passkey";
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
export const FAILED: Partial<Record<Added, string>> = {
  failed: content.security.notAdded,
  offline: content.errors.network,
  unsure: content.sessionUnsure,
};

/** The words for a remove whose answer the list read followed (decision 7, 6(f)). */
const REMOVED: Partial<Record<Removed, string>> = {
  removed: content.security.removedNotice,
  "not-removed": content.security.notRemoved,
  gone: content.security.gone,
};

/**
 * The person's own passkeys, read from the server on every visit and kept in this component only,
 * Add and Remove (spec M3g-2a-2, decisions 3 to 8). Both run in `passkey.ts`, so a sent one finishes
 * after this screen is gone; this screen then shows nothing of it.
 */
export function Security({ onSignedOut, onModal }: Props) {
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [status, setStatus] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [canAdd, setCanAdd] = useState(passkeySupported);
  /** The open dialog: what runs once more after it is verified, and the control Cancel returns to. */
  const [stepUp, setStepUp] = useState<{ again: () => void; back: string } | null>(null);
  /** The one row whose removal confirmation is open (decision 6(d)). */
  const [asking, setAsking] = useState<string | null>(null);
  /** Where focus goes once the render it waits for is in the page (decision 8): the heading, Add, or
   * the element with that id. */
  const [focus, setFocus] = useState<{ to: string } | null>(null);
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
    onModal(stepUp !== null);
    return () => { onModal(false); };
  }, [stepUp, onModal]);

  // In the commit that shows the words, so focus and status arrive together.
  useLayoutEffect(() => {
    if (focus === null) return;
    (focus.to === "heading" ? headingRef.current : focus.to === "add" ? addRef.current : document.getElementById(focus.to))?.focus();
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

  function say(words: string, to: string) {
    setStatus(words);
    setFocus({ to });
  }

  /** `again` after a verified step-up: a second stepup-required is an error, never another dialog (decision 4). */
  async function add(again: boolean) {
    const controller = new AbortController();
    flight.current = controller;
    const gone = () => controller.signal.aborted;
    setStatus(null);
    setAsking(null);
    const done = await addPasskey(controller.signal);
    if (done === null || gone()) return;
    const { result, rows } = done;
    if (result === "signed-out") {
      onSignedOut();
    } else if (result === "stepup" && !again) {
      setStepUp({ again: () => void add(true), back: "add" });
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

  function ask(id: string | null, back: string) {
    setAsking(id);
    setFocus({ to: back });
  }

  /** As `add`: one more remove after a verified step-up, never a second dialog (decisions 4, 7). */
  async function remove(id: string, again: boolean) {
    const controller = new AbortController();
    flight.current = controller;
    setStatus(null);
    const done = await removePasskey(id, controller.signal);
    if (done === null || controller.signal.aborted) return;
    const { result, rows } = done;
    setAsking(null);
    const back = `remove-${id}`;
    if (result === "signed-out" || rows === "signed-out") {
      onSignedOut();
    } else if (result === "stepup" && !again) {
      setStepUp({ again: () => void remove(id, true), back });
    } else if (rows === null) {
      show(null, content.security.listUnsure);
    } else if (rows !== undefined) {
      show(rows, REMOVED[result] ?? content.errors.generic);
      setFocus({ to: rows.some((row) => row.id === id) ? back : "heading" });
    } else {
      say(result === "unsure" ? content.sessionUnsure : content.errors.generic, back);
    }
  }

  return (
    <>
      <h1 tabIndex={-1} ref={headingRef} inert={stepUp !== null}>
        {content.security.title}
      </h1>
      <section className="card" aria-labelledby="passkeys-title" aria-busy={load.kind === "loading"} inert={stepUp !== null}>
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
              <li key={row.id}>
                <span id={`row-${row.id}`}>{row.text}</span>
                <button type="button" className="secondary" id={`remove-${row.id}`} aria-labelledby={`remove-${row.id} row-${row.id}`} disabled={busy} onClick={() => { ask(row.id, "remove-cancel"); }}>
                  {content.security.remove}
                </button>
                {asking === row.id ? (
                  <div role="group" aria-labelledby="remove-ask" className="actions" onKeyDown={(event) => { if (event.key === "Escape" && !busy) ask(null, `remove-${row.id}`); }}>
                    <p id="remove-ask">{content.security.removeAsk(row.text)}</p>
                    <button type="button" disabled={busy} onClick={() => void remove(row.id, false)}>
                      {busy ? content.security.removeBusy : content.security.remove}
                    </button>
                    <button type="button" className="secondary" id="remove-cancel" disabled={busy} onClick={() => { ask(null, `remove-${row.id}`); }}>
                      {content.security.cancel}
                    </button>
                  </div>
                ) : null}
              </li>
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
            setStepUp(null);
            // Each open is its own StepUp, which calls nothing once cancelled or closed, so this is
            // always the open dialog's answer.
            stepUp.again();
          }}
          onCancel={() => {
            setStepUp(null);
            setFocus({ to: stepUp.back });
          }}
          onSignedOut={onSignedOut}
        />
      ) : null}
      <Message id="security-status" text={status} />
    </>
  );
}
