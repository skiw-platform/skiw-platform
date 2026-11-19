import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";

import { content } from "../content";
import { Message } from "../forms";
import { addPasskey, operation, type PasskeyRow } from "../passkey";
import { FAILED } from "./Security";
import { StepUp } from "./StepUp";

type Props = {
  /** Skip, or an add the server confirmed (with the words Today announces). */
  onDone: (notice?: string) => void;
  onSignedOut: () => void;
  /** The step-up dialog opened or closed: everything outside it is inert meanwhile (decision 6(d)). */
  onModal: (open: boolean) => void;
};

/**
 * "Add a passkey?", once, after the recovery codes (spec M3g-2a-2 decision 10, flow 5.4); App shows
 * it only where WebAuthn exists. Add is Security's add (decisions 4 to 6, the same runner); it reads
 * nothing before begin. Only an add the server confirmed leaves for Today: an unconfirmed one stays
 * here with the list, as 6(f) says.
 */
export function Offer({ onDone, onSignedOut, onModal }: Props) {
  const [status, setStatus] = useState<string | null>(null);
  const [rows, setRows] = useState<PasskeyRow[] | null>(null);
  const [canAdd, setCanAdd] = useState(true);
  const [stepUp, setStepUp] = useState(false);
  const [focus, setFocus] = useState<{ to: "add" | "skip" } | null>(null);
  const addRef = useRef<HTMLButtonElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);
  /** Leaving (Skip) aborts the add, which stops it only before confirm is sent. */
  const flight = useRef<AbortController | null>(null);
  const busy = useSyncExternalStore(operation.subscribe, operation.busy, operation.busy);

  useEffect(() => () => { flight.current?.abort(); }, []);

  useLayoutEffect(() => {
    onModal(stepUp);
    return () => { onModal(false); };
  }, [stepUp, onModal]);

  useLayoutEffect(() => {
    if (focus !== null) (focus.to === "add" ? addRef : skipRef).current?.focus();
  }, [focus]);

  function say(words: string, to: "add" | "skip") {
    setStatus(words);
    setFocus({ to });
  }

  /** `again` after a verified step-up: a second stepup-required is an error, never another dialog (decision 4). */
  async function add(again: boolean) {
    const controller = new AbortController();
    flight.current = controller;
    setStatus(null);
    const done = await addPasskey(controller.signal);
    if (done === null || controller.signal.aborted) return;
    const { result, rows: read } = done;
    if (result === "signed-out" || read === "signed-out") {
      onSignedOut();
    } else if (result === "stepup" && !again) {
      setStepUp(true);
    } else if (result === "unsupported") {
      setCanAdd(false);
      say(content.passkeys.unsupported, "skip");
    } else if (read === null) {
      setRows(null);
      say(content.security.listUnsure, "add");
    } else if (result === "added") {
      onDone(content.security.addedNotice);
    } else if (read !== undefined) {
      setRows(read);
      say(content.security.unconfirmed, "add");
    } else {
      say(FAILED[result] ?? content.errors.generic, "add");
    }
  }

  return (
    <>
      <div inert={stepUp}>
        <h1>{content.offer.title}</h1>
        <p>{content.security.intro}</p>
        {rows !== null && rows.length === 0 ? <p>{content.security.empty}</p> : null}
        {rows !== null && rows.length > 0 ? (
          <ul className="rows" aria-label={content.security.listTitle}>
            {rows.map((row) => (
              <li key={row.id}>{row.text}</li>
            ))}
          </ul>
        ) : null}
        <div className="actions">
          {canAdd ? (
            <button type="button" ref={addRef} disabled={busy} onClick={() => void add(false)}>
              {busy ? content.security.addBusy : content.security.add}
            </button>
          ) : null}
          <button type="button" className="secondary" ref={skipRef} onClick={() => { onDone(); }}>
            {content.offer.skip}
          </button>
        </div>
      </div>
      {stepUp ? (
        <StepUp
          purpose="factor.change"
          onVerified={() => {
            setStepUp(false);
            void add(true);
          }}
          onCancel={() => {
            setStepUp(false);
            setFocus({ to: "add" });
          }}
          onSignedOut={onSignedOut}
        />
      ) : null}
      <Message id="offer-status" text={status} />
    </>
  );
}
