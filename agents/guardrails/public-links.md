# Guardrails — public share links, OTP, e-signatures

**Stack:** any.

## Share links
- **LINK-01 (hard)** Token: 32 random bytes. Only its SHA-256 hash is stored.
- **LINK-02** Has expiry and revoke. Bound to one document **version**.
- **LINK-03** Rate limited per link and per IP.
- **LINK-04** Response headers: `noindex`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`.
- **LINK-05** Tokens scrubbed from logs and error trackers.
- **LINK-06** Nothing from other documents or tenants is reachable through a link.

## OTP and signatures
- **LINK-07** OTP: 6 digits, stored HMAC-hashed, 10-minute expiry, 5 attempts (or the spec's values).
- **LINK-08** Signing flow: OTP → typed name → signature record + certificate page with every field the spec lists.
- **LINK-09** The approval step is one atomic transaction (freeze + signature + follow-on records + events) and is
  idempotent on retry or double-click.
