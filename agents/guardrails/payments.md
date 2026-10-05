# Guardrails — payments

**Stack:** any.

- **PAY-01** Every write to payment/financial tables goes through audited, server-side code.
- **PAY-02 (hard)** Client cart/checkout state is advisory. At payment time apply MON-07 (server recomputes every amount), and independently re-check stock and voucher validity.
- **PAY-03** Payment-provider integration sits behind an interface, so a second provider is an adapter, not a rewrite.
- **PAY-04** Webhooks: signature verified, idempotent by provider event id, and replay-safe.
- **PAY-05** Stock, voucher and expiry changes are race-safe (row locks or atomic conditional updates), with tests.
- **PAY-06** Checkout-enabling switches follow the locked-switch table in `PROJECT.md` §9. Never flip one without
  the evidence named there.
