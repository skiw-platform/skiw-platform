import { useEffect, useRef, useState } from "react";

import { post, sessionState, type SessionState } from "./api";
import { content } from "./content";
import { leaveEnrol, onEnrolPath, takeToken } from "./enrolLink";
import { EnrolMissing, EnrolPassword, EnrolSetup, type Setup } from "./screens/Enrol";
import { Recovery } from "./screens/Recovery";
import { SecondFactor } from "./screens/SecondFactor";
import { SignIn } from "./screens/SignIn";

type Shown = {
  kind: SessionState | "recovery";
  notice: string | null;
  setup: Setup | null;
  codes: string[];
};
type View = { kind: "loading" } | Shown;
type Extra = { notice?: string; setup?: Setup; codes?: string[] };
const NOTHING: Omit<Shown, "kind"> = { notice: null, setup: null, codes: [] };

export function App() {
  const [view, setView] = useState<View>({ kind: "loading" });
  const [moves, setMoves] = useState(0);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let live = true;
    void sessionState().then((kind) => {
      if (live) setView({ kind, ...NOTHING });
    });
    return () => {
      live = false;
    };
  }, []);

  // After the person acts, the new screen takes focus; the first load leaves focus where it is.
  useEffect(() => {
    if (moves > 0) mainRef.current?.focus();
  }, [moves]);

  function go(kind: SessionState | "recovery", extra: Extra = {}) {
    setView({ kind, ...NOTHING, ...extra });
    setMoves((count) => count + 1);
  }

  async function signOut() {
    setSignOutError(null);
    setSigningOut(true);
    const { status } = await post("/api/auth/logout", {});
    setSigningOut(false);
    if (status === 200 || status === 401) go("signed_out");
    else setSignOutError(status === 0 ? content.errors.network : content.errors.generic);
  }

  const [signingOut, setSigningOut] = useState(false);
  const signedIn = view.kind === "signed_in";
  return (
    <div className={signedIn ? "app" : "app app--solo"}>
      <a className="skip-link" href="#main">
        {content.skipLink}
      </a>
      <header className="topbar">
        <p className="brand">{content.product}</p>
        {signedIn ? (
          <button type="button" className="link" disabled={signingOut} onClick={() => void signOut()}>
            {signingOut ? content.signOutBusy : content.signOut}
          </button>
        ) : null}
      </header>
      {signedIn ? (
        <nav className="sidebar" aria-label={content.navLabel}>
          <ul>
            {content.nav.map((item) => (
              <li key={item.href}>
                <a href={item.href} aria-current="page">
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      <main id="main" tabIndex={-1} ref={mainRef}>
        <Screen view={view} go={go} signOutError={signOutError} />
      </main>
    </div>
  );
}

type ScreenProps = {
  view: Shown | { kind: "loading" };
  go: (kind: SessionState | "recovery", extra?: Extra) => void;
  signOutError: string | null;
};

function Screen({ view, go, signOutError }: ScreenProps) {
  switch (view.kind) {
    case "loading":
      return (
        <>
          <h1>{content.loading.title}</h1>
          <p role="status">{content.loading.status}</p>
        </>
      );
    case "signed_in":
      return (
        <>
          <h1>{content.pageTitle}</h1>
          <section className="card" aria-labelledby="empty-title">
            <h2 id="empty-title">{content.emptyTitle}</h2>
            <p>{content.emptyBody}</p>
          </section>
          <div aria-live="polite" className="message">
            {signOutError}
          </div>
        </>
      );
    case "second_factor":
      return <SecondFactor onNext={go} />;
    case "enrol_factor":
      return <EnrolSetup setup={view.setup} go={go} />;
    case "recovery":
      return (
        <Recovery
          codes={view.codes}
          onDone={() => {
            leaveEnrol();
            go("signed_in");
          }}
        />
      );
    case "signed_out":
      return <SignedOut notice={view.notice} go={go} />;
  }
}

/** `/enrol` shows the invitation screens; anywhere else a signed-out visitor signs in. */
function SignedOut({ notice, go }: { notice: string | null; go: ScreenProps["go"] }) {
  if (!onEnrolPath()) return <SignIn notice={notice} onNext={go} />;
  const token = takeToken();
  return token ? <EnrolPassword token={token} go={go} /> : <EnrolMissing go={go} />;
}
