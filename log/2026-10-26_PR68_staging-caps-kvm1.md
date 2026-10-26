# PR 68 — feat(infra): staging memory caps for KVM 1 and a RAM-rule test

- **Merged:** 2026-10-26T14:39:00Z (GitHub) · **Merge commit:** `4ea58f545e435c48bd4013076034ccdb91360d0a` · **Branch:** `feat/m1-staging-caps` (final head `60fb2489695c0b27b72aa83a214d92514713c120`)
- **Gate breaches:** none (5 files, +79 / −5; about 34 lines of code and test, 45 of docs)
- **Approval receipt:** `reviews/PR-68.receipt` on `agent-logs`, written 2026-10-26T10:03:39Z (before the merge, by 4 h 35 min); names head `60fb248…`, review `reviews/PR-68.md` (hash `20363b08…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 68` → MERGED, merge commit `4ea58f5`, final head equals the reviewed head; `git merge-base --is-ancestor 4ea58f5 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved with conditions (Round 1)
- **Spec:** main spec v1.20, hash `92841ba555e9e857ac70e86a5b043cf9729ed371`; amendment `docs/specs/2026-10-25-hostinger-vps-vendor.md` v1.2 §2 (conditional exception) and decision 3 · **Milestone:** M1 (before the purchase and M1k)

## What changed
Staging caps for a Hostinger KVM 1 (4 GB): `SKIW_MEM_WEB` 640m → 512m and `SKIW_MEM_DB` 768m → 640m in `infra/host/env/staging.env`; the sum without `migrate` goes from 3328 to 3072 MiB (plan RAM 4096 − 1024); ClamAV stays 1280m. A host test checks the RAM rule for production (8192) and staging (4096) and the ClamAV floor, with a strict `m`/`g` parser. DECISIONS "2026-10-26 — Q43 answered: production KVM 2, staging KVM 1 (monthly)". Plan G3 row. `docs/runbooks/host-rebuild.md` section "Staging on a monthly term (rebuild checklist)".

## Review rounds
- R1: Approved with conditions. One P2 (deferred), one P3 (owner).

## Deferred conditions
- **P2: the "staging lapses" runbook steps leave live things behind** (staging DNS, `ghcr_read_token`, `alert_credential`, `STAGING_DEPLOY_KEY`, the UptimeRobot monitor). The fix is a docs PR, **due by 2026-11-20 and in any case before staging is first allowed to lapse.** Required: before the term ends, turn the staging deploy off; delete or point away the staging DNS names; revoke the staging `ghcr_read_token` (rotate production's if it is the same token); revoke the staging bot token (BotFather `/revoke`); delete the `STAGING_DEPLOY_KEY` secret; pause the UptimeRobot monitor; destroy the VPS in the Hostinger panel and record the date. In "To bring it back": point the DNS names at the new IPv4 before `apply`, and un-pause the monitor.
- P3 (owner, non-blocking): read the DECISIONS entry with the owner's quoted words. The owner merged.

## Decisions worth keeping
- Owner (2026-10-26): production KVM 2, staging KVM 1 on a monthly term; Q44 (term) open for production. Rejected: staging on a local Mac VM with an open SSH port, BitVPS, free tiers, one shared server.
- The caps are ceilings, not use; the real need is proven by a load check and a measured deploy peak in M1k [A].

## Follow-ups
- **Docs PR for the deferred P2, by 2026-11-20.** Until it merges, staging must not lapse.
- Owner: Q44 production term; buy the VPSs (Malaysian location, Ubuntu 24.04, automatic backups off if allowed); G-VENDOR questions; Telegram bot per host and UptimeRobot monitors.
- Carry the spec Q43 and Q44 "answered" wording to the next spec change.
- M1k: measure the staging load and deploy peak with the new caps.
