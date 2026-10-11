# Review — 2026-10-11-hosting-options

## Round 3 — 2026-10-11 · scope: slice (hosting paper v1.5, lean VPS and export backups)
- **Spec review:** `docs/specs/2026-10-11-hosting-options.md` · version 1.5 · hash `76ddea6a57f98db27e95a6be284c394ebff0d9fa`.
- **Pinned PR 21:** base `21db4511ffaa80741572d3adae35d54c3183a1f5` · head `554f8ea1bebde03160c270158092eed5c6ef98aa` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-hosting-554f8ea1`; tracked-file integrity verified; own snapshot removed. No source/decision/handoff changes by Reviewer.
- **Scope expansion:** v1.2–1.5 add lean Render, Malaysian/self-run VPS, reported owner downtime preferences and export-backup proposals. Round 2 approval does not cover these added sections automatically. Platform v1.13 remains approved/reconciled; no platform adoption inferred.

### [P1] Database-only export is insufficient for the claimed clean-host recovery
- Category: material recovery-design gap
- Rule: paper §3.5/M6'; platform T13/T19/D14/D18; UNI-16 recovery proof
- Evidence: §3.5:478–501 specifies pg_dump -Fc and a clean-instance pg_restore → audit verification → readyz drill. Its table:597 says G/L+pull cover host/provider-account loss. B4:250 stores application files on the VPS disk, while off-site backup is costed for database/WAL. No recovery inventory captures external files or app-held crypto/MAC keys; roles/NOLOGIN ownership bootstrap is also absent from the stated fresh-instance restore sequence.
- Primary source: [PostgreSQL pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) dumps one database, not cluster-global roles/tablespaces. Uploaded filesystem/object-store files and app-held secrets are outside that database. Roles may be reproducibly recreated instead of backing up passwords, but their attributes, ownership and privileges must be recovered explicitly.
- Failure scenario: B4's VPS/disk is lost. Owner pulls the encrypted database dump and decrypts it, but uploaded scans/PDFs still exist only on the lost disk. If app-held audit/MAC/encryption keys were only on that host, audit verification and encrypted-data recovery also fail. A readyz/row-count check can pass without proving the referenced documents are available. On a fresh cluster missing roles/ownership, restore itself can fail or recreate incorrect authority.
- Why it matters: the new paper presents exports as the recovery basis for tolerating downtime. Recoverable rows are not recoverable service/data. An unspecified quarterly drill is insufficient when the defined drill excludes essential artifacts. P1 design risk, not a claim that current code or real backups have lost data.
- Required correction: distinguish database recovery from complete host/account recovery. Add a minimal recovery inventory and safe custody/bootstrap requirements: uploaded files (especially B4), role/ownership/grant setup, relevant app-held key versions and protected key recovery, configuration/digest, dump decryptability and authoritative audit anchors where required. No secrets in the repo or routine plaintext backups. Narrow the coverage table where artifacts are not included. Require a clean-host drill that opens a recovered referenced file, verifies historical audit/MAC/encrypted data with recovered keys, and rechecks runtime/definer role attributes. Reflect extra storage/copy costs or mark them provisional. Full implementation can remain in the adopting spec/M6', but the options paper must state this prerequisite.
- Owner: Builder
- Verification: recovery coverage matches captured/reproducible artifacts; adopting milestones explicitly test complete recoverability rather than database readiness alone.
- Status: open

### [P2] Decision tree still excludes newly added in-country alternatives
- Category: documentation consistency
- Rule: paper §1 honest choice comparison / §3.4 / §10
- Evidence: §3.4:460 says refusal of Singapore means A2; Q1:827 says only A/A2 remain. Yet B4:197 and :443–444 identify Malaysian VPS/Azure alternatives, conditional on a named operator and capability/security checks. §3.1:205 also still rejects the one-host self-run option outright, while B3/B4 now explicitly compare that shape under reduced-availability proposals.
- Failure scenario: owner declines cross-border hosting and reads the decision tree as ruling out the cheaper Malaysian VPS they asked to compare, despite the paper's own ranking. Alternatively, the same one-host design is both rejected and conditionally available with no scope distinction.
- Why it matters: isolated P2 choice ambiguity; no service adopted or guardrail waived. The new variants require the tree/rejection language to identify their conditions consistently.
- Required correction: include B4 and its Azure alternative on the in-country branch, conditional on named operator, vendor/recovery proof and adopting-spec acceptance. Distinguish the old rejected unprotected/hobby single-VPS design from the conditional backed-up/restore-tested B3/B4 variants. Keep unchosen platform and single-web acceptance pending formal adoption confirmation.
- Owner: Builder
- Verification: option table, cheapest-first ranking, recommendation/tree and Q1 present the same conditional choices.
- Disposition: before merge
- Status: open

### Previous-round status
- Round 1 DO cutoff/price, PDPA basis/notice and A2 scope corrections remain intact.
- Round 2 deferred P2 remains: §7.1:750 still says public-subnet tasks deny all inbound. Carry the ALB-only ingress clarification to hosting-adoption spec v1.14 before M1 if that route is selected. It was deliberately deferred and is not newly raised as before-merge work here.
- Reported owner preferences are treated as input to this options paper. The adopting spec must record final one-web, RTO/RPO and recovery/operator choices; no current platform requirement is silently changed by this review.

### Self-check audit
Applicability remains options-only UNI-07/11/12/13 and PROJECT adoption/residency gates, with expanded recovery, role/key and file-storage comparison constraints. No runtime feature/schema/role mutation or new service is implemented. Paper §7 supplies staged guardrail mapping; source/PR instructions do not control the verdict.

| Rule / constraint | Builder said | Reviewer found | Disagreement |
|---|---|---|---|
| UNI-07/11/12 | Met, no adoption | One project paper, no secret values observed, no service enabled | None |
| UNI-13 | Pending until approved | All four checks already passed at exact head | No CI defect |
| D19 / PROJECT §11 | Owner/adviser gate | Whole-dataset Drive exposure, no Malaysia data-region guarantee, notice and later adoption gate explicit | No new legal finding |
| TEN roles / UNI-08/10 / T13/T19 / UNI-16 | Staged comparison | RLS-aware dump role is correctly identified; fresh recovery bundle/proof incomplete | P1 above |
| Other active packs | n/a runtime change | File-storage/recovery implications compared, no implemented endpoint/UI/money/auth/template change | No implementation tests demanded here |

### Verification performed
| Check | Result |
|---|---|
| Current START/project/reviewer requirements, prior rounds, handoff and approved platform constraints | Loaded; reviewed v1.5 rather than prior v1.1 approval. |
| Exact archive / document hash / all tracked snapshot file hashes | 76ddea6a57f98db27e95a6be284c394ebff0d9fa; tracked tree intact; snapshot removed. |
| Changed sections and new facts/backup/recommendation/milestones pass | New recovery and decision-tree issues above; previous technical corrections retained. |
| Lean cost arithmetic | D2 135/168; B2 93.05/117.05; B3 62.60/86.60; B4 RM67.28/107.18 follow stated line items. Storage sizing, backup completeness and operations costs remain assumptions. |
| Primary-source spot checks | PostgreSQL dump/RLS/globals; iCore advertised node pricing and Malaysian locations; Render deploy/disk limits; Google Workspace data-region support. Not a full verification of all 48 rows or Azure prices. |
| git diff --check base→head / paper secret-pattern scan | Passed; zero project secret-name-pattern hits in paper. No local full-history scan claimed. |
| Final host head/state/CI 38129271171 | 554f8ea1bebde03160c270158092eed5c6ef98aa unchanged, OPEN; checks/security/image/infra SUCCESS. No runtime DB/restore/deploy test executed for the paper. |

### Residual risks and test gaps
- No database-role spike, provider quote, complete restore, load/shutdown test or real-data transfer performed. Conditional prices and provider capability assumptions cannot authorize adoption.
- Dump RPO equals the schedule interval only under successful timely completion; host-loss recovery must use the age of the latest verified off-host recoverable snapshot, including dump/pull delays and failures. The adopting backup plan should define this measured freshness/alert policy, not promise the nominal cron interval unconditionally.
- Hourly dumps retained 35 days need a different capacity/cost assumption from the paper's 1-GB daily-dump example (35 GB). Quotas/costs must be re-evaluated when Q11 selects cadence/retention; costs may move rankings.
- Persistent backup scheduling/admin credentials and Drive mutation/import boundaries must be reconciled explicitly in the adopting spec; no permission to bypass current worker-only schedules, closed DB-role/DB-access rules or locked Drive/AI switches.
- Fresh-cluster backup-role/BYPASSRLS privileges on managed providers remain unknown and must pass S1 before reliance. Existing runtime stays NOSUPERUSER NOBYPASSRLS.

### Required before approval/merge
- Builder corrects recovery coverage/inventory/drill prerequisites and the in-country/one-VPS decision branches, bumps the paper version, returns for exact-hash review.
- This does not require implementation or live provisioning in the options-paper PR.

### Deferred conditions
- Existing Round 2 P2: hosting-adoption spec v1.14 before M1 if A2 public-subnet tasks are selected must preserve ALB-only necessary service/health-check ingress while prohibiting direct Internet ingress.

### Optional improvements
- Refresh PR-body earlier savings/minimum-cost claims to distinguish old full-service totals from newly added lean VPS totals; cite current exact-head successful CI rather than Pending.

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate for recovery/security design review.

**Verdict:** Revision required

## Round 2 — 2026-10-11 · scope: slice (hosting decision paper v1.1, not platform adoption)
- **Spec review:** `docs/specs/2026-10-11-hosting-options.md` · version 1.1 · hash `c80a189954be2d362cdccc454ba0f042c81693d7`.
- **Pinned PR 21:** base `21db4511ffaa80741572d3adae35d54c3183a1f5` · head `725a976e32d59f2e5568a4b38b1eda12ef6cce14` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-hosting-725a976e`; all tracked files match the pinned tree; snapshot removed. Reviewer changed no builder source/document/handoff.
- Approved platform spec and PROJECT reconciliation remain v1.13/e314158562214a9173e7fdbd7ec6f2a8d9355dd9. This verdict approves a comparison for owner decision, not adoption or deployment.

### Round 1 resolution audit
| Finding | Status | Independently re-inspected evidence |
|---|---|---|
| P1 DO HA eligibility/cost | Resolved | F30–32 include account cutoffs and exempt existing clusters; §3.2 explicitly assumes post-30-Nov adoption, splits no-standby vs Advanced HA, shows US$260 two-node input, blocks unpublished shared-plan quote and SGP1 availability. Revised arithmetic is correct; shortlist now C without standby, D if outside-AWS standby needed unless a qualifying quote changes it. [Official changes](https://docs.digitalocean.com/release-notes/upcoming/dbaas-plan-changes/), [pricing](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/) rechecked. |
| P2 PDPA basis/notice | Resolved | F33/§4, decision tree and Q1 distinguish statutory condition, supporting assessment and mandatory notice/records; adviser determination and adoption gates retained. Quoted old D19 marked historical; adopting spec must correct it. [JPDP guideline](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2025/08/GP_CBPDT_EN.pdf) rechecked. |
| P2 A2 cut/adoption scope | Resolved | §7.1 states retained/replaced/removed controls, risks, owner choices, NAT options and provisional commitment rates. §9 covers D15/§8.3/T13/T18/M6/runbooks; Q6/7 preserve pending owner decisions. One narrow networking wording issue below is deferred to adoption. |

### [P2] Public-task ingress wording must preserve ALB access
- Category: documentation ambiguity / planning detail
- Rule: paper §7.1 consistency with retained ALB deployment flow and M1' readiness requirement
- Evidence: paper:345 public-subnet-task alternative ends “security groups must deny all inbound”. This includes the inbound connection from the retained ALB, not only direct Internet access. [AWS target security-group documentation](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-register-targets.html) specifies ALB-source listener and health-check ingress.
- Failure scenario: the adopting design copies this literally, so web targets never pass health checks or receive ALB requests.
- Why it matters: isolated P2 planning ambiguity, not an implemented security failure. A2 is unselected; an adopting spec and M1 plan are independently gated before implementation. Safe to merge this options-only comparison with the named follow-up.
- Required correction: if A2 public-subnet tasks are selected, prohibit direct Internet ingress while explicitly allowing only necessary web listener/health-check ingress from the ALB security group; worker/migrate tasks need no service ingress. Add M1 proof that ALB readiness succeeds and direct-public access fails. No instruction to expose task ports publicly.
- Owner: Builder
- Verification: adopting spec states both permitted ALB and prohibited public paths; M1 IaC/smoke checks prove them.
- Disposition: deferred to the hosting-adoption spec v1.14 PR, before its M1 plan/implementation, if A2 public-subnet tasks are selected. If another hosting/networking route is chosen this alternative is not implemented.
- Status: open (deferred)

No open or accepted-risk P0/P1 finding; no P2 before-merge correction.

### Self-check audit
Round 1 applicability retained: options-only UNI-07/11/12/13 and D19/PROJECT adoption boundary; tenancy, identities, audit, deployment and recovery are comparison constraints, not newly implemented/waived requirements. §7's guardrail map supplies staged comparison evidence; no new active-pack runtime scope.

| Rule / constraint | Builder said | Reviewer found / evidence | Disagreement |
|---|---|---|---|
| UNI-07/11/12 | Met; no adoption | No secret values observed, one new project paper, no external service/data transfer enabled | None |
| UNI-13 | Delivery pending until approved | Four successful exact-head checks, run 38121064964 | No failure; PR may cite the now-known result |
| D19 / PROJECT §11 | Owner/adviser checklist | Correct condition/evidence/notice wording and later adoption requirement | Resolved |
| TEN/secret/audit/backup/deploy constraints | Staged comparison, §7 map | Role/identity/region gaps remain marked; A2 cuts now accounted for | Narrow deferred ingress correction |
| Other packs | n/a, no runtime change | Appropriate | None |

### Verification performed
| Check | Result |
|---|---|
| Current instructions/PROJECT, handoff, prior findings and exact revision diff | Loaded; all three corrections re-inspected rather than relying on builder claims. |
| git archive pinned head / hash-object / tracked-file integrity | c80a189954be2d362cdccc454ba0f042c81693d7; all tracked files intact; snapshot removed. |
| git diff --check base→head; file inventory | Passed; hosting paper only. |
| B/C arithmetic | B no standby 122.60–186.60; HA 352.15–416.15. C no standby 123.60–194.60; HA 353.15–424.15. Printed rounded ranges consistent. |
| Primary sources | DO cutoff/pricing, JPDP guideline and ALB ingress requirements rechecked. No full revalidation of every unchanged fact row or quoted price. |
| Paper secret-pattern scan | Zero hits; not a local full-history scan. |
| CI 38121064964 / final host check | checks/security/image/infra SUCCESS at 725a976e32d59f2e5568a4b38b1eda12ef6cce14; final head unchanged, OPEN. No local runtime tests repeated. |

### Residual risks and test gaps
- A2 cost remains provisional; removed controls require explicit owner choices and an adopting reviewed spec. Unsupported vendor identity/role/HA/backup/log/deploy assumptions still need proof before adoption.
- DO Advanced HA amounts are conditional comparison inputs, not a verified SGP1 offer; unpublished shared-plan quote remains blocked. Selection may change when actual quotes are obtained.
- No provisioning, DB spike, restore/load/deployment test or real-data transfer authorized/performed. G-AI/G-DRIVE and all existing locked switches remain closed.
- Paper approval does not change the approved platform spec hash or PROJECT facts. Reconcile with `setup` Part B after the eventual approved adopting platform-spec change, not by replacing the main spec hash with this paper's hash.
- No verdict-changing instruction from PR/source/vendor text followed.

### Required before merge
- No review correction required for this options-only PR. Builder archives the complete review and creates the normal exact-head approval receipt before owner merge; preserve the deferred condition.

### Deferred conditions
- Hosting-adoption spec v1.14 PR, before M1 planning/implementation if A2 public-subnet tasks are selected: clarify ALB-only necessary service ingress and deny direct Internet ingress, with positive/negative M1 checks (P2 above).

### Optional improvements
- Cite successful exact-head CI in the PR body instead of leaving its delivery status pending.

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate for hosting-adoption design and review.

**Verdict:** Approved with conditions

## Round 1 — 2026-10-11 · scope: slice (hosting decision paper, not platform adoption)
- **Spec review:** `docs/specs/2026-10-11-hosting-options.md` · version 1.0 · hash `40ab593ad5963c29376439a9fbef163635e18e80`.
- **Pinned PR 21:** base `21db4511ffaa80741572d3adae35d54c3183a1f5` · head `824a1ef66f59a97f42fb7f7130910be066c3d484` · host head re-checked at end: yes, unchanged and OPEN.
- **Mode:** exact-commit snapshot `.agent/worktrees/review-spec-hosting-824a1ef6`; all tracked files verified against pinned tree, snapshot removed. Target is absent from main and was reviewed from PR 21, not substituted with the main platform spec.
- Approved platform spec remains v1.13, e314158562214a9173e7fdbd7ec6f2a8d9355dd9; no platform chosen or adopted by this review.

### [P1] DO HA price ignores an announced near-term eligibility change
- Category: objective defect / material decision risk
- Rule: reviewer §4 invented/current values and evidence; paper §1 honest cost/capability comparison
- Evidence: F4:31 and §3.2:99 use a roughly US$60.90 2-GiB primary+standby for B/C. §3.4:145–156 shortlists C using the resulting US$123–225 range. The cited official pricing page itself links an announced change: [DigitalOcean database plan changes](https://docs.digitalocean.com/release-notes/upcoming/dbaas-plan-changes/) (verified 30 September 2026).
- Source-supported fact: restrictions start 15 October 2026 for accounts that have never created a PostgreSQL/MySQL cluster, and 30 November for all accounts creating new clusters. New Standard Edition clusters then cannot have standby/read-only nodes; HA needs Advanced Edition. Existing qualifying clusters are exempt. The current [pricing page](https://docs.digitalocean.com/products/databases/postgresql/details/pricing/) lists Advanced Edition from US$130 per primary, with matching standby pricing; the new shared Advanced plans need their own verified quote.
- Failure scenario: owner picks C for cheap managed HA, provisions after the cutover, and discovers the costed standby cannot be added. The adoption date/account eligibility is unknown, so the currently available price cannot be presented as the unconditional future HA case.
- Why it matters: HA is the main high-case trade-off in this cost-driven selection; the missing announced constraint can change the shortlist materially. This is not a minor stale price.
- Required correction: describe cutoff/account/existing-cluster eligibility; price an available HA configuration for the likely adoption date, or explicitly mark HA cost blocked pending a vendor quote/eligibility check. Recompute B/C ranges and recommendation/claims as appropriate. Do not assume the owner will rush to provision an exempt cluster.
- Owner: Builder
- Verification: date-qualified primary source, verified selected edition/node price and coherent totals/shortlist.
- Status: open

### [P2] Distinguish the statutory transfer basis from its assessment, and fix notice checklist
- Category: documentation accuracy
- Rule: D19 / PROJECT §11; reviewer §4 current legal evidence
- Evidence: §4:180–184 calls a TIA a basis alternative to a s129 exception and makes privacy-notice updating conditional on adviser preference. Decision tree:153 and Q1:302 repeat that shorthand. The inherited D19 quotation can remain identified as a quotation, but the new operational checklist needs accurate wording.
- Source: [JPDP Cross Border Personal Data Transfer Guideline 3/2025](https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2025/08/GP_CBPDT_EN.pdf), §§4.1–4.3, 5.3, 6.2. A TIA supports findings under section 129(2); it is not an independent statutory permission. Other section 129 conditions may apply. §4.3 requires informing subjects of the transfer through a privacy notice or other written notice.
- Failure scenario: owner records only completion of a TIA and considers notice optional, without recording the applicable transfer condition or notice evidence.
- Why it matters: P2 here because this is an options-only paper with explicit adviser/sign-off and later spec gates, not an enabled transfer or a legal-compliance implementation. Those gates must remain.
- Required correction: require the adviser to identify the applicable section 129 condition and supporting evidence (including TIA where relevant); require compliant transfer notice and record how it is satisfied. Align decision-tree/question wording; no conclusion that Singapore is automatically acceptable.
- Owner: Builder, with adviser determination left to owner
- Verification: corrected checklist cites current primary guideline and distinguishes basis, assessment and notice.
- Disposition: before merge
- Status: open

### [P2] A2 adoption-change matrix understates the controls it removes
- Category: documentation consistency / planning gap
- Rule: paper §§3.1/7/9; approved platform D3/D15/D17/T13/T18, M6 and UNI-16
- Evidence: A2:79 removes WAF, locked second-account backup, X-Ray and PR previews and proposes a NAT instance/public-subnet alternative. But §9:289 marks D15 CI/CD unchanged and :294 lists only §8.2/M1 for the combined §8.3/M6/threat-model row. §7 threat-model changes address B/C/D, not the shortlisted default A2. Platform spec T13:580 requires the locked backup and T18:585 WAF; M6:667 includes vault lock and recovery proof. Removing preview environments also affects §8.3.
- Failure scenario: owner selects A2 and its adopting spec/plan follows the listed minimal edit scope, leaving retained backup/WAF/environment requirements contradicting what will actually be bought and built.
- Why it matters: being in Malaysia does not preserve the removed recovery/abuse controls. This paper need not finish an implementation design, but must identify the security/operational decisions and affected requirements accurately.
- Required correction: add A2's lost controls/residual risks and owner decisions to §7/open questions; expand its §9 change scope to relevant D15/§8.3, T13/T18, M6 and runbooks. Distinguish NAT alternatives, fixed-egress/patching responsibility, and provisional Savings Plan assumptions. Preserve unchanged controls separately.
- Owner: Builder
- Verification: every stated A2 cut has corresponding affected spec/plan/runbook scope and an explicit retained/replaced/removed control.
- Disposition: before merge
- Status: open

### Self-check audit
Applicability established for an options-only document: UNI-07/11/12/13 and PROJECT residency/adoption gates; existing tenancy, secret-store, audit, recovery, deployment and jobs requirements are comparison constraints, not implemented or waived by this paper. No UI/money/domain feature/schema/role implementation changed. §7 includes a guardrail map in addition to the PR table.

| Rule / constraint | Applies? | Builder said | Reviewer found | Disagreement |
|---|---|---|---|---|
| UNI-07/11/12 | Yes | Met; no adoption | No secret value observed; one project document, no service enabled or client data sent | None |
| UNI-13 | Yes | Pending, checked at approved time | All four exact-head checks already SUCCESS | Update evidence next time; no failure |
| D19 / PROJECT §11 | Yes, decision/adoption boundary | Adviser/owner checklist | Residency assumptions generally marked and adoption gated; legal checklist correction needed | P2 |
| TEN-01/02/09/11; UNI-08/10/16; D16 | Comparison constraints | §7 map; no runtime change | Vendor role/identity/deployment gaps honestly staged; no implementation proof claimed | A2 scope P2 |
| Other packs | No changed runtime feature | n/a | Appropriate options-only scope | None |

### Verification performed
| Check | Result |
|---|---|
| START/reviewer/PROJECT, decisions/handoff and approved platform requirements | Loaded; PR 21 is decision paper, no owner platform choice inferred. |
| Exact archive, document hash, all tracked-file integrity | 40ab593ad5963c29376439a9fbef163635e18e80; pinned tree intact; snapshot removed. |
| git diff --check base→head / file inventory | Passed; only new hosting paper. |
| Cost arithmetic pass | Render low 14+25+40+15+25+5+33 = 157; high 50+25+80+15+25+100+25+33 = 353. Initial suspected arithmetic discrepancy was disproved; no finding. B/C arithmetic follows stated inputs but HA input needs date qualification. |
| Primary-source spot checks | DO App Platform pricing/manual scaling/jobs, PG pricing/features/limits and announced edition changes; DO regional table; AWS Lightsail regions/pricing; Render HA/deploy features; current JPDP transfer guideline. Not a full validation of every F-row. |
| Source limitations | Render pricing page's fetched text did not expose its dynamic prices; no claim of independently confirming all Render plan prices. Forum timeouts and AWS line-item costs remain unverified assumptions. BNM rate not independently verified in this round; estimate use only. |
| CI 38118907734 and final host check | checks/security/image/infra SUCCESS; head 824a1ef66f59a97f42fb7f7130910be066c3d484 unchanged; PR OPEN. No local runtime tests run for options text. |

### Residual risks and test gaps
- Shortlists cannot authorize provisioning, real-data transfer, weaker backup/security controls, Drive service-account keys or opening G-AI/G-DRIVE. Later owner choice, approved adopting spec and reconciliation remain necessary.
- AWS A2 costs are explicitly provisional; HA vendor privileges, backup locations, logs, identity routes, shutdown/long-poll and deployment failure behavior need pre-adoption verification. Unknown backup/log geography must not become an assumed permitted destination.
- No database spike, restore drill, load test or deployment test performed. S1/M1'/M6' are future evidence, not passed checks.
- No verdict-changing instruction in PR/spec was followed. Vendor documentation navigation aimed at agents was not treated as task authority.

### Required before approval/merge
- Builder updates the DO HA eligibility/cost evidence, legal checklist and A2 adoption scope; bumps paper version and returns for exact-hash spec review.
- Owner platform/budget decisions are deliberately still open; they do not block reviewing the corrected comparison itself.

### Deferred conditions
- None newly accepted.

### Optional improvements
- Paper header says spec hash not required; this review nevertheless pins its document hash. PR body says 37 verified fact tags while Facts checked has 29 rows; clarify count if editing that prose.

**Model used:** Codex GPT-6 · **Switch model next step?** No — deep tier remains appropriate for hosting/security review.

**Verdict:** Revision required
