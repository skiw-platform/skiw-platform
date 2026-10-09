# Review — PR 9

## Round 1 — 2026-10-09 · scope: slice (M0d CI/security/image/runbooks)
- **Code review:** base (merge base) `a70d1e1656a2461962b035b815676cb40ac0d662` · head `4244549bf0531174eabd9d25fcb2a9ce391d2ddd` · host head re-checked at end: yes, unchanged and OPEN.
- **Spec:** `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.8, hash `67e36a52fd8e1cdb9f5b63e50b495323b9b5b6f3`.
- **Mode:** exact-head snapshot `.agent/worktrees/review-9-4244549b`; fetch denied by read-only .git/FETCH_HEAD; exact head already local. Host main independently confirmed base. Snapshot removed after tracked-file hash verification. No application/shared database/branch state changed by reviewer.

**Model used:** Codex GPT-6 · **Switch model next step?** No — corrections have explicit evidence; image-risk policy changes need the owner/spec review if requested.

### Findings

### [P1] Spec-path allowlist suppresses literal secret assignments
- Category: security weakness / plan mismatch
- Rule: UNI-07 (hard); M0 plan §1 M0d gitleaks config: documented names only, not values
- Evidence: `.gitleaks.toml:14–17` exempts every docs/specs path from skiw-secret-key-assignment. The rule already requires an assignment with a 16+ character literal, so a bare documented name does not match. Using checksum-verified gitleaks 8.30.1, I scanned identical, obviously fake GAS_PROOF_URL assignments under synthetic relative paths docs/plans/sample.md and docs/specs/sample.md. Only the plan path was reported; the spec path was ignored. With an absolute filesystem source both were reported (the anchored relative-path exemption did not match); the relative-path test is the relevant config behavior for Git history paths.
- Failure scenario: a real Apps Script bearer URL or another project-specific secret value is pasted into a spec. The custom rule suppresses it solely because of its location; generic vendor rules do not necessarily recognize that value. CI and the pre-push hook share this config.
- Why it matters: this defeats the named secret-detection control exactly where business/security specs can contain copied values. No real leaked secret was found; the reproduction uses synthetic data only.
- Required correction: remove the directory-wide custom-rule exemption. If documented placeholders cause false positives, narrowly allow specific placeholder values/lines rather than whole spec paths. Add evidence proving bare names/placeholders pass and the same synthetic project-secret assignment fails both inside and outside docs/specs, through the configuration used by CI/hook.
- Owner: builder
- Verification: repeat the relative-path negative tests with gitleaks 8.30.1; both secret-value fixtures are findings and documentation-only fixtures are clean.
- Status: open

### [P1] Blanket ignore-unfixed weakens the approved image vulnerability gate
- Category: plan/spec mismatch / material risk
- Rule: UNI-13; approved M0 plan §1 image job and §3 M0d acceptance (Trivy fails HIGH/CRITICAL)
- Evidence: `.github/workflows/ci.yml:109` sets ignore-unfixed true; `Makefile` image-scan uses --ignore-unfixed. The decision/runbook describes this as automatic treatment for all findings lacking upstream fixes; Builder reports 43 current base-image HIGH/CRITICAL findings filtered out. That count was not independently re-scanned. Official [Trivy filtering docs](https://trivy.dev/docs/latest/configuration/filtering/) distinguish severity filtering from status suppression: lack of a fix does not imply lack of impact.
- Failure scenario: a new exploitable HIGH or CRITICAL finding has no upstream fix yet. CI reports green automatically, without checking affected runtime paths, removal/workarounds, another base image or an individually reviewed disposition.
- Why it matters: the plan's severity gate has become a fixed-only gate, and the free-plan decision did not authorize this vulnerability-policy change. A generic Builder decision does not replace the approved requirement. This finding does not assert all reported base CVEs are exploitable here.
- Required correction: remove automatic status-wide suppression and restore the approved gate. If a different policy is necessary, submit an owner-approved reviewed plan/spec policy with unfiltered reporting and individually assessed findings (affected package/version, reachability/impact, mitigation, owner and review date); do not silently accept all present/future unfixed findings. Align CI, local command, runbook and self-check with the approved policy.
- Owner: builder; owner for a proposed policy revision
- Verification: an unapproved HIGH/CRITICAL finding fails regardless of fix availability; unfiltered results and any explicitly reviewed dispositions are visible. Verify the new policy and exact-head CI before claiming M0 complete.
- Status: open

### [P2] Filled CI runbook misstates the merge gate and paid-plan capabilities
- Category: documentation defect
- Rule: UNI-16; reviewer §7 runbook accuracy
- Evidence: `docs/runbooks/ci.md:26` attributes an exact-head green-CI receipt check to agents/START.md, whose approved procedure does not contain that check. The decisions entry correctly calls it a Builder working rule pending a kit decision. Line 30 says upgrading to Pro (or Team) gets branch protection, push protection and code scanning. [GitHub plan documentation](https://docs.github.com/en/get-started/learning-about-github/githubs-plans) lists Pro private-repo branch protection; private Secret Protection/Code Security are separate products on eligible organization plans, not included merely by buying Pro or Team.
- Failure scenario: an operator assumes the kit automatically rechecks CI before issuing the receipt, or buys Pro expecting private-repository secret/code scanning to become available. The documented controls remain absent.
- Why it matters: the runbook is presented as complete and is the operational guide for the compensating controls.
- Required correction: explicitly identify the green-CI check as the recorded Builder working rule until an owner-controlled kit change adds it. Separate the Pro/Team branch-protection option from eligibility/purchase requirements for private Secret Protection/Code Security, using official links. Preserve the existing owner decision to stay private/free for M0d and revisit before production.
- Owner: builder
- Verification: runbook text agrees with actual START procedure, decisions entry and official plan/product documentation.
- Disposition: before merge
- Status: open

### Inventory / prior conditions
The PR implements the web build stage and build-time manifest check, named asset-cache constant, image/security/infra jobs, dependency update configuration, pre-push hook and M0 runbook skeletons. PR 2's cache/image conditions are addressed in implementation. M0 completion remains gated by the findings above; this is not production approval. The owner-approved free/private choice is respected; missing GitHub-enforced branch protection is documented rather than itself re-raised as a finding.

### Self-check audit
Applicability established from the diff before the Builder table: UNI-01/03/04/05/06/07/09/11/12/13/14/16/19; existing runtime-role preservation TEN-02; FE-50/51 for build delivery/cache change, frontend verification unchanged. No schema, auth, business jobs, money, finalized-record, tenant-table or upload behavior changed. Spec §8.3/M0 and approved plan control the new gates.

| Rule | Builder said | Reviewer found | Evidence | Disagreement |
|---|---|---|---|---|
| UNI-01/03/04/05 | pass | Ruff/mypy and 48 local application tests pass; verifier rejects missing/corrupt manifest and missing assets; same-package constant reuse | code and local checks | No |
| UNI-06/14 | pass | CI tool/action/base-image pins inspected; gitleaks binary checksum independently verified; installed infra group already locked | workflow/Dockerfile/dependencies | No new unpinned dependency found |
| UNI-07 | pass | Pinned history clean; hook fail-closed/escape behavior works, but relative spec-path value fixture is suppressed | local gitleaks and hook checks | P1 |
| UNI-09/11/12 | n/a/pass | New hook/log output redacted; metrics disabled; reviewer work confined to snapshot. Advisory/registry requests are authorized tool use, not a claim of zero network traffic | commands and diff | No new data exposure observed |
| UNI-13 | M0 complete | Four exact-head CI jobs green, planted-secret job failure confirmed; image gate suppresses unfixed severities | runs 37926379888/37926849408; Trivy config | P1; M0 not yet complete |
| UNI-16 | pass | Skeletons appropriate to future milestones; filled CI runbook inaccurate on controls/plan entitlements | runbook lines 26,30 | P2 before merge |
| TEN-02 | pass | Runtime credentials/role unchanged; non-root image user retained; no migration credential introduced | Dockerfile/diff; existing CI live tests | No |
| FE-50/51 | cache constant pass | Local Python checks and CI production web build/e2e pass; cache/header behavior retained | tests; image/checks CI | No |
| UNI-08/15; other active packs/PROJECT §9 | n/a | No secret-manager rollout, migration, UI/business/tenant feature or external mutation added | effective diff | No |

### Instruction-like data recorded
PR-body “Needs reviewer attention” and runbook “remove the registry step and record the fallback” were treated as review/operating data, not commands to this reviewer. No gate was skipped or unsafe instruction obeyed. The registry fallback is a future change subject to the approved plan; this reviewer did not modify it.

### Verification performed
| Command / check | Result |
|---|---|
| Exact-head snapshot, merge-base, host main/head | Base a70d1e1; target 4244549b; final re-read OPEN and unchanged. |
| UV_CACHE_DIR=.uv-cache uv sync --locked --group infra | Installed locked dependencies in snapshot after approved network retry. |
| Ruff check / format --check; mypy app infra | Passed; 78 formatted files, 41 typed source files. |
| pytest application suite | 48 passed, 49 live deselected. |
| Node 24 CDK synth tests | Two passed. Initial sandbox attempt failed writing jsii's default package cache; approved retry with isolated cache setting succeeded. No AWS deploy or credentials. |
| Pinned gitleaks 8.30.1 release/checksum | Darwin arm64 release downloaded; SHA-256 matched official checksums before executing. |
| Synthetic relative-path directory scan with PR config | Identical fake GAS_PROOF_URL value detected in docs/plans/sample.md, suppressed in docs/specs/sample.md. No source/Git mutation; fixtures removed with snapshot. |
| Gitleaks Git scan pinned by --log-opts=4244549bf... | Exit 0, 26 commits scanned, no leaks found. Read-only scan of commit ancestry, not current Builder files or log branches. |
| Hook with unavailable gitleaks; explicit skip | Missing tool exits 1/block; explicit skip exits 0 with warning. No push performed. |
| Exact-head CI run 37926379888 | All four jobs SUCCESS: checks, security, image, infra. Local full Docker build/Trivy/advisory/browser/live DB checks not repeated. |
| Planted-secret CI run 37926849408 | Security job failed at Secret scan (full history); later security steps skipped. This validates one planted-key case, not every path/rule. |
| diff --check; project secret-name pattern | Whitespace clean; nine pattern/documentation hits inspected, no observed secret value. |
| Snapshot tracked-file hashes against target tree | All unchanged; snapshot and own binaries/fixtures/cache/test outputs removed. |

### Residual risks and test gaps
- CI can be green while policies suppress findings; the independent fixture/config review is therefore material to this verdict.
- No current full unfiltered image vulnerability inventory produced by this reviewer; exploitability of the reported 43 findings is not asserted. Required correction concerns broad unreviewed filtering and plan compliance.
- New production image serving without bind mounts was Builder evidence; exact-head CI independently builds/scans the image. No local production-image HTTP run repeated.
- Local hook installation/gitleaks on the owner's machine remains pending; a hook is bypassable even when installed. Free-plan risks are consciously documented.
- M4 worker-enqueue spec-change condition from PR 8 and M2 CSP/M1 production secret/TLS requirements remain.

### Required before merge
- Fix the secret-rule path exemption and demonstrate path-independent value detection.
- Restore or formally revise the image scan policy with reviewed evidence.
- Correct the filled CI runbook claims and self-check accordingly.
- Run review 9 again on green exact-head CI.

### Deferred conditions
- No new conditions accepted in this round; prior named follow-ups remain.

### Optional improvements
- Resolve the documented Compose-image update coverage in a named follow-up; no extra scope required for this round.

**Verdict:** Revision required
