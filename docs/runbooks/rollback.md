# Runbook — rollback

iCore VPS, spec §8.4 H3 steps 7 and 10.

## Automatic switch-back (M1g-1)
A deploy whose `/readyz` or worker check fails switches `web` and `worker` back to the digest that
was running, alerts and exits 1 (see [deploy.md](deploy.md), step 6). Migrations are never reversed:
every migration is additive (UNI-15), so the previous digest runs on the new schema.

## Application rollback (previous image)
`skiw-deploy --rollback <digest>` (owner key only, digest from the accepted-digest record, refused
across a contract migration) arrives in M1g-2. Until then `rollback <digest>` through the forced
command is refused (exit 2); deploy the previous digest with `deploy <digest>` instead.

## Migration rollback (reversible migrations only, UNI-15)
Not automated. A contract migration that the target digest does not know means a restore from the
pre-migration dump (M1g-2).

## When a rollback is not enough
See [restore.md](restore.md).
