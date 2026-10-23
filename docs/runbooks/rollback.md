# Runbook — rollback

iCore VPS, spec §8.4 H3 steps 7 and 10.

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
Not automated. When a rollback is refused for a contract migration, the target code may not run on
the current schema: restore the pre-migration dump instead ([restore.md](restore.md)).

## When a rollback is not enough
See [restore.md](restore.md).
