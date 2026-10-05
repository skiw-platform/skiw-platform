# Guardrails — auth and authorization

**Stack:** any server-side web app.

Parameter: `ACTION_WRAPPER` (from `PROJECT.md` §8). In a project with no tenant boundary, the "tenant"
step of AUTH-01 is n-a; say so in the self-check.

## Every mutating server entry point
- **AUTH-01 (hard)** Goes through `ACTION_WRAPPER`, in this order: session → tenant → role/permission → input schema
  validation → idempotency → handler.
- **AUTH-02** Middleware is never the only gate. It can redirect; the server action must still authorize.
- **AUTH-03** Permissions match the permission matrix in the spec exactly.

## Credentials and sessions
- **AUTH-04** Passwords hashed with Argon2id, or another memory-hard scheme recorded in the decisions log. Never plaintext or reversible.
- **AUTH-05** Uniform responses for login, reset and signup (don't reveal whether an account exists).
- **AUTH-06** Rate limits are persistent (DB or shared store), not in-memory per instance.
- **AUTH-07** Sessions revoked on password, 2FA or email change.
- **AUTH-08** Reset and invite links: single use, short expiry (value in spec).
- **AUTH-09** Step-up auth (recent TOTP) on the sensitive actions the spec lists.

## Providers and edge
- **AUTH-10** OAuth provider list: auth config, sign-in UI, env example and runbook change together.
- **AUTH-11** Edge middleware must not depend on the database in unsafe ways.
- **AUTH-12** Role changes propagate to both server code and middleware. If JWT sessions are used, stale-role
  behavior is documented.
- **AUTH-13** Sign-out clears both server session and client navigation state.
