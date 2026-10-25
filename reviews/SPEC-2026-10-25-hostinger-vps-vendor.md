# Review — 2026-10-25-hostinger-vps-vendor

## Round 2 — 2026-10-25 · scope: slice (vendor amendment v1.1)

- **Spec review:** `docs/specs/2026-10-25-hostinger-vps-vendor.md` · version 1.1 · hash
  `b6c1d4263c2e3fe98a57ed700656fd499c74def2` (working file, untracked in the main checkout).
- **Amends:** v1.19, hash `75ac19f61466445c35e4ff9341a0d0984a55249f` (unchanged). `main` =
  `origin/main` = `550b622`.
- **Mode:** read only; no file written except this one.
- **Model used:** Claude Opus 5.5. **Switch model next step?** No.

**Verdict:** Revision required

One P2 is left, and it is a one-line fix: the S1 test still fails on two lines that S1 itself asks
for. Everything else from Round 1 is resolved.

### Round 1 resolution audit (re-read in v1.1)
| Round 1 finding | Status | Evidence in v1.1 |
|---|---|---|
| P2 "Kuala Lumpur" as [V] and as a purchase gate | resolved | Decision 2: [V] for "Malaysia" only, the city [A] from the blog; §5, S3 and §7 say "a Malaysian location"; item 1 asks for country, city and site in writing |
| P2 automatic weekly backups | resolved | Decision 9: off at purchase if allowed, recorded; else blocking without a written Malaysian location, retention and deletion; item 3 asks "on by default … can they be turned off"; new §7 row; §5 and S3 |
| P2 plan rule and CPU | resolved | Decision 3: the facts with source and date; RAM rule "sum without `migrate` ≤ RAM − 1 GiB". I re-computed: production 6656 MiB ≤ 7168 (passes); staging 3328 MiB > 3072 (fails by 256). CPU halving stated; G-LOAD is the CPU test; KVM 4 the fallback; Q43 has the facts |
| P2 change list and §8.2 values | resolved | Decision 10 adds T24, H2, H6 (both lines), H1, the control-table heading; gives the new §8.2 text. I re-computed: (8.79 + 6.49) × 4.10 = RM 62.65 ≈ 63; (14.99 + 11.99) × 4.10 = RM 110.62 ≈ 111; RM 4.10 is the spec's rate (line 628). A catch-all adds any missed iCore line (for example the §8.2 intro, lines 626–627) |
| P2 S1 test cannot pass | **partly** | Allowed hits now list the changelog v1.14–v1.19, answered-Q history, the paper, this document, DECISIONS before 2026-10-25 and PROJECT.md until S2. Two required lines are still missing (below) |
| P3 prices and term | resolved | Decision 4 and Q44: paid upfront, ≈ US$211 and US$156 (I re-computed 210.96 and 155.76) |
| P3 Debian line | resolved | Decision 5: July 2026, Debian news of 2026-07-12, LTS to 2028-06-30 |
| P3 UNI-11 two kinds of data | resolved | Decision 11; S1 names it |

### Findings

No P0 or P1.

### [P2] The S1 test still fails on the v1.20 changelog entry and the new DECISIONS entry
- Category: untestable milestone
- Rule: reviewer §4 "each milestone has a testable done when"
- Evidence: S1 done when allows "the main spec's changelog entries v1.14 to v1.19" and "`docs/DECISIONS.md`
  entries dated before 2026-10-25", then "Any other hit fails the PR". But decision 10 requires a
  v1.20 changelog entry (it will say that Hostinger replaces iCore), and S1 requires the DECISIONS
  entry titled "2026-10-25 — Hostinger replaces iCore". Both hit `git grep -i icore`.
- Failure scenario: the S1 PR fails its own test. Or the builder drops "iCore" from the new entries,
  and the record no longer says what was replaced.
- Required correction: allow "changelog entries v1.14 to v1.20" and "DECISIONS entries dated
  2026-10-25 or before" (or name the new entry), in S1 and in the §7 "stale iCore line" row.
- Owner: builder. Verification: re-read S1 and §7.
- Disposition: before merge (before approval). Status: open.

### [P3] Decision 3 asks for an env change that §2 rules out
- Evidence: §2 "No change to … any … env file". Decision 3: "the builder lowers the staging caps in
  `infra/host/env/staging.env` by at least 256 MiB (an env change, in the M1 PRs)". It does not say
  which caps.
- Suggested correction: in §2, except this conditional change, made in its own PR with the Compose
  config tests. Say to keep `SKIW_MEM_CLAMAV` (1280m), because ClamAV needs that memory to load its
  signatures [A]; take the 256 MiB from `web` or `db`.

### [P3] The deploy peak is above the RAM rule
- Evidence: decision 3 leaves `migrate` out of the sum, because it is "a one-off run at deploy". D16
  runs `migrate` before the switch, while the old `web` and `worker` still run. During a deploy the
  production caps sum to 8192 MiB, above the 7168 MiB of the rule.
- Effect: small. These numbers are caps, not memory in use. G-LOAD does not run during a deploy.
- Suggested correction: one sentence saying that the deploy peak is allowed because the numbers are
  caps, and that M1k measures the real peak during one staging and one production deploy.

### Required before approval
- The P2 item.

## Round 1 — 2026-10-25 · scope: slice (vendor amendment v1.0)

- **Spec review:** `docs/specs/2026-10-25-hostinger-vps-vendor.md` · version 1.0 · hash
  `2c1e7134191e0f5955255f3337f4145d6cebda28` (working file, untracked in the main checkout).
- **Amends:** v1.19, hash `75ac19f61466445c35e4ff9341a0d0984a55249f` (unchanged; = the hash in
  the amendment header). `main` = `origin/main` = `550b622` (PR 65 merged).
- **Mode:** read only; no file written except this one.
- **Model used:** Claude Opus 5.5. **Switch model next step?** No.

**Verdict:** Revision required

The direction is sound and is the owner's decision: Hostinger for both hosts, in Malaysia, on
Ubuntu 24.04, with no design change and no real data before the H12 gates. The P2 items below are
about facts the spec states wrongly or leaves open, and about tests that cannot pass as written.

### Facts I checked (2026-10-25)
| Fact | Source | Found |
|---|---|---|
| Malaysia is a Hostinger VPS location | https://www.hostinger.com/support/1583267-where-are-your-servers-located (modified 2026-09-15) | yes, "Asia: India, Indonesia, and Malaysia" under VPS (KVM). **No city is named.** Kuala Lumpur comes only from a Hostinger blog post |
| KVM 1 | https://www.hostinger.com/vps-hosting and https://www.hostinger.com/vps/servers/malaysia | 1 vCPU, 4 GB RAM, 50 GB NVMe; US$6.49/mo promo, renews at US$11.99/mo for 2 years |
| KVM 2 | same | 2 vCPU, 8 GB RAM, 100 GB NVMe; US$8.79/mo promo (the owner's 2026-10-13 record says 8.99), renews at US$14.99/mo for 2 years |
| Payment | same | "All plans are paid upfront. The monthly rate reflects the total plan price divided by the number of months" |
| Backups | same | "Free weekly backups"; "automatic weekly backups. Restore your VPS from your dashboard". On by default, location and retention: not stated |
| IP | /vps-hosting FAQ | "every KVM VPS client gets a dedicated IP address" (static across rebuild: not stated) |
| OS, 2FA, CPU sharing | same | "Ubuntu" without a version; 2FA not stated; "dedicated resources, such as CPU power" in an FAQ, cores not said to be dedicated |
| Debian 12 regular security support | https://www.debian.org/News/2026/20260712 | ended and handed to LTS (announcement dated 2026-07-12); LTS to 2028-06-30 |
| Owner's price record | `docs/DECISIONS.md` 2026-10-13 M1a entry, "Owner answer (2026-10-13, option 1)" | matches the spec's quote |

### Findings

No P0 or P1.

### [P2] The spec says "Kuala Lumpur" as a verified fact and as a purchase gate; Hostinger names only "Malaysia"
- Category: spec mismatch (unsupported [V]; ambiguity)
- Rule: reviewer §4 "invented values"; D19
- Evidence: decision 2 "[V: …1583267-where-are-your-servers-located]" for "Malaysia (Kuala Lumpur)";
  §5 failure path "if Kuala Lumpur is not offered … No other location is accepted"; S3 done when "The
  order page shows Kuala Lumpur". The cited page names the country only.
- Failure scenario: the order page shows "Malaysia". One reader buys; another reader refuses, because
  the spec needs "Kuala Lumpur".
- Why it matters: D19 needs Malaysia. The city matters only for the written record.
- Required correction: decision 2 cites the page for "Malaysia" and the blog (with its date) for the
  city as [A]. The purchase rule and S3 say "a Malaysian location"; G-VENDOR item 1 confirms the city
  and site in writing.
- Owner: builder. Verification: re-read decision 2, §5, S3, item 1.
- Disposition: before merge (before approval). Status: open.

### [P2] Hostinger includes automatic weekly backups; the spec treats provider backups as opt-in
- Category: material risk (D19, H4, H6)
- Rule: D19; spec H4 (keys only on the host and in escrow), H6 (copies and their location)
- Evidence: decision 9 "used only if G-VENDOR item 3 shows a stated Malaysian location …". Hostinger
  sells "Free weekly backups … automatic weekly backups" on every plan. The pages do not say whether
  they are on by default, where they sit, or how long they are kept.
- Failure scenario: the backups run by default. Hostinger then holds a whole-disk copy: the database,
  the files and `/etc/skiw/secrets` (every key in clear). The copy may sit outside Malaysia, and it may
  keep old keys after a rotation. Nothing in the spec turns it off.
- Why it matters: this copy is outside D19 (location), H4 (keys) and the rotation and deletion rules.
  "Used only if" does not stop a copy that the vendor makes by itself.
- Required correction: a rule that the owner turns automatic backups and snapshots **off** at purchase
  if Hostinger allows it, and records that. G-VENDOR item 3 asks: on by default? can it be turned off?
  location, retention and deletion? If it cannot be turned off and the copy is not confirmed in
  Malaysia, the answer is blocking. Add a threat row.
- Owner: builder (text); owner (the setting at purchase). Verification: re-read decision 9, item 3, §7.
- Disposition: before merge (before approval). Status: open.

### [P2] The plan rule is unclear, and the CPU count halves without a word
- Category: ambiguity; material risk
- Rule: reviewer §4 "testable controls"; spec G-LOAD
- Evidence: decision 3 "the builder checks the sum of the `SKIW_MEM_*` limits against the chosen RAM;
  a plan below that sum is not bought" and "Keeps the tested sizing". Today the sums are: production
  256+1536+1024+1536+2048+1536+256 = **8192 MiB** (migrate included); staging **3968 MiB**. The vCPU
  count is called "not recorded [A]", but Hostinger lists it: KVM 2 has **2** vCPU (iCore NODE2: 4
  cores), KVM 1 has **1** vCPU (NODE1: 2 cores).
- Failure scenario: production's sum equals 8 GiB with no room for the OS. A guest with "8 GB"
  usually sees less than 8192 MiB. One reader says KVM 2 fails the rule, so no plan fits. Another
  reader says it passes. Production also gets half the CPU of the sizing the spec assumed.
- Required correction: state the rule with numbers, for example "the sum without `migrate` is at most
  the plan's RAM minus 1 GiB for the host", or drop the rule and say that G-LOAD decides. Record the
  vCPU and disk of both plans with the source and date. Say that G-LOAD on the production plan (which
  includes the 1 s p95 job-delivery bound) is the CPU test. Add to Q43 the facts the owner needs:
  2 vCPU vs 4 before, and KVM 4 as the fallback if G-LOAD fails.
- Owner: builder. Verification: re-read decision 3 and Q43.
- Disposition: before merge (before approval). Status: open.

### [P2] The change list misses iCore lines, and the cost table has no new values
- Category: consistency
- Rule: reviewer §4 "consistency"; the amendment's own "It changes nothing else"
- Evidence: decision 10 lists the places to change. `grep -i icore` in v1.19 also finds **T24**
  (line 592: "outside the iCore account", "iCore portal 2FA"), **H2** (line 721: "iCore page does not
  say that the IPv4 is static"; decision 10 names H5, which has no iCore text), **H6** (line 944
  off-site (a) "a second small iCore VPS (NODE1 RM 39.90"; line 960 "that iCore offers them") and the
  §10 control-table heading (line 1128 "v1.14 iCore VPS"). For §8.2 the spec gives no new rows: no
  plan price, no total (line 638 "RM 99.80–139.70"), no footnote sum (641), no stopgap plans (647).
- Failure scenario: the S1 builder either edits places the approval does not cover, or leaves them
  stale. For §8.2 the builder must invent prices and totals.
- Required correction: add T24, H2, H6 (both lines) and the heading to decision 10, or say they stay
  as history. Give the new §8.2 text: the plan rows as "KVM 2 / KVM 1, open (Q43)" with the dated list
  prices in USD and the paid-upfront term, the total as a range or "open until Q43 and Q44", and the
  stopgap as "a larger Hostinger plan (KVM 4 or KVM 8), price open".
- Owner: builder. Verification: re-run the grep against decision 10.
- Disposition: before merge (before approval). Status: open.

### [P2] The S1 "done when" test cannot pass
- Category: untestable milestone
- Rule: reviewer §4 "each milestone has a testable done when"
- Evidence: S1 done when "`git grep -i icore` finds only the history lines listed in section 7"; §7
  lists only the DECISIONS 2026-10-12 and 2026-10-13 entries, the hosting paper and this document. But
  `agents/PROJECT.md` names iCore and changes only in S2 (`setup`). The main spec's changelog (line 5:
  the v1.14 entry, "go with icore") is history and stays. The Q1 answer (line 1216) is history.
- Failure scenario: the S1 PR fails its own test, or the builder rewrites history to pass it. Decision
  10 forbids that ("Editing history entries" rejected).
- Required correction: list the allowed hits: the changelog entries of v1.14 to v1.19, answered-Q
  history, the hosting paper, this document, the DECISIONS history entries, and `agents/PROJECT.md`
  until S2. Then S2 done when adds: no iCore in PROJECT.md except history.
- Owner: builder. Verification: re-read S1, S2 and §7.
- Disposition: before merge (before approval). Status: open.

### [P3] Prices and the term: update to today's page
- Evidence: decision 3 quotes US$8.99 (2026-10-13); the page today shows US$8.79 promo, US$14.99
  renewal, and KVM 1 at US$6.49 / US$11.99. "All plans are paid upfront."
- Suggested correction: cite the page with today's date. In Q44, state the upfront sum for 24 months,
  roughly US$211 (KVM 2) and US$156 (KVM 1) before tax, as list prices that may change.

### [P3] The Debian 12 line
- Evidence: decision 5 "support ended 2026-07-11 for regular updates". Debian's announcement is dated
  2026-07-12, and LTS continues to 2028-06-30.
- Suggested correction: "regular security support ended July 2026 (debian.org news 2026-07-12); LTS
  to 2028-06-30". This does not change the choice.

### [P3] The UNI-11 record should list the owner's own data sent to Hostinger
- Evidence: §1 "Hostinger is a new service that holds all data". The account also gets the owner's
  name, contact and payment details, and the control panel is run by a foreign group [A].
- Suggested correction: the S1 DECISIONS entry lists both: all project data on the disks (in Malaysia,
  gated by G-VENDOR), and the owner's own account data (PDPA rule (a) of 2026-10-24 applies, as for
  UptimeRobot).

### What holds
- Non-goals: true. `git grep -l -i icore` finds only docs: `agents/PROJECT.md`, DECISIONS, the M1 plan,
  five runbooks (deploy, incident-pdpa-breach, local-dev, restore, rollback), the main spec and the
  hosting paper. No code, env file or test names the vendor.
- Gates: no real data before the five H12 gates; G-VENDOR keeps eleven items. The new questions on
  the contracting entity, its governing law and access from outside Malaysia are right. A "yes" to
  access from outside Malaysia is blocking until a D19 basis exists.
- The PROJECT §9 rule (a new external service needs a reviewed spec change first) is met by this
  amendment, after it is approved.
- Q43 and Q44 are free numbers (the last is Q42).
- Decision 7 (two accounts if item 11 allows) and decision 8 (Q36 stays open; T24 residual grows) are
  honest about the risk.

### Required before approval
- The five P2 items.
