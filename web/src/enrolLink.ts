// The invitation link is `/enrol#<token>`. The fragment never reaches the server; the page reads
// it once and removes it from the address bar, so the token does not stay in history, a
// bookmark or a copied URL (PR 149 review). It is kept in memory only and sent only in a POST body.

let taken: string | null | undefined;

export function onEnrolPath(): boolean {
  return window.location.pathname === "/enrol";
}

export function takeToken(): string | null {
  if (taken === undefined) {
    const token = window.location.hash.replace(/^#/, "");
    taken = token === "" ? null : token;
    if (window.location.hash !== "") {
      window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
    }
  }
  return taken;
}

/** Leaving the invitation page for the ordinary address, so the next screen is not read as an invitation. */
export function leaveEnrol(): void {
  window.history.replaceState(window.history.state, "", "/");
}

/** The visitor is not signed out, so this invitation is not theirs to use: forget it and leave the page. */
export function discardInvitation(): void {
  taken = null;
  if (onEnrolPath()) leaveEnrol();
}

/** For tests: the module remembers the token between renders on purpose. */
export function forgetToken(): void {
  taken = undefined;
}
