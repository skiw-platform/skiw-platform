import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type MouseEvent } from "react";

import { endSession, sessionState, unauthenticated, type SessionState } from "./api";
import { content } from "./content";
import { discardInvitation, leaveEnrol, onEnrolPath, takeToken } from "./enrolLink";
import { leave, operation, passkeySupported, stay, trusted } from "./passkey";
import { EnrolMissing, EnrolPassword, EnrolSetup, type Setup } from "./screens/Enrol";
import { Offer } from "./screens/Offer";
import { Recovery } from "./screens/Recovery";
import { SecondFactor } from "./screens/SecondFactor";
import { Security } from "./screens/Security";
import { SignIn } from "./screens/SignIn";

/** `offer`: the passkey step after the recovery codes (spec M3g-2a-2 decision 10). */
type Step = SessionState | "recovery" | "offer";
type Shown = {
  kind: Step;
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
  const pageRef = useRef(page);
  /** The step-up dialog is open: the page around it is inert (spec M3g-2a-2 decision 6(d)). */
  const [modal, setModal] = useState(false);
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

  /** A notice on Today (the offer's "Passkey added") leaves with the page it was said on; a hash
   * that keeps the page (the skip link's `#main`) keeps it. */
  const turn = useCallback((next: Page) => {
    if (next === pageRef.current) return;
    pageRef.current = next;
    setPage(next);
    setView((shown) => (shown.kind === "signed_in" && shown.notice !== null ? { ...shown, notice: null } : shown));
  }, []);

  // The address decides the page, so click, Back, Forward, reload and a pasted link all agree.
  useEffect(() => {
    const read = () => { turn(pageOf(window.location.hash)); };
    window.addEventListener("hashchange", read);
    window.addEventListener("popstate", read);
    return () => {
      window.removeEventListener("hashchange", read);
      window.removeEventListener("popstate", read);
    };
  }, [turn]);

  // After the person acts, the new screen takes focus; the first load leaves focus where it is.
  useEffect(() => {
    if (moves > 0) mainRef.current?.focus();
  }, [moves]);

  const go = useCallback((kind: Step, extra: Extra = {}) => {
    // The next person to sign in starts on Today, not on this one's page.
    if (kind === "signed_out" && window.location.hash === "#security") {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
      pageRef.current = "today";
      setPage("today");
    }
    setView({ kind, ...NOTHING, ...extra });
    setMoves((count) => count + 1);
  }, []);

  const expired = useCallback(() => { go("signed_out", { notice: content.errors.expired }); }, [go]);

  // A plain click keeps this document, and with it a factor change still in flight; the href stays
  // real, so a new tab, a modified click, Back and Forward behave as for any link.
  function follow(event: MouseEvent<HTMLAnchorElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    window.history.pushState(null, "", event.currentTarget.href);
    turn(pageOf(window.location.hash));
  }

  async function signOut() {
    setSignOutError(null);
    setSigningOut(true);
    leave();
    try {
      // A factor change whose answer was lost may have rotated the token: no logout until it is known (6(e)).
      if (!(await trusted())) {
        setSignOutError(content.sessionUnsure);
        return;
      }
      const { out, state } = await endSession();
      if (out === "signed_out" || unauthenticated(state)) go("signed_out");
      else setSignOutError(out === "offline" ? content.errors.network : content.errors.generic);
    } finally {
      setSigningOut(false);
      stay();
    }
  }

  const [signingOut, setSigningOut] = useState(false);
  const signedIn = view.kind === "signed_in";
  return (
    <div className={signedIn ? "app" : "app app--solo"}>
      <a className="skip-link" href="#main" inert={modal}>
        {content.skipLink}
      </a>
      <header className="topbar" inert={modal}>
        <p className="brand">{content.product}</p>
        {signedIn ? (
          <button type="button" className="link" disabled={signingOut || phase === "sent"} onClick={() => void signOut()}>
            {signingOut ? content.signOutBusy : content.signOut}
          </button>
        ) : null}
      </header>
      {signedIn ? (
        <nav className="sidebar" aria-label={content.navLabel} inert={modal}>
          <ul>
            {content.nav.map((item) => (
              <li key={item.href}>
                <a href={item.href} onClick={follow} aria-current={item.page === page ? "page" : undefined}>
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      ) : null}
      <main id="main" tabIndex={-1} ref={mainRef}>
        <Screen view={view} page={page} go={go} expired={expired} onModal={setModal} />
        {/* Mounted empty on the offer, so the notice it hands to Today is a change a screen reader announces. */}
        {signedIn || view.kind === "offer" ? (
          <div id="today-status" aria-live="polite" className="message">
            {signedIn ? (phase === "sent" ? content.finishing : signOutError) ?? view.notice : null}
          </div>
        ) : null}
      </main>
    </div>
  );
}

type ScreenProps = {
  view: Shown | { kind: "loading" };
  page: Page;
  go: (kind: Step, extra?: Extra) => void;
  expired: () => void;
  onModal: (open: boolean) => void;
};

function Screen({ view, page, go, expired, onModal }: ScreenProps) {
  switch (view.kind) {
    case "loading":
      return (
        <>
          <h1>{content.loading.title}</h1>
          <p role="status">{content.loading.status}</p>
        </>
      );
    case "signed_in":
      return page === "security" ? (
        <Security onSignedOut={expired} onModal={onModal} />
      ) : (
        <>
          <h1>{content.pageTitle}</h1>
          <section className="card" aria-labelledby="empty-title">
            <h2 id="empty-title">{content.emptyTitle}</h2>
            <p>{content.emptyBody}</p>
          </section>
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
            go(passkeySupported() ? "offer" : "signed_in");
          }}
        />
      );
    case "offer":
      return <Offer onDone={(notice) => { go("signed_in", notice === undefined ? {} : { notice }); }} onSignedOut={expired} onModal={onModal} />;
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
