# Review — 2026-10-11-hosting-options

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
