# PROJECT.md — the only file you fill in per project

- **Kit version used:** 1.7.3 <!-- from agents/README.md; tells you which master changes this project hasn't picked up -->

Every project fact lives here and nowhere else. The role files (`roles/`) and the
guardrail packs (`guardrails/`) never change between projects; they read this file.

`setup` fills this file with you. Every double-braced field must end up resolved: a real value,
`none` for an optional field, or `pending scaffold` for a command that doesn't exist yet. A completed
setup leaves no double braces anywhere in this file.

---

## 1. Identity

- **Project name:** SKIW Platform
- **What it is (one sentence):** A managed, in-country (AWS Malaysia) replacement of the "SKIW Assistant" stack that SK iWealth advisers use daily to prepare work against TechVision CRM, Phillip FAME and Great Eastern ePartner (plus AI chat, Life Goal Planner, returns/IRR, reviews, Case Guide and PDF form filling), keeping the "the app prepares, a person submits" invariant (spec §1, D11).
- **Target users / segment:** SK iWealth's own staff and advisers — one agency in v1 (~5 staff accounts, ~146 clients today), designed to scale to 50 and then 500 advisers by changing named components (spec §1, D18). Internal tool; clients of the agency are data subjects, not users. <!-- reviewer uses this to catch scope creep -->
- **Markets / currencies / locales:** Malaysia (PDPA as amended 2024, spec D19); currency MYR (AI ledger in `MYR`; USD only as a dated `fx_rate` input for AI cost, D23); agency timezone `Asia/Kuala_Lumpur` (spec §4.1); UI language not stated in the spec.
- **Owner (final approver, merges PRs):** Ying
- **Builder role name:** Builder <!-- the agent that writes code; follows roles/builder.md -->
- **Reviewer role name:** Reviewer <!-- the agent that reviews; follows roles/reviewer.md -->

## 2. Sources of truth

| What | Path | Wins over |
|---|---|---|
| Product spec / proposal (latest) | docs/specs/2026-10-05-skiw-platform-stack-design.md | everything except the owner |
| Spec hash at last reconcile | e314158562214a9173e7fdbd7ec6f2a8d9355dd9 <!-- git hash-object of the spec (v1.13, review Round 16 Approved, PR 19 merged 2026-10-10) when setup last filled this file; previous reconcile v1.8 67e36a52 --> | |
| Decisions log (committed) | docs/DECISIONS.md | handoff, chat history |
| Durable notes (other lasting facts) | none <!-- owner decision 2026-10-05: spec and decisions log hold lasting facts; add a notes file only when a distinct need appears --> | handoff, chat history |
| Review files | `.agent/reviews/` (reviewer writes, builder reads; local only — the final round is copied into each PR log) | |
| In-flight task state (handoff) | .agent/handoff.md | nothing — repo wins for code state |
| Extra frontend standard (on top of `guardrails/frontend.md`) | none <!-- spec v1.8 D2: Fernly layout as visual reference only, SK iWealth navy #001C30 and gold #FFB300 (skiwealth.com); tokens live in web/src/styles.css (FE-13); no separate design-system file --> | |
| Other standards | none | |
| Notes the reviewer must always load | none | |
| Extra in-flight files (checklists, cutover plans) | none | |

**Conflict rule:** repo state wins for *what the code is*. Handoff wins for *what we were doing*.
Spec wins for *what we should build*. If two of these disagree, stop and ask Ying.

## 3. Paths and layout

- **Project root:** /Users/charlie/Documents/Projects/Personal/SKIW
- **Repo root:** /Users/charlie/Documents/Projects/Personal/SKIW <!-- same as project root -->
- **Code must live under:** `app/`, `web/`, `infra/`, `extension/` (spec §9 M0), plus repo-root tooling files the scaffold creates (lockfiles, CI config, Docker Compose, `Makefile`, `.env.example`)
- **Layout:** (spec §9 M0)
  - `app/` — Django 5.2 modular monolith on Python 3.12, ASGI (D1); apps `accounts`, `tenancy`, `clients`, `planner`, `portfolio`, `reviews`, `cases`, `forms`, `connectors` (crm, fame, epartner), `bridge`, `outbox`, `ai`, `documents`, `audit`, `settings`, plus `jobs` (D5)
  - `web/` — React 19 + TypeScript (strict) + Vite SPA served same-origin by Django; typed API client generated from the `django-ninja` OpenAPI schema (D2)
  - `infra/` — AWS CDK (Python) stacks for `ap-southeast-5` (D3, D15)
  - `extension/` — Browser Bridge v1.0, Chrome MV3, store-distributed (D10)
  - `docs/` — specs, plans, runbooks, decisions log
- **Specs:** docs/specs/YYYY-MM-DD-<topic>-design.md
- **Per-PR plans:** docs/plans/YYYY-MM-DD-<topic>.md
- **Per-PR logs:** one file per merged PR, `<log folder>/YYYY-MM-DD_PR<N>_<slug>.md`, committed on
  the **log branch** — never on the default branch or a feature branch. The owner may merge the log
  branch into the default branch whenever they like; agents never do.
  - Log branch: agent-logs
  - Log folder: log
  - Review archive folder (same branch): reviews
  - Log tracking starts at: no commits yet (setup Part B, 2026-10-05; no git repository existed) <!-- earlier PRs are covered by migrated legacy logs or not at all -->
- **Runbooks:** docs/runbooks

## 4. Repository

- **Remote:** https://github.com/charliekhc/skiw-platform (private) <!-- created 2026-10-05 under the owner's personal account `charliekhc`; may move to an org later (owner decision, then update this line and docs/DECISIONS.md). The old app repo https://github.com/apiskiw/skiw-assistant is read-only reference only. -->
- **Default branch:** main <!-- local repo initialised on `main` 2026-10-05; GitHub default branch is set when the first push creates it (owner-approved baseline push) -->
- **Merge policy:** Reviewer approves → Ying merges. The builder never merges. The reviewer never merges.
- **Commit trailer:** `none`
- **PR size target:** 400 LOC (spec §9: "PR size target ≈ 400 LOC; each milestone is 1–4 PRs")

## 5. Milestones

- **Unit name:** Milestone (`M0` … `M19+`, then `Later`)
- **Milestone list lives in:** docs/specs/2026-10-05-skiw-platform-stack-design.md §9 "Milestones" (plus its "Strangler / migration plan")
- **Scaffold milestone:** M0 — Scaffold (repo layout, uv + pnpm lockfiles, ruff/mypy strict/eslint/tsc, pytest/vitest, Docker Compose, `.env.example`, import-linter contracts, CI pipeline, runbook skeleton, `jobs.enqueue_in_tx` M0c subset transaction test as `skiw_app`; tenant guard and `args_mac` are M4) <!-- after this merges, never re-scaffold, re-init git, or redo its paperwork -->

## 6. Model tiers

Role files talk in tiers, never in model names. Map them here.

| Tier | Use for | Model(s) this project uses |
|---|---|---|
| deep | spec design, architecture, security, auth, data isolation, money, milestone gates, implementation plans | Claude Opus (run as a sub-agent; exact model ID not recorded) |
| standard | normal feature work, most reviews | Claude Sonnet (exact model ID not recorded) |
| fast | mechanical edits, copy, status checks | Claude Haiku (exact model ID not recorded) |

- **Needs owner confirmation before use (cost):** none — the agent must name why the cheaper deep option isn't enough.

## 7. Commands

Leave a command out if the project doesn't have it yet; the scaffold milestone fills them in.

```bash
# install
make install       # check-node, uv sync --locked && pnpm install --frozen-lockfile
# fast checks (run before every push)
make typecheck     # mypy app infra && pnpm -C web typecheck
make lint          # ruff check/format --check, lint-imports, semgrep --config semgrep/ + --test, pnpm -C web lint
make test          # pytest (no DB, `-m 'not live'`) && vitest
make test-live     # Compose Postgres, migrate as skiw_migrator, pytest -m live as skiw_app (roles, jobs, queue grants)
make audit         # gitleaks (history) && pip-audit && pnpm audit --audit-level high; needs gitleaks installed
# database: start, migrate, run isolation tests
make dev           # web build, db up, migrate, compose up (db :5433, app, worker; ClamAV/MinIO/mail catcher with M16/M3)
make db-up         # docker compose up -d --wait db
make migrate       # migrate with MIGRATION_DATABASE_URL (skiw_migrator), then makemigrations --check, then `lintmigrations --warnings-as-errors` (django-migration-linter; required gate, same command in CI)
pending M4         # make db-test: RLS isolation, schema check, forged-tenant tests under skiw_app
# end-to-end
make e2e           # web build, compose up --wait, playwright test
```

**Secret-scan pattern** (base pattern + this project's key prefixes):
```bash
rg -n "SECRET|TOKEN|PASSWORD|PRIVATE KEY|BEGIN RSA|BEGIN OPENSSH|CRED_ENC_KEY|SUPABASE_SERVICE_KEY|ANTHROPIC_API_KEY|GAS_PROOF_URL|tenant_token_key|tenant_source_key|login_blob_key|approval_mac_key|audit_mac_key|private_key_id" .
```
<!-- Extra names from the spec: old-app secrets that must never reach the new repo (Appendix A.2, A.8, D12),
the app-held key names (§4.2, T16), and the Google service-account JSON key marker (T15, D13 keyless WIF). CI also
runs gitleaks + GitHub push protection (T16). Expect hits in docs/specs/ (the names are documented there). -->

## 8. Active guardrail packs

Tick what applies. Unticked packs are ignored by both roles.
Every rule has an ID (`TEN-09`, `FE-05`). Self-checks and findings cite IDs. Rules marked **(hard)**
are never downgraded below P1.

- [x] `guardrails/universal.md` — always on, do not untick
- [x] `guardrails/frontend.md` — any UI (semantics, layout, components, WCAG 2.2 AA)
- [x] `guardrails/tenancy-rls.md` — multi-tenant data isolation
- [x] `guardrails/money.md` — any stored or computed money
- [x] `guardrails/finalized-records.md` — issued/signed/legal documents, sequential numbering
- [x] `guardrails/auth.md` — login, sessions, roles, OAuth
- [ ] `guardrails/public-links.md` — unauthenticated share links, OTP, signatures
- [x] `guardrails/files-templates.md` — uploads, generated PDFs, user templates
- [x] `guardrails/events-jobs.md` — background jobs, queues, domain events
- [ ] `guardrails/payments.md` — payment providers, checkout, webhooks

Why:
- **universal** — always on.
- **frontend** — React SPA for every screen (D2); M19+ requires each screen to meet `frontend.md` (WCAG 2.2 AA).
- **tenancy-rls** — Postgres RLS with `agency_id` on every tenant-owned table; spec D18 says "tick `tenancy-rls.md`" and §4.2 maps TEN-01..12.
- **money** — `bigint` minor units + `currency` (MON-01/02) for AI budget ledger, lead cost, premiums, sums assured, goal targets, holdings; one rounding module `ai.cost.to_minor` (MON-04); one currency per ledger (MON-05); FX frozen on reservations (MON-06-like).
- **finalized-records** — approved outbox payloads are frozen with `payload_sha256` and never edited (REC-01/02: supersede, not edit); filed documents and case-step evidence are finalised only at `verified` (T13); append-only evidence tables; client `display_code` pattern (Q28) is a numbering scheme whose changes never rename old folders (REC-09). See §9 for how REC-06..12 apply.
- **auth** — Django auth, Argon2id, passkeys/TOTP, DB sessions, step-up, role matrix §6, persistent rate limits (D6, D7, Flow 5.1).
- **files-templates** — uploads (magic bytes, ≤ 20 MB, `<agency_id>/<uuid>` keys, presigned GET ≤ 5 min, D14) and PDF form filling from issuer templates (`form_template`; spec says FILE-05/06 apply).
- **events-jobs** — Procrastinate Postgres queue with transactional enqueue `jobs.enqueue_in_tx` (EVT-01), dead-letter + admin retry (EVT-05), worker-owned schedules (EVT-06) (D5).
- **public-links (unticked)** — no unauthenticated share links, client-facing OTP or e-signature exist in v1. Presigned S3 downloads are short-lived authenticated-session downloads covered by FILE-04; the OTP the spec mentions is FAME's own login done by the adviser (Flow 5.3); bridge request signatures are device auth (D10, covered by auth + §9); `wa.me` links are outbound drafts.
- **payments (unticked)** — no payment provider, checkout or payment webhook in scope; fees/commission are owner config only (§2) and commission reconciliation is "Later" (§9); the only webhooks mentioned are a future WhatsApp BSP integration (D21, separate spec).

**Pack parameters** (packs refer to these by name):
- Tenant key column: `agency_id` (`uuid not null`; spec §4 "Tenant key")
- Tenant session setting: `app.tenant_token` — a transaction-local HMAC token, read **only** by `guard.current_agency()` (SECURITY DEFINER, owned by NOLOGIN `skiw_tenant_guard`), which every policy calls; a plain `app.agency_id` setting is never trusted (spec D18, §4.2 "Tenant binding"; project TEN-06 mapping in §9)
- Runtime DB role: `skiw_app` · Migration DB role: `skiw_migrator` (also `skiw_readonly` for reporting/break-glass; NOLOGIN function owners `skiw_tenant_guard`, `skiw_auth_lookup` — spec D4)
- Scoped transaction helper: `with_agency(agency_id)` (sync, inside `transaction.atomic`); async twin `bridge.db.async_with_agency(agency_id)` for the bridge long-poll only (spec §4.2, D26)
- Admin/bypass helper (if any): `with_admin_operation` <!-- owner decision 2026-10-05: contract named now, implemented in M4; each call names one permitted operation and writes its audit event (TEN-12). Original note: spec §4.1/§4.2 (TEN-12 row) defines its job — cross-agency or global writes: owner admin, waffle flags, `agency` updates, one audit row per call — but uses the kit placeholder name, not a concrete function name -->
- Server action wrapper: `authorized_action` <!-- owner decision 2026-10-05: contract named now, implemented in M3/M4 with AUTH-01's required check order. Original note: spec §4.3 and §6 refer to "the AUTH-01 wrapper" / "the action wrapper per §6 (AUTH-01/03)" without a concrete name -->
- Where configurable business values live: the per-agency `setting` table (typed, validated, versioned; history in `setting_change`; owner step-up writes audited) and dated `fx_rate` rows; feature flags in `django-waffle`; infra values in CDK context; secrets only in AWS Secrets Manager (spec D22, D23, §8.1)

## 9. Project-specific hard constraints

Things unique to this product. Generic rules belong in a guardrail pack, not here.

**Out of scope (reviewer rejects scope creep):**
- Any automated submission to FAME, ePartner or a fund house; no FAME write adapter will ever exist (spec §2, D11).
- Captcha solving or OCR of captchas, VPNs, rotating/residential IPs or any technique that evades FAME's firewall or any portal's controls; no unattended FAME runner unless Phillip confirms in writing (spec §2, D10, T12, B.11, Q8).
- The Doc2 Marketing suite (Campaigns, Funnels & sites, Automation builder, Media, Reviews widgets, WhatsApp/Conversations inbox); WhatsApp is draft-only `wa.me` with a person pressing send (spec §2, D21, T21).
- Kubernetes, microservices, multi-region active-active (spec §2, B.4).
- New business rules: fees, targets (FYP, MDRT, SES, Supremacy), CPD and commission logic come only from owner-supplied config (spec §2, §8.1).
- A mobile app (responsive web only) and a CRM replacement (TechVision stays system of record) (spec §2, Q4).
- "Later" items, each needing its own spec: Google Calendar writes, WhatsApp via BSP, marketing tool integration, create-client in CRM, commission reconciliation, lead cost-per-client (spec §9 "Later", §5.10).

**Stubs only (interface, no implementation yet):**
- `external_action(op=create_client)` — draft only, blocked until a CRM create-client capability exists (Q5); UI says "create in CRM manually, then link" (spec Flow 5.6, §5.10).
- Outbox executor/sweeper/reconciler run only against a fake CRM test double in M9; no real connector writer exists until M13 (spec §9 M9).
- AI (M11): only offline parts (ledger, pseudonymiser, tool layer, red-team set) against a stub model until gate G-AI opens (spec D12, M11).
- Drive writer (M16): built and tested against the Drive fake and staging only until gate G-DRIVE opens (spec D25, M16).
- Fallback adapters kept behind the same interfaces, not built: Anthropic API direct (D12), CRM via the bridge (B.10), `job_outbox` relay only if the M0 Procrastinate test fails (D5).

**Architecture rules:**
- Django modular monolith; app boundaries enforced by `import-linter` contracts in CI (spec D1, UNI-04).
- Outbox invariant: every write to a third-party system of record is an `external_action` row (§4.3 state machine, DB CHECKs + `external_action_guard` trigger); only `outbox.executor` imports connector write functions; only `outbox.approval` mints approval artifacts and writes approval transitions; only `outbox.executor`/`outbox.reconciler` write execution transitions; each CRM write is read back field by field; `outcome_unknown` is never blindly retried (spec D11, §4.3).
- Drive writes follow D25 only: only `documents.drive_writer` imports Drive mutation calls and it exposes exactly create folder / upload file / move file from Scans inbox; every op is a `drive_operation` row; dependent local state is written only at `verified` (spec D25).
- Every external mutation needs a row in spec §5.10 (a spec change) before code; a CI contract test lists the allowed importers (spec §5.10).
- All job enqueueing goes through `jobs.enqueue_in_tx` (derives the agency itself; no `agency_id` parameter; ids checked under RLS; `args_mac` — the full guard lands in M4; M0c ships only the subset and probe-task boundary in spec D5 "Staging"); direct `.defer()`/`.defer_async()` is banned by Semgrep; job args are ids only, never PII (spec D5, §4.2 item 6). From spec v1.9 (owner decisions 2026-10-10, `docs/DECISIONS.md`): the worker runs only through `manage.py runworker` on the `DjangoConnector` (no swap to `PsycopgConnector`), so a sync handler enqueues in its own `with_agency()` transaction; periodic per-agency fan-out uses one `with_agency(a)` transaction per deployment agency and an insert-only `job_fanout` marker (kept for the tick lifetime; v1 deletes none); periodic system tasks are the only unsigned job kind (exact `{"timestamp": int}` args, cron-aligned, inside a replay window) and signed or provenance-checked periodic parents are required before a second agency; no automatic re-queue of a suspected stalled attempt (read-only report in M4, audited operator release after confirmed termination in M5; the library's normal owned retry stays); every Procrastinate or asgiref upgrade PR must run the M4 worker tests (UNI-13). Implementation is M4/M5. EVT-02 is n/a unless the M0 `job_outbox` fallback is used. EVT-07..11 (plugins) are n/a: the browser extension is a client, not a plugin.
- Tenancy (project TEN-06 mapping, spec §4.2): policies are keyed on `(SELECT guard.current_agency())`, the only reader of `current_setting('app.tenant_token', true)`; any predicate reading `current_setting(…)` directly fails the schema check. Tokens are minted only in `with_agency()` / `async_with_agency()`; every tenant-to-tenant reference is a composite FK `(agency_id, <col>)`; the global-table list in spec §4.1 is closed; tenant sources (session, `bridge_session`, job args, login blobs) are MAC-verified (spec D18, §4.1–4.2).
- **TEN-03 rule mapping — Procrastinate queue tables (owner decision 2026-10-07, option A):** `procrastinate_jobs`, `procrastinate_events`, `procrastinate_periodic_defers` and `procrastinate_workers` are mutable operational queue state, not append-only evidence, so TEN-03 does not apply to them; `skiw_app` holds only the per-object grants listed in spec §4.1 "Procrastinate queue grants" (never TRUNCATE; no DELETE on `procrastinate_jobs`; DELETE only on `procrastinate_periodic_defers` and `procrastinate_workers`, which Procrastinate's periodic deferrer and worker register/prune paths need). `audit_event` and the other evidence tables in spec §4.2's TEN-03 row stay append-only under TEN-03. Known limit: on the shared queue a compromised `skiw_app` connection can disrupt another agency's jobs (not forge them) — spec §4.2 item (b), Q32.
- TEN-10 allow-list of modules touching the DB outside the helper: `accounts.session`, `accounts.auth`, `bridge.auth`, `jobs`, migrations; DB-side only `guard.*` functions read key tables (spec §4.2).
- Intra-agency visibility (own book / team / agency) is the lint-enforced app-level `scoped()` module, not RLS, in v1 (spec D18, §6).
- Bridge long-poll is the only async view: every `MIDDLEWARE` entry async-capable, no ORM or `transaction.atomic` in it, no transaction or pooled connection held while waiting (spec D26).
- The bridge is GET-only from a static, code-shipped job-type allow-list on both sides; the server never sends a URL; FAME/ePartner tokens never leave the browser (spec D10).
- No stored third-party passwords; only an envelope-encrypted CRM cookie jar (spec D8, D9).
- AI tools are read-only except `draft_crm_task`, which only creates a `draft` `external_action`; prompts pseudonymised; the AI can never approve (spec D12, Flow 5.8, §4.3).
- Audit events are appended only by the `audit` module through the `audit_head` append protocol with `event_mac`; `auth_stepup` only by `accounts.auth`; the daily verifier schedule changes only by a reviewed spec revision (spec §4.1, T19).
- Schema changes only through Django migrations run by the `migrate` task as `skiw_migrator`; startup fails closed on unapplied migrations (spec D16).
- Primary data, backups, object storage and logs stay in AWS `ap-southeast-5`; each cross-border flow needs a TIA or s129 basis (spec D3, D19).
- The old app repo `https://github.com/apiskiw/skiw-assistant` is read-only reference: never cloned, no code copied unless the owner asks; single files read with `gh api` only when a spec or review needs a fact (docs/DECISIONS.md 2026-10-05).
- finalized-records mapping: REC-01/02 apply to approved `external_action` payloads (frozen + `payload_sha256`; changes supersede) and to `verified` filings; REC-06..10 apply to client `display_code` allocation once Q28 fixes the pattern (allocator to be specified then); REC-11/12 for filled issuer forms are settled (owner ruling 2026-10-05, `docs/DECISIONS.md`): saved form data may persist; a draft PDF preview is watermarked and temporary; the final PDF is stored when issued or signed (a filled form is the document a person signs, spec §4.1 `form_instance`).

**Locked switches (must stay in this state until the condition is met):**
| Switch | Must stay | Until | Evidence lives in |
|---|---|---|---|
| G-AI: `ai.mode`, `ai.allowed_inference_profiles`, Bedrock adapter | `off` / empty list / adapter fails closed; no non-stub Bedrock call for any user | the owner's Q13 decision (with TIA or s129 basis) is recorded, and only the profile ids it lists are allowed | spec D12, §8.1, M11; Q13 entry in docs/DECISIONS.md |
| G-DRIVE: waffle flag `documents.drive_writes`; Drive writer with real data | off; writer refuses every mutation | a Q24 entry exists in the decisions log and `drive.write_policy` matches it | spec D25, §8.1, M16; Q24 entry in docs/DECISIONS.md |
| `drive.write_policy` | `stepup_required` | the owner records Q24 "yes", then sets `person_triggered` by an owner step-up action | spec D25, §8.1; docs/DECISIONS.md |
| Flag `outbox.executor.crm` | off (no real CRM writer) | the M13 tests pass | spec §9 M9, M13 |
| Bedrock model invocation logging | disabled (no `PutModelInvocationLoggingConfiguration` in CDK or by hand) | never, without a reviewed spec revision (UNI-09) | spec D17, D12, M11 (CDK snapshot + release check) |
| FAME / ePartner write code | none exists | never (spec non-goal) | spec §2, D11, M15 contract test |
| Bedrock extended thinking / prompt caching | not enabled (no `thinking`, no `cachePoint`) | a reviewed spec revision | spec Flow 5.8, M11 |
| Sentry (error tracker) | not adopted | a TIA is done; then `send_default_pii=False` + scrubbing | spec D17, D19 |
| Second agency onboarding | not allowed | the owner reviews the T1 "not contained" list (Q2) | spec D18, §4.2, Q2 |
| Per-module cutover flags (M17) | off for all users | flag on for 1 pilot user for 3 days with zero P0/P1 incidents | spec §9 M17 |
| Old app repo `apiskiw/skiw-assistant` | read-only reference | the owner says otherwise | docs/DECISIONS.md 2026-10-05 |

## 10. Never commit

`.agent/` (handoff, review files, worktrees), `.env*` (except `.env.example`), agent tool folders (none; exclude specific local state or secrets individually if they appear under `.claude/` or `.codex/`), and:
- Google service-account JSON key files (Drive access is keyless via WIF — spec D13, T15).
- Any real client or personal data: unanonymised CRM/FAME/ePartner pages or fixtures, Supabase exports or dumps, IC images, production snapshots (GitHub holds code only — spec D19; fixtures are anonymised — T4, §8.3).
- Old-app secrets or their values (`CRED_ENC_KEY`, `SUPABASE_SERVICE_KEY`, `ANTHROPIC_API_KEY`, `GAS_PROOF_URL` — spec Appendix A).

## 11. Extra approval gates

On top of the gates in `roles/builder.md`:
- Opening gate G-AI (any non-stub Bedrock call, or any other LLM use such as the scan classifier or IC OCR) needs the owner's recorded Q13 decision (spec D12, Q12, Q13).
- Enabling Drive writes on real data (gate G-DRIVE) needs the owner's recorded Q24 decision (spec D25, M16).
- Any production deploy needs the manual approval in the GitHub production environment after staging smoke tests (spec D15, §8.3).
- Any new external mutation, new cross-border data flow (TIA / s129, D19) or new external service (UNI-11) needs a spec change approved by review and the owner first.
- Turning on a module cutover flag for all users, or any M18 decommission step (deleting stored passwords, revoking `CRED_ENC_KEY`, deleting Supabase, removing Render or Apps Script), needs the owner's yes (spec §9 M17–M18, D20).
