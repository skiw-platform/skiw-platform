# Guardrails — multi-tenant data isolation

**Stack:** PostgreSQL row-level security. A project on another database ticks this pack only if it maps
each rule to its own mechanism in `PROJECT.md` §9; otherwise it writes equivalent isolation rules there.

Parameters (from `PROJECT.md` §8): `TENANT_KEY`, `TENANT_SETTING`, `DB_APP_ROLE`, `DB_MIGRATOR_ROLE`,
`TENANT_TX_HELPER`, `ADMIN_TX_HELPER`.

## Database roles
- **TEN-01** `DB_MIGRATOR_ROLE` owns the schema and runs migrations.
- **TEN-02 (hard)** `DB_APP_ROLE` is the only role the running app uses. It has **no** superuser and **no** BYPASSRLS.
- **TEN-03** Append-only tables (audit log, event or job records): `DB_APP_ROLE` may INSERT, and SELECT where the app
  must read them. It has no UPDATE, DELETE or TRUNCATE.

## Every tenant table
- **TEN-04** Has a non-null `TENANT_KEY` column.
- **TEN-05** Row-level security `ENABLE`d **and** `FORCE`d.
- **TEN-06** Policies have both `USING` and `WITH CHECK`, keyed on `current_setting('TENANT_SETTING', true)`.
- **TEN-07** Default deny: a RESTRICTIVE tenant policy on every table, plus targeted PERMISSIVE policies.
  No blanket permissive policy.
- **TEN-08** Isolation tests exist for read **and** write, including through any plugin/extension path.
  A new tenant table without its isolation test is a finding.

## Access
- **TEN-09 (hard)** Every request and background job runs inside `TENANT_TX_HELPER`, which sets the tenant
  transaction-locally: `SET LOCAL`, or `set_config(name, value, true)` (the same thing in function form).
  Plain `SET` and `set_config(…, false)` are banned (they leak across pooled connections).
- **TEN-10** No direct DB access outside the helper, except a small, lint-enforced allow-list of system modules.
- **TEN-11 (hard)** The active tenant comes from the server session. Never from client input (body, query, header, cookie
  the client controls).
- **TEN-12** Any bypass (`ADMIN_TX_HELPER`) is explicit, scoped to one operation, and writes an audit row.
