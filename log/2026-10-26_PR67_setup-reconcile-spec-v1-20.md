# PR 67 — docs: setup reconcile PROJECT.md with spec v1.20 (Hostinger)

- **Merged:** 2026-10-26T07:25:57Z (GitHub) · **Merge commit:** `53f6a02c481c7c43d749d456f8f74e854f518202` · **Branch:** `docs/setup-reconcile-v1-20` (final head `1c357d1be38c9bcb03a8e7bd5bb71dcf53daaca7`)
- **Gate breaches:** none (one file, 6 lines)
- **Approval receipt:** `reviews/PR-67.receipt` on `agent-logs`, written 2026-10-26T07:24:55Z (before the merge, by 62 seconds); names head `1c357d1…`, review `reviews/PR-67.md` (hash `93cb711d…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 67` → MERGED, merge commit `53f6a02`, final head equals the reviewed head; `git merge-base --is-ancestor 53f6a02 origin/main` succeeded.
- **Drafted by:** builder · **Final verdict:** Approved (Round 1)
- **Spec:** main spec v1.20, hash `92841ba555e9e857ac70e86a5b043cf9729ed371` (review Round 23 Approved); amendment `docs/specs/2026-10-25-hostinger-vps-vendor.md` v1.2 · **Milestone:** M1 (reconcile before M1k)

## What changed
`agents/PROJECT.md` reconciled with spec v1.20: §2 spec hash `75ac19f6…` → `92841ba5…`; the one-sentence description, the `infra/` line, the residency rule (Malaysian location, city and site confirmed in writing, provider backups off or blocking, no PDPA claim) and the G-VENDOR locked switch now say Hostinger; "Other standards" lists the Hostinger amendment (Round 23 P3). Part A unchanged; no defaults applied; packs unchanged.

## Review rounds
- R1: Approved. No findings.

## Deferred conditions
- none.

## Decisions worth keeping
- `git grep -i icore agents/PROJECT.md` finds nothing (the amendment's S2 done-when).
- The reconcile and spec gates are clear for `build` at hash `92841ba5…`.

## Follow-ups
- Owner: Q43 plan size and Q44 contract term before buying. If staging is KVM 1, the staging-caps PR (at least 256 MiB lower, not from `SKIW_MEM_CLAMAV`) comes first.
- Owner buys the VPSs (Malaysian location, Ubuntu 24.04, automatic backups off if allowed), sends the eleven G-VENDOR questions, and records the answers (M1k).
- Owner to-do from earlier: SKIW_PUBLISH_PREDEPLOY and SKIW_BACKUP_IMAGE; G7; G6/T25 and STAGING_DEPLOY_KEY; G10; staging address and host key; Telegram bot per host and UptimeRobot monitors.
- Earlier optional items remain (PR 60 P3 flapping check; two alert value shapes; quote marks in the amendment's owner answer line).
