import type { CDPSession, Page } from "@playwright/test";

/**
 * A virtual platform authenticator in Chromium's own WebAuthn stack (Chrome DevTools Protocol,
 * `WebAuthn` domain): the page's `navigator.credentials` is the browser's, only the device is
 * simulated. It verifies the user and answers presence at once. Chromium only.
 */
export class Authenticator {
  private constructor(
    private readonly cdp: CDPSession,
    private id: string,
  ) {}

  static async attach(page: Page): Promise<Authenticator> {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send("WebAuthn.enable", { enableUI: false });
    return new Authenticator(cdp, await Authenticator.add(cdp));
  }

  private static async add(cdp: CDPSession): Promise<string> {
    const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", {
      options: {
        protocol: "ctap2",
        transport: "internal",
        hasResidentKey: true,
        hasUserVerification: true,
        isUserVerified: true,
        automaticPresenceSimulation: true,
      },
    });
    return authenticatorId;
  }

  /** The credentials this device holds (the server's list is separate: removal there leaves them). */
  async held(): Promise<{ rpId?: string; isResidentCredential: boolean }[]> {
    return (await this.cdp.send("WebAuthn.getCredentials", { authenticatorId: this.id })).credentials;
  }

  /** Swaps this device for a new, empty one, as a person adding a second device would. */
  async replace(): Promise<void> {
    await this.cdp.send("WebAuthn.removeVirtualAuthenticator", { authenticatorId: this.id });
    this.id = await Authenticator.add(this.cdp);
  }
}
