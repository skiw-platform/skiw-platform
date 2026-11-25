# Runbook — rollback

Hostinger VPS, spec §8.4 H3 steps 7 and 10.

## Automatic switch-back (M1g-1)
A deploy whose `/readyz` or worker check fails switches `web` and `worker` back to the digest that
was running, alerts and exits 1 (see [deploy.md](deploy.md), step 6). Migrations are never reversed:
every migration is additive (UNI-15), so the previous digest runs on the new schema.

## Application rollback (previous image)
With the owner's production key, on the owner's machine (spec H3 step 10):
```
ssh -i <owner production key> -p <SKIW_SSH_PORT> skiw-deploy@<production host> rollback <digest>
```
Pick `<digest>` from `sudo cat /var/lib/skiw/accepted-digests` on production. Refused (exit 2,
the serving digest unchanged) with the staging key, for a digest that is not in that record
(unknown, or only ever run on staging), when the record holds a malformed or cut line, when the
pulled image's commit label is not the commit the record holds for it, and when
`/var/lib/skiw/applied-contracts` (the contract migrations of every image whose `migrate` was
started on this host, written before `migrate` runs) names a migration the target image does not
ship (a plain `deploy` of such an older digest is refused the same way). There is no staging check (staging may already run something newer) and no `migrate`; the
target is pulled by digest, then steps 5–7 of [deploy.md](deploy.md) apply, including the automatic
switch-back. A rollback adds no accepted-digest line; the journal and deploy log record it.

## Migration rollback (reversible migrations only, UNI-15)
Not automated. The supported rollback is the application image (above): it never runs `migrate`
and the previous digest runs on the newer schema. Reversing migrations (`manage.py migrate <app>
<earlier migration>` as `skiw_migrator`) is a manual schema change outside that path. When a
rollback is refused for a contract migration, the target code may not run on the current schema:
restore the pre-migration dump instead ([restore.md](restore.md)).

**Reversing accounts past 0025 is refused while role or org change events exist.** Those
`security_event` rows are the append-only audit record (TEN-03). The reverses of accounts 0025, 0024
and 0022 each stop with SQLSTATE 55000 and
`reverse refused: security_event holds role or org change events`, before the shape trigger or
an RLS policy is dropped. Django commits each migration on its own, so the reverses that ran
before stay committed. From the head this means 0030 to 0026 (the `skiw_app` write grants on the
roles tables and the Decision 32 triggers are gone, so roles changes fail), with accounts at 0025
and `security_event` still isolated.
- **Never delete change events to get past it.** The recovery is to roll forward: `deploy <digest>`
  of the image that was serving; its `migrate` re-applies 0026 to 0030 and every change event is
  kept.
- **Restore is exceptional, and loses data.** A pre-migration dump predates every role, permission,
  assignment or org change made since, and restoring it discards those changes and their audit
  events together. Do it only if roll-forward is impossible, and only with the owner's decision:
  the owner names the exact dump, lists the changes and events made after it (compare
  `security_event` change rows against the dump's) and records them as lost or re-enters them, then
  follows [restore.md](restore.md). Do not clear the incident until that account is written down.
- **Verify before serving**: `check_tenancy_schema` passes (deploy step 4 runs it), and as
  `skiw_migrator` or `postgres` (`psql` as in restore.md step 4):
  ```sql
  SELECT relrowsecurity, relforcerowsecurity FROM pg_class
   WHERE oid = 'public.security_event'::regclass;              -- t | t
  SELECT polname FROM pg_policy WHERE polrelid = 'public.security_event'::regclass
   ORDER BY 1;          -- security_event_ins, security_event_sel, security_event_tenant
  SELECT tgenabled FROM pg_trigger WHERE tgrelid = 'public.security_event'::regclass
   AND tgname = 'security_event_shape';                        -- O
  SELECT max(name) FROM django_migrations WHERE app = 'accounts';  -- the image's head
  ```

## When a rollback is not enough
See [restore.md](restore.md).
