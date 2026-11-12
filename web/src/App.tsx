import { useEffect, useRef, useState } from "react";

import { post, sessionState, type SessionState } from "./api";
import { content } from "./content";
import { SecondFactor } from "./screens/SecondFactor";
import { SignIn } from "./screens/SignIn";

type View = { kind: "loading" } | { kind: SessionState; notice: string | null };

export function App() {
  const [view, setView] = useState<View>({ kind: "loading" });
  const [moves, setMoves] = useState(0);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let live = true;
    void sessionState().then((kind) => {
      if (live) setView({ kind, notice: null });
    });
    return () => {
      live = false;
    };
  }, []);

  // After the person acts, the new screen takes focus; the first load leaves focus where it is.
  useEffect(() => {
    if (moves > 0) mainRef.current?.focus();
  }, [moves]);

  function go(kind: SessionState, notice: string | null = null) {
    setView({ kind, notice });
    setMoves((count) => count + 1);
  }

  async function signOut() {
    setSignOutError(null);
    const { status } = await post("/api/auth/logout", {});
    if (status === 200 || status === 401) go("signed_out");
    else setSignOutError(status === 0 ? content.errors.network : content.errors.generic);
  }

  const signedIn = view.kind === "signed_in";
  return (
    <div className={signedIn ? "app" : "app app--solo"}>
      <a className="skip-link" href="#main">
        {content.skipLink}
      </a>
      <header className="topbar">
        <p className="brand">{content.product}</p>
        {signedIn ? (
          <button type="button" className="link" onClick={() => void signOut()}>
            {content.signOut}
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

function Screen({ view, go, signOutError }: { view: View; go: (kind: SessionState, notice?: string | null) => void; signOutError: string | null }) {
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
      return (
        <SecondFactor onNext={go} />
      );
    case "enrol_factor":
      return (
        <>
          <h1>{content.enrolPending.title}</h1>
          <p>{content.enrolPending.body}</p>
          <p>
            <button type="button" className="link" onClick={() => { go("signed_out"); }}>
              {content.enrolPending.back}
            </button>
          </p>
        </>
      );
    case "signed_out":
      return (
        <SignIn notice={view.notice} onNext={go} />
      );
  }
}
