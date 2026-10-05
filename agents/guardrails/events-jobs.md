# Guardrails — events and background jobs

**Stack:** any database with transactions and a job queue.
If this project lacks that mechanism, don't silently waive these rules. Before ticking this pack, record
in `PROJECT.md` §9 the alternative mechanism and how each affected rule's outcome is tested; otherwise
leave the pack unticked and write replacement rules in §9.

- **EVT-01** Domain events, and any jobs they trigger, are recorded **atomically with the change they describe**: an
  outbox row, or a queue job enqueued inside the same database transaction. If the change rolls back, no event or job remains.
- **EVT-02** If events pass through a relay, it runs as a singleton and is idempotent by event id. N/A when jobs are
  enqueued transactionally; say so in the self-check.
- **EVT-03** Handlers ignore unknown fields (forward-compatible).
- **EVT-04** Core handlers run before plugin/extension handlers. Plugin failures never block core.
- **EVT-05** Retries with backoff, a dead-letter queue, and a way to retry from the UI or an admin command.
- **EVT-06** Schedules are owned by the worker. No HTTP cron endpoints.

## Plugins / extensions (if the project has them)
- **EVT-07** Receive only a context object. Never a DB handle.
- **EVT-08** No plugin-to-plugin calls; communicate through events.
- **EVT-09** No plugin code inside request handlers.
- **EVT-10** Compiled in with a static registry. No runtime loading.
- **EVT-11** Availability and entitlement checked when enabled **and** on every job.
- **EVT-12** Plugin settings and stored credentials encrypted (AES-256-GCM, versioned key).
