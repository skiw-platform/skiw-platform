import { useState } from "react";

import { content } from "../content";

/** The codes live only in this component's props: shown once, never stored by the page. */
export function Recovery({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [note, setNote] = useState<string | null>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(codes.join("\n"));
      setNote(content.recovery.copied);
    } catch {
      setNote(content.recovery.copyFailed);
    }
  }

  return (
    <>
      <h1>{content.recovery.title}</h1>
      <p>{content.recovery.intro}</p>
      <ul className="codes" aria-label={content.recovery.list}>
        {codes.map((code) => (
          <li key={code}>
            <code>{code}</code>
          </li>
        ))}
      </ul>
      <div className="actions">
        <button type="button" onClick={() => void copy()}>
          {content.recovery.copy}
        </button>
        <button type="button" onClick={onDone}>
          {content.recovery.done}
        </button>
      </div>
      <div aria-live="polite" className="note">
        {note}
      </div>
    </>
  );
}
