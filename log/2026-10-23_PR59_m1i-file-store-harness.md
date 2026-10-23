# PR 59 — feat(documents): M1i file store with quarantine, verified open, clamd scan and failpoint harness

- **Merged:** 2026-10-23T15:23:25Z (GitHub) · **Merge commit:** `7de4bc2607abae4b4700828a91b6a901ff425958` · **Branch:** `feat/m1i-file-store-harness` (final head `5405b5f69fc955069b02e8210ce35788684ea1b8`)
- **Gate breaches:** none (owner-approved size: one PR, about 1,490 lines, about 860 tests; G14 yes)
- **Approval receipt:** `reviews/PR-59.receipt` on `agent-logs`, committed 2026-10-23T15:20:27Z (before the merge); names head `5405b5f…`, review `reviews/PR-59.md` (hash `ad083a2d…`, equal to the archived copy), CI green on that exact head (checks, host, image, security).
- **Merge evidence:** `gh pr view 59` → MERGED, merge commit `7de4bc2`, final head equals the reviewed head of Round 2; `git merge-base --is-ancestor 7de4bc2 origin/main` succeeded.
- **Drafted by:** Opus subagent under the builder · **Final verdict:** Approved (Round 2)
- **Spec:** v1.18, hash `0edfb3cdc514e1d5bbd3ae3d34875cd16c037644` · **Milestone:** M1i

## What changed
`app/documents/storage.py`: quarantine write (magic allow-list PDF/PNG/JPEG, size limit while streaming, tmp → fsync → rename → directory fsync, `O_NOFOLLOW`/`O_EXCL`), `publish_clean` under `pg_advisory_xact_lock` (H5 steps 1–6), `open_verified` (size and SHA-256 before the first byte; `integrity_failed` mark), sweeper helpers, five failpoints that exist only under test settings. `app/documents/clamd.py`: stdlib INSTREAM client, fail closed. Storage issues no SQL (caller passes a `FileRows` bound to its transaction). Semgrep `files-volume-only-storage` and `documents-storage-no-db`; import-linter 9 contracts. `files_probe` harness (G14) in `make test-live`; EICAR against a real clamd in `make host-test-live`. Round 1 fix: tests for five storage mutants; `CLAMD_CONF_AlertExceedsMax: "yes"` on the clamav service and the test container, a limit hit is never clean (`failed`); uuid checks on path parts and an exact clean key; mark-then-raise documented.

## Review rounds
- R1 (Revision required): P2 tests did not protect the sweeper keep side, the agency check, the clean-status check or a socket closed mid-stream; P2 clamd answered OK for a partly scanned file; two P3 (path parts and keys; mark-then-raise). TEN-10 reading confirmed, PROJECT.md §7 confirmed out of date, G14 recorded. All fixed.
- R2: Approved. One optional P3: the PR self-check table was not updated for the fix.

## Deferred conditions
- none.

## Decisions worth keeping
- Storage touches no database; `FileRows` runs inside the caller's `with_agency()` in M16. No TEN-10 allow-list entry.
- A scan cut short by a clamd limit is `failed`, not `infected` (not known malicious; a retry hits the same limit; never served; source kept). The mounted `clamd.conf` planned for non-root must keep `AlertExceedsMax yes`.
- With that setting, a legitimate file over a default limit is refused; the owner may tune limits when real documents arrive.
- The caller of `open_verified` must catch `FileIntegrityError` and commit the mark outside a rolled-back transaction.

## Follow-ups
- PROJECT.md §7: the file-store harness runs under `make test-live`; only the clamd test runs under `host-test-live` (setup follow-up, not a feature PR).
- Still open (DECISIONS): clamav as non-root needs a mounted `clamd.conf`; the backup service (uid 10003, M6) cannot read 0600 files; the alert channel is an error log line only; limits not covered by `AlertExceedsMax` (MaxScanTime, MaxEmbeddedPE, MaxHTMLNormalize, PCRE) were not probed; `SKIW_FILES_ROOT` and the clamd address are not in `compose.yml` until M16.
- Re-run the harness on the real `document` table in M16.
