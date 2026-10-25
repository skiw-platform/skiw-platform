# PR 66 — docs: Hostinger replaces iCore as the VPS vendor (S1, spec v1.20)

- **Merged:** 2026-10-25T13:29:27Z (GitHub) · **Merge commit:** `5f4fc58cb6420df7e746ca4be78308d193f6cc21` · **Branch:** `docs/hostinger-vps-vendor` (final head `ecf85e00c00d4d444148cf52395bd4de88dc8ba9`)
- **Gate breaches:** none (docs only; 10 files, about 270 lines including the new 80-line amendment)
- **Approval receipt:** `reviews/PR-66.receipt` on `agent-logs`, written 2026-10-25T13:12:25Z (before the merge, by 17 minutes); names head `ecf85e0…`, review `reviews/PR-66.md` (hash `94aa8a1e…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 66` → MERGED, merge commit `5f4fc58`, final head equals the reviewed head; `git merge-base --is-ancestor 5f4fc58 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved (Round 1)
- **Spec:** main spec v1.19 → **v1.20**; amendment `docs/specs/2026-10-25-hostinger-vps-vendor.md` v1.2, hash `2ef0bb3aaf6509025c324058f4a3b0dee8e950d6` (spec review Round 3 Approved) · **Milestone:** M1 (vendor change before M1k)

## What changed
Hostinger replaces iCore for production and staging. Main spec v1.20 (text only): D3, D19, D24, T24, §8.2 (dated USD list prices, RM at 4.10), §8.3, §8.4 H1/H2/H6/H8/H12, UNI-11, control table, Q1/Q19/Q36/Q38, new Q43 (plan size) and Q44 (term). G-VENDOR keeps eleven items. M1 plan (G2, G3, G4 settled as Ubuntu 24.04, UNI-11 row, G8 note), five runbook headers, a one-line note on the hosting paper, and the DECISIONS entry "2026-10-25 — Hostinger replaces iCore as the VPS vendor (UNI-11, D19 record)". The amendment file was added unchanged.

## Review rounds
- R1: Approved. One optional P3 (the amendment puts quote marks around words the owner did not type; DECISIONS has the real words).

## Deferred conditions
- none.

## Decisions worth keeping
- Owner (2026-10-25): Hostinger for both hosts; KVM 1 or KVM 2 (open); Ubuntu 24.04. Merging this PR is the owner's confirmation that Hostinger's account data (b) is only the owner's own data (PDPA rule (a) of 2026-10-24).
- A Malaysian location is required; Kuala Lumpur is [A]; city and site come in writing under G-VENDOR item 1. Provider backups are off at purchase if allowed, else blocking without written terms.
- The owner typed `approved 66` after a plain-words summary of item (9).

## Follow-ups
- `review spec` of the main spec v1.20, then `setup` (reconciles `agents/PROJECT.md`, which still names iCore), then the owner buys.
- Q43 plan size and Q44 contract term (owner). If staging is KVM 1, staging caps drop by at least 256 MiB in their own PR.
- G-VENDOR: send the eleven questions to Hostinger and record the answers (M1k).
- Optional P3 from the review: the quote marks in the amendment, fix at the next spec change.
- Earlier optional items remain: PR 60 P3 (flapping check); the two alert value shapes for the amendment table; M1k real Telegram and UptimeRobot proof.
