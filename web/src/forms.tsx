import type { ChangeEvent, Ref } from "react";

type FieldProps = {
  id: string;
  label: string;
  type: "text" | "email" | "password";
  value: string;
  onChange: (value: string) => void;
  autoComplete: string;
  help?: string;
  errorId?: string;
  inputRef?: Ref<HTMLInputElement>;
};

/** A labelled input. `errorId` names the message that describes it while one is showing (A11Y-03). */
export function Field({ id, label, type, value, onChange, autoComplete, help, errorId, inputRef }: FieldProps) {
  const helpId = help ? `${id}-help` : undefined;
  const described = [helpId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {help ? (
        <p id={helpId} className="field-help">
          {help}
        </p>
      ) : null}
      <input
        id={id}
        ref={inputRef}
        name={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        autoCapitalize="none"
        spellCheck={false}
        required
        aria-invalid={errorId ? true : undefined}
        aria-describedby={described}
        onChange={(event: ChangeEvent<HTMLInputElement>) => { onChange(event.target.value); }}
      />
    </div>
  );
}

/** The polite live region stays in the page so a screen reader hears the message when it appears. */
export function Message({ id, text }: { id: string; text: string | null }) {
  return (
    <div id={id} className="message" aria-live="polite">
      {text}
    </div>
  );
}
