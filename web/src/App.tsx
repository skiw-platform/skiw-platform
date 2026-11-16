import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { endSession, sessionState, unauthenticated, type SessionState } from "./api";
import { content } from "./content";
import { discardInvitation, leaveEnrol, onEnrolPath, takeToken } from "./enrolLink";
import { operation, trusted } from "./passkey";
import { EnrolMissing, EnrolPassword, EnrolSetup, type Setup } from "./screens/Enrol";
import { Recovery } from "./screens/Recovery";
import { SecondFactor } from "./screens/SecondFactor";
import { Security } from "./screens/Security";
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

type Page = "today" | "security";
/** Only the exact hash `#security` selects Security; any other hash reads as Today (spec decision 2). */
const pageOf = (hash: string): Page => (hash === "#security" ? "security" : "today");

export function App() {
  const [view, setView] = useState<View>({ kind: "loading" });
  const [moves, setMoves] = useState(0);
  const [signOutError, setSignOutError] = useState<string | null>(null);
  const mainRef = useRef<HTMLElement>(null);
  const [page, setPage] = useState<Page>(() => pageOf(window.location.hash));
  const phase = useSyncExternalStore(operation.subscribe, operation.phase, operation.phase);

  useEffect(() => {
    let live = true;
    // The link's token leaves the address bar before anything else, whatever the session turns out to be.
    if (onEnrolPath()) takeToken();
    void sessionState().then((kind) => {
      if (kind !== "signed_out") discardInvitation();
      if (live) setView({ kind, ...NOTHING });
    });
    return () => {
      live = false;
    };
  }, []);

  // The address decides the page, so click, Back, Forward, reload and a pasted link all agree.
  useEffect(() => {
    const read = () => { setPage(pageOf(window.location.hash)); };
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);
    return () => {
      window.removeEventListener("hashchange", read);
      window.removeEventListener("popstate", read);
    };
  }, []);

  // After the person acts, the new screen takes focus; the first load leaves focus where it is.
  useEffect(() => {
    if (moves > 0) mainRef.current?.focus();
  }, [moves]);

  const go = useCallback((kind: SessionState | "recovery", extra: Extra = {}) => {
    // The next person to sign in starts on Today, not on this one's page.
    if (kind === "signed_out" && window.location.hash === "#security") {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
      setPage("today");
    }
    setView({ kind, ...NOTHING, ...extra });
    setMoves((count) => count + 1);
  }, []);

  const expired = useCallback(() => { go("signed_out", { notice: content.errors.expired }); }, [go]);

  async function signOut() {
    setSignOutError(null);
    setSigningOut(true);
    // A factor change whose answer was lost may have rotated the token: no logout until it is known (6(e)).
    if (!(await trusted())) {
      setSigningOut(false);
      setSignOutError(content.sessionUnsure);
      return;
    }
    const { out, state } = await endSession();
    setSigningOut(false);
    if (out === "signed_out" || unauthenticated(state)) go("signed_out");
    else setSignOutError(out === "offline" ? content.errors.network : content.errors.generic);
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
          <button type="button" className="link" disabled={signingOut || phase === "sent"} onClick={() => void signOut()}>
            {signingOut ? content.signOutBusy : content.signOut}
          </button>
        ) : null}
      </header>
      {signedIn ? (
        <nav className="sidebar" aria-label={content.navLabel}>
          <ul>
            {content.nav.map((item) => (
              <li key={item.href}>
                <a href={item.href} aria-current={item.page === page ? "page" : undefined}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      <main id="main" tabIndex={-1} ref={mainRef}>
        <Screen view={view} page={page} go={go} expired={expired} signOutError={phase === "sent" ? content.finishing : signOutError} />
      </main>
    </div>
  );
}

type ScreenProps = {
  view: Shown | { kind: "loading" };
  page: Page;
  go: (kind: SessionState | "recovery", extra?: Extra) => void;
  expired: () => void;
  signOutError: string | null;
};

function Screen({ view, page, go, expired, signOutError }: ScreenProps) {
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
          {page === "security" ? (
            <Security onSignedOut={expired} />
          ) : (
            <>
              <h1>{content.pageTitle}</h1>
              <section className="card" aria-labelledby="empty-title">
                <h2 id="empty-title">{content.emptyTitle}</h2>
                <p>{content.emptyBody}</p>
              </section>
            </>
          )}
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
