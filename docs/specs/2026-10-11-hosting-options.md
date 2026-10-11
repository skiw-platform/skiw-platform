# SKIW Platform — hosting options (decision paper)

- Date: 2026-10-11 · Author: Builder (deep tier) · Status: draft
- Version: 1.5 · This paper changes no spec text, so no spec hash moves. The review pins this paper's own
  git hash (v1.0 was `40ab593a`, v1.1 was `c80a1899`, v1.2 was `667150a6`, v1.3 was `9670b835`,
  v1.4 was `8d0906e5`).
- Supersedes: nothing. Input to a possible spec change of `docs/specs/2026-10-05-skiw-platform-stack-design.md`
  (v1.13, hash `e3141585`) sections D3, D4, D12–D15, D17, D19, D23, D24, §8.2, §8.3, M1, M6.
- Audience: the Reviewer ("Bob"), then the owner. The owner has **not** chosen a platform.

## How to read this

- The owner asked (2026-10-11): AWS Step 1 (§8.2, ≈ US$245/month) costs too much; what about a VPS
  (DigitalOcean) or a Vercel-like platform with deployment automation and security?
- §3 lists the options, §3.2 the prices, §4 what leaves Malaysia, §7 what security changes, §9 what a
  spec change would contain, §3.4 the builder's recommendation. Nothing here is decided.
- Tags: **[V Fn]** = verified on the official page in row Fn of "Facts checked" (URL and date there).
  **[A]** = assumption, not verified; must be checked before it is relied on. **[O]** = needs the owner.
- This paper is not legal advice. §4 is a checklist of what the owner must decide and record.
- Prices are list prices in USD per month, 730 h, excluding AI tokens, tax and Google Workspace.
  RM uses **4.10** (BNM selling rate 4.096 on 2026-10-09 [V F29], rounded). The spec uses 4.25 [A];
  at 4.25 every RM figure is about 3.7 % higher.

## Changes from 1.4

Owner backup input (2026-10-11) on v1.4 hash `8d0906e5`: HA is not critical if a database backup exists; a
short downtime with manual recovery is acceptable. Two proposed backup mechanisms: a scheduled export to a cloud
store such as Google Drive (**Option G**), and a dump to the VPS's own disk, downloadable on demand
(**Option L**).
1. §1 quotes both inputs and records the reading: downtime and manual restore accepted; Q10 answered in
   practice (confirm in the adopting spec); RTO "hours, manual", no numbers.
2. New §3.5 "Backup design for the owner's proposal": dump role and RLS, RPO, restore drill, encryption,
   credential, integrity, retention, ransomware, Drive quotas, readers, PDPA/D19, Malaysia-resident alternatives,
   Option L, a G / L / L + pull table, and the builder's backup recommendation.
3. §3.4: a paragraph on what the inputs change (no ranking change). §4: checklist item 9. §9 S1: backup role.
   §10: Q3 and Q10 updated, new Q11. F36 adds the Render disk price. New rows F45–F48.

## Changes from 1.3

Owner input (2026-10-11) on v1.3 hash `9670b835`: a DB standby (HA) is not needed in v1; it can come later.
1. §1 records the input and how it is read. §10 Q3 is partly answered; Q7 is answered; new Q10 asks whether
   "HA later" also covers one web instance.
2. §3.2 compares v1 on the no-standby totals. The standby figures stay, labelled "later upgrade, not v1", with
   the cost to add HA later per option. A (§8.2 Step 1) is already a single-AZ DB.
3. §3.4 re-runs the recommendation on the no-standby totals. Same two options; the reasons change.
4. PDPA position unchanged. New rows F42–F44.

## Changes from 1.2

Owner request (2026-10-11) on v1.2 hash `667150a6`: add a lean VPS comparison next to AWS and lean Render.
1. New variants: **B2** (one DO Droplet with managed Postgres), **B3** (B2 with Postgres on the same VPS) and
   **B4** (a Malaysian VPS, iCore Technology, Postgres on the VPS). Azure Malaysia West is priced as a B4
   alternative. Rows in §3.1; the compact table in §3.2 now reads A, A2, D2, B2, B3, B4, with a cheapest-first
   ranking; notes in §3.3, §3.4, §7, §9; open question 9 (§10). New rows F40–F41.
2. Correction: F16 said the old Render instance gets "30 s grace (up to 300 s)". It now matches F37: `SIGTERM`
   60 s after traffic switches, then `SIGKILL` after the shutdown delay (default 30 s, max 300 s).

## Changes from 1.1

Owner request (2026-10-11) on v1.1 hash `c80a1899`: add a lean Render setup, **D2**, to read side by side
with AWS. D2 is one web instance, one worker and one Postgres node in Render Singapore on a Pro workspace,
with Spaces for files and no staging at first. New: option row D2 (§3.1), a second cost table "AWS vs lean
Render" under the main table (§3.2), notes in §3.3, §3.4, §7, §9, open question 8 (§10), and rows F35–F39.
Nothing else changed.

## Changes from 1.0

Fixes review Round 1 (2026-10-11) on v1.0 hash `40ab593a`:

1. **[P1] DO HA price.** DigitalOcean (DO) stops selling standby nodes on new Standard Edition clusters
   (15 Oct 2026 for accounts that never made a PostgreSQL/MySQL cluster, 30 Nov 2026 for all) [V F30].
   HA then needs Advanced Edition, from US$130 per node [V F31]. B and C are re-costed with and without
   a standby (§3.2); the shortlist and decision tree change (§3.4). New rows F30–F32.
2. **[P2] PDPA wording.** §4 checklist, the decision tree and Q1 now follow JPDP Guideline 3/2025 [V F33]:
   the adviser names the section 129 condition and its evidence; a TIA supports a s129(2) finding and is not
   a basis on its own; a transfer notice to data subjects is required and recorded.
3. **[P2] A2 scope.** New §7.1 lists each A2 cut as retained / replaced / removed, with its residual risk.
   §9 adds D15, §8.3, T13, T18, M6 and UNI-16 runbooks to the A2 change scope. NAT alternatives are
   separated; the Savings Plan is marked provisional. New open questions 6–7.
4. Optional note: the fact-count line below states the exact counts; the header explains the hash.

## Facts checked

All rows checked 2026-10-11 unless stated. The table has **48 rows (F1–F48)**. The paper cites them in
**187 verified-fact tags** (183 in §§1–10, 4 in the sections above; a tag may cite more than one row). v1.4 had
44 rows and 157 tags; v1.3 had
41 rows and 129 tags; v1.2 had 39 rows and 103 tags; v1.1 had 34 rows and 81 tags. The v1.0 PR text said "37 verified fact tags"; v1.0 actually had 29 rows and 64 tags.

| # | Fact | Value | Source URL |
|---|---|---|---|
| F1 | DigitalOcean (DO) regions | 16 regions; **no Malaysia**; SGP1 (Singapore) has Droplets, Managed PostgreSQL, App Platform, Load Balancers, Container Registry, Spaces | https://docs.digitalocean.com/platform/regional-availability/ |
| F2 | DO Basic Droplets | 2 GB/1 vCPU $12; 4 GB/2 vCPU **$24**; 8 GB/4 vCPU $48; backups 20 % (weekly) or 30 % (daily) of Droplet price | https://www.digitalocean.com/pricing/droplets |
| F3 | DO Managed PostgreSQL price | 1 GiB single node **$15.15**; 2 GiB $30.45; 4 GiB $60.90; extra storage $0.215/GiB | https://www.digitalocean.com/pricing/managed-databases |
| F4 | DO PostgreSQL HA pricing (Standard Edition) | Docs: single node "begin at $15.00"; HA = 2 GiB primary $30 + matching standby $30. **Only for clusters created before the F30 cutoff** | https://docs.digitalocean.com/products/databases/postgresql/details/pricing/ |
| F5 | DO PostgreSQL limits | Users "cannot access the `superuser` role"; PITR "limited to the last 7 days"; daily full backups + WAL; automated failover with a standby; LUKS at rest; 22 connections on 1 GiB | https://docs.digitalocean.com/products/databases/postgresql/details/limits/ and …/details/features/ |
| F6 | DO `pgcrypto` | Supported on PostgreSQL 14–18, including 17 | https://docs.digitalocean.com/products/databases/postgresql/details/supported-extensions/ |
| F7 | DO DB trusted sources | Allow-list by Droplet, App, tag, IP/CIDR; ≤ 100 rules; TLS required (`sslmode=require`, `verify-full` recommended) | https://docs.digitalocean.com/products/databases/postgresql/how-to/secure/ |
| F8 | DO App Platform prices | Shared 1 vCPU: 0.5 GB $5, 1 GB $12, 2 GB $25; 2 vCPU/4 GB $50; dedicated from $29; dedicated egress IP "up to $25"/month; jobs billed while running | https://docs.digitalocean.com/products/app-platform/details/pricing/ |
| F9 | DO App Platform components | Workers are long-running, non-routable services; jobs can run "Before every deploy" (failure behaviour not stated) | https://docs.digitalocean.com/products/app-platform/how-to/manage-workers/ and …/manage-jobs/ |
| F10 | DO App Platform request timeout | 100 s hard limit — **community answers only**, not in the limits page | https://www.digitalocean.com/community/questions/how-to-resolve-the-100s-request-timeout-of-digital-ocean-s-app-is-there-a-way-to-increase-the-timeout-or-something-else |
| F11 | DO Spaces, Registry, LB | Spaces $5 (250 GiB, 1 TiB transfer); Registry Basic $5, Professional $20 (no scanning mentioned); Load Balancer from $12 | https://www.digitalocean.com/pricing/spaces-object-storage, …/pricing/container-registry, …/pricing/load-balancers |
| F12 | DO OIDC for GitHub Actions | Not offered for the DO API; open feature request; `doctl` needs an API token | https://ideas.digitalocean.com/security/p/support-oidc-openid-connect, https://docs.digitalocean.com/reference/doctl/reference/auth/ |
| F13 | Render regions | Oregon, Ohio, Virginia, Frankfurt, **Singapore**; no Malaysia | https://render.com/docs/regions |
| F14 | Render prices | Workspace Hobby $0, **Pro $25**, Scale $499 + compute; services 512 MB $7, 1 CPU/2 GB $25, 2 CPU/4 GB $85; Postgres 1 GB $19, 1 CPU/2 GB $40, 1 CPU/4 GB $55; storage $0.30/GB; dedicated IPs $100 per IP set (Pro); PITR 3 days (Hobby) / 7 days (Pro+); "Firewall & DDoS mitigation" listed from Hobby | https://render.com/pricing |
| F15 | Render Postgres HA | Needs ≥ 1 CPU plan and PostgreSQL ≥ 13; standby billed like the primary; failover "a few seconds" | https://render.com/docs/postgresql-high-availability |
| F16 | Render deploys | Pre-deploy command runs after build, before deploy; on failure the deploy is cancelled; zero-downtime deploys; the old instance gets `SIGTERM` 60 s after traffic switches, then `SIGKILL` after the shutdown delay (default 30 s, max 300 s) (as F37; corrected in v1.3) | https://render.com/docs/deploys |
| F17 | Render Postgres features | `pgcrypto` on PostgreSQL ≥ 13; PITR restores into a **new** instance; logical backups kept 7 days; internal (private network) URL and IP allow list; AES-256 at rest | https://render.com/docs/postgresql-extensions, https://render.com/docs/postgresql-backups, https://render.com/docs/postgresql-creating-connecting |
| F18 | Render request timeout | 100 min — **community forum only** | https://community.render.com/t/need-to-increase-requests-timeout-of-5-minutes/4001 |
| F19 | Vercel Functions | Max duration Hobby 300 s; Pro/Enterprise **800 s**, **1800 s** extended (Beta); default region **`iad1`**; body ≤ 4.5 MB | https://vercel.com/docs/functions/limitations |
| F20 | Vercel regions | 19 compute regions incl. `sin1`; no Malaysia; on regional outage traffic is rerouted to the next region | https://vercel.com/docs/regions |
| F21 | Fly.io | 17 regions incl. `sin` (Managed Postgres ✓); no Malaysia; Managed Postgres from $38/month, HA on all plans, storage $0.28/GB | https://docs.fly.io/reference/regions, https://docs.fly.io/mpg |
| F22 | Railway | Regions US West, US East, EU West, Southeast Asia (Singapore); no Malaysia | https://docs.railway.com/reference/deployment-regions |
| F23 | AWS `ap-southeast-5` service list | Lists ECS, ECR, RDS for PostgreSQL, S3, WAF, Secrets Manager, KMS, Backup, X-Ray, CloudWatch Logs, CloudTrail, Bedrock, GuardDuty, Shield, Inspector, ELB, **Lightsail** | https://api.regional-table.region-services.aws.a2z.com/index.json (data behind the AWS "Regional services" page) |
| F24 | Lightsail | Malaysia `ap-southeast-5` is a Lightsail region (opt-in); 2 GB $12, 4 GB $24; LB $18; DB 1 GB $15 / HA $30, 2 GB $30 / HA $60; object storage $1/$3/$5; Malaysia gets half the data-transfer allowance | https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html, https://aws.amazon.com/lightsail/pricing/ |
| F25 | Lightsail DB PITR | Point-in-time restore over the previous 7 days | https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-creating-a-database-from-point-in-time-backup.html |
| F26 | Azure Malaysia West | Azure Database for PostgreSQL flexible server listed; zone-redundant HA ✓; geo-redundant backup ✗; backup retention 7 days default, up to 35 | https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/overview |
| F27 | PostgreSQL 17 `CREATEROLE` | A non-superuser with `CREATEROLE` cannot grant `BYPASSRLS`, `SUPERUSER` or `REPLICATION`; a created role is granted back `WITH ADMIN TRUE, SET FALSE, INHERIT FALSE` | https://www.postgresql.org/docs/17/role-attributes.html |
| F28 | Spec D19 / D3 / D24 | D19 (quoted): "primary store, backups, object storage, logs in Malaysia" and each cross-border flow needs "a Transfer Impact Assessment or a s129 exception"; D19 rejected "Stay in Singapore"; D24 already documents a Render Singapore fallback | spec §3 (repo) |
| F29 | USD→MYR | BNM 2026-10-09: buying 4.071, selling 4.096 | https://api.bnm.gov.my/public/exchange-rate/USD |
| F30 | DO database plan changes (announced) | From **15 Oct 2026** for accounts that have never created a PostgreSQL or MySQL cluster, and **30 Nov 2026** for all accounts: new Standard Edition clusters get no plans above 4 GiB and "do not support standby nodes or read-only nodes". From 15 Oct 2026 Advanced Edition adds "Basic - Shared CPU" plans of 8–64 GiB (no price stated). Clusters created before the change applies to the account are exempt and may still add standby nodes | https://docs.digitalocean.com/release-notes/upcoming/dbaas-plan-changes/ |
| F31 | DO PostgreSQL Advanced Edition price | Primary "begin at $130.00 per month for an 8 GiB RAM/2 vCPU primary node"; standby and read-only nodes "bill at the same rate as the primary node"; extra storage $0.115/GiB. The page repeats the F30 cutoffs. No price for the new shared-CPU Advanced plans | https://docs.digitalocean.com/products/databases/postgresql/details/pricing/ |
| F32 | DO Advanced Edition details | PostgreSQL 16, 17, 18; 1-, 2- or 3-node clusters; 99.95 % SLA with a standby, 99.5 % without; "Available regions depend on the CPU option and plan" (SGP1 not stated); the how-to still says "Basic - Shared CPU plans are not available for Advanced Edition" (older than F30) | https://docs.digitalocean.com/products/databases/postgresql/concepts/advanced-edition/, https://docs.digitalocean.com/products/databases/postgresql/how-to/use-advanced-edition-clusters/ |
| F33 | JPDP Guideline 3/2025, Cross Border Personal Data Transfer (issued 29 Apr 2025) | §4.1: s129(2) allows transfer to a place with (a) a substantially similar law or (b) adequate protection. §4.2: s129(3) conditions apply "notwithstanding" s129(2) (consent, contract necessity, legal proceedings, reasonable grounds, all reasonable precautions and due diligence, vital interests). §4.3: the controller "shall through its personal data protection notice or such other written notice inform data subject about the transfer". §§5.3, 6.2: a TIA is conducted "in order to fulfil the requirement under paragraph 129(2)(a)" or "(b)"; findings valid ≤ 3 years. §8.3.3: storage abroad is not "necessary" where local data centres offer it at lower or similar cost. §16.2: keep records proving each transfer meets s129 | https://www.pdp.gov.my/ppdpv1/wp-content/uploads/2025/08/GP_CBPDT_EN.pdf |
| F34 | Spec T13 / T18 / M6 / D15 / §8.3 | T13 (line 580): AWS Backup daily snapshot "to a vault with Vault Lock in a separate AWS account", 35 days; T18 (585): AWS WAF managed core, known-bad-inputs, IP reputation, rate rule 1 000 req/5 min/IP, tested by "WAF rule set in IaC snapshot test"; M6 (667): "Backup vault lock, PITR, alarms, runbooks", done when a timed restore drill ≤ 2 h is recorded; D15 (99): OIDC, ECR scan, auto-deploy to staging, manual approval to production; §8.3 (651): preview-per-PR environment; D3 (87) and §5.2 (506): NAT fixed EIP so TechVision can be asked to allow-list us | `docs/specs/2026-10-05-skiw-platform-stack-design.md` v1.13 (repo) |
| F35 | Render workspace plans, Hobby vs Pro | Hobby $0 "For individuals building personal projects and prototypes"; Pro $25 "For teams deploying production-grade apps and agents". Hobby / Pro: seats 1 / unlimited; services 25 / unlimited; environments 2 per project / unlimited; bandwidth 5 GB / 25 GB, then $0.15/GB; build pipeline 500 / 1 000 min, then $5 per 1 000; PITR 3 / 7 days; log retention 7 / 14 days; horizontal autoscaling — / yes; full-stack previews — / yes (single-service previews on both); dedicated IPs — / $100 per IP set. Both show private networking, high availability, zero-downtime deploys, pre-deploy command, private services and background workers. No clause banning commercial use on Hobby was found; the Free-instance page says Free instances are not for production. Pricing page read from its HTML source (the fetcher shows no table) | https://render.com/pricing, https://render.com/docs/new-workspace-plans, https://render.com/docs/outbound-bandwidth, https://render.com/docs/build-pipeline, https://render.com/docs/postgresql-backups, https://render.com/docs/free |
| F36 | Render compute and Postgres prices | Services and workers: `0.5c-512mb` (old name Starter) $7; `1c-2g` (Standard) $25; `2c-4g` $85. Postgres: `0.5c-1g` $19; `1c-2g` $40; `1c-4g` $55; storage $0.30/GB. Persistent disks $0.25 per GB per month. Plans renamed 26 Aug 2026, "There are no changes to pricing" | https://render.com/pricing (HTML source), https://render.com/docs/compute-plans-update |
| F37 | Render deploy with one instance | The zero-downtime sequence "applies to web services, private services, background workers, and cron jobs"; no instance count is required. The new instance starts, passes the health check, then "begins receiving all incoming traffic". "After 60 seconds" the old instance gets `SIGTERM`; `SIGKILL` after the shutdown delay (default 30 s, max 300 s). A persistent disk disables zero-downtime deploys. Whether open requests on the old instance finish is not stated | https://render.com/docs/deploys |
| F38 | Render scaling, private network, private services | Manual scaling (fixed instance count) "is available for all Render workspaces"; autoscaling Pro and higher. Services in one region share a private network; Pro or higher can block cross-environment traffic. Private services "aren't reachable via the public internet" and must bind a port. No sidecar or multi-container service is described | https://render.com/docs/scaling, https://render.com/docs/private-network, https://render.com/docs/private-services |
| F39 | Render object storage | The pricing page lists no object storage product. The docs offer MinIO, run by us as a paid web service with objects "on a 10 GB persistent disk" | https://render.com/pricing (HTML source), https://render.com/docs/deploy-minio |
| F40 | Azure Malaysia West list prices (pay-as-you-go, Linux, per hour unless stated; × 730 h) | VM `Standard_B2as_v2` (2 vCPU, 8 GiB) $0.0855; `B2als_v2` (2 vCPU, 4 GiB) $0.0428. Standard SSD disk E6 $4.80/month. Standard static public IPv4 $0.005. Blob Hot LRS $0.018/GB-month. PostgreSQL flexible server: Burstable B1ms (1 vCore, 2 GiB) $0.0234; General Purpose $0.1098 per vCore; storage $0.1242/GB-month; storage 32 GiB minimum; backup retention 7–35 days. Burstable is "Not recommended for production workloads". Location field "MY West". Region with PostgreSQL flexible server: F26 | https://prices.azure.com/api/retail/prices (Microsoft retail price API, `armRegionName eq 'malaysiawest'`), https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/basv2-series, https://learn.microsoft.com/en-us/azure/postgresql/compute-storage/concepts-compute |
| F41 | iCore Technology Sdn. Bhd. (Malaysian VPS host) | NVMe Linux VPS: NODE1 4 GB / 2 cores RM 39.90; NODE2 8 GB / 4 cores RM 59.90; NODE3 16 GB / 6 cores RM 119.90 per month; NVMe "From 50 GiB - 2 TiB"; unlimited data transfer; no contract. "All our servers are located at" CJ1 Data Center, Cyberjaya and AIMS Data Center, Kuala Lumpur (both "Tier III certified"). No managed PostgreSQL, object storage or API is listed; backup service price not shown | https://www.icore.com.my/nvme-vps |
| F42 | DO: adding a standby later | Clusters created before the F30 restrictions apply to the account "are not affected": "You can continue to resize, fork, and restore these clusters from backups, including onto plans that are otherwise unavailable for new clusters, and add standby and read-only nodes." Neither the plan-change note nor the Advanced Edition how-to describes converting a Standard cluster to Advanced Edition; the how-to shows standby choices at cluster creation | https://docs.digitalocean.com/release-notes/upcoming/dbaas-plan-changes/, https://docs.digitalocean.com/products/databases/postgresql/how-to/use-advanced-edition-clusters/ |
| F43 | Render: enabling HA later | "You can enable High Availability (HA) for any Render Postgres database with the required specs" (≥ 1 CPU, PostgreSQL ≥ 13). "Enabling HA requires a database restart. Your database will be unavailable temporarily (usually for less than five minutes)." Standby has the same plan and storage as the primary "and is billed accordingly" | https://render.com/docs/postgresql-high-availability |
| F44 | AWS RDS: Multi-AZ later | "You can use the console to convert existing DB instances to Multi-AZ DB instance deployments by modifying the DB instance and specifying the Multi-AZ option" (also `modify-db-instance`) | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZSingleStandby.html |
| F45 | Google Drive limits for uploads by a job | "Service accounts don't have storage quota and can't own files. Instead, they must upload files and folders into shared drives, or use OAuth 2.0 to upload items on behalf of a human user." Files in shared drives "belong to the organization". A shared drive holds at most 500 000 items. "Each user can upload and copy 750 GB to Drive within 24 hours"; files up to 5 TB. Drive API: 1 000 000 quota units per minute per project, 325 000 per user per project | https://developers.google.com/workspace/drive/api/guides/about-shareddrives, https://support.google.com/a/answer/7338880, https://developers.google.com/workspace/drive/api/guides/limits, https://knowledge.workspace.google.com/admin/drive/storage-and-upload-limits-for-google-workspace |
| F46 | Google Workspace storage and data location | Pooled storage: Business Starter "30 GB times the number of End Users", Business Standard 2 TB, Business Plus 5 TB per user; content in shared drives counts toward the pool. Data regions for data at rest: "United States, European Union … or No preference" (no Malaysia or Asia option); supported on Business Standard and Plus, Enterprise and some other editions, not Business Starter; with "No preference" Google stores covered data without a location restriction | https://knowledge.workspace.google.com/admin/storage/google-workspace-storage-faq-for-admins, https://knowledge.workspace.google.com/admin/compliance/choose-a-geographic-location-for-your-data |
| F47 | AWS RDS point-in-time restore | "RDS uploads transaction logs for DB instances to Amazon S3 every five minutes." You can restore "to any point in time within your backup retention period"; a restore creates a new DB instance | https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_PIT.html |
| F48 | PostgreSQL 17 `pg_dump` and row security | "By default, pg_dump will set row_security to off, to ensure that all data is dumped from the table. If the user does not have sufficient privileges to bypass row security, then an error is thrown." Superusers and `BYPASSRLS` roles always bypass RLS; table owners bypass it unless the table has `FORCE ROW LEVEL SECURITY`. `-Fc` custom format is "compressed by default" and restores with `pg_restore` | https://www.postgresql.org/docs/17/app-pgdump.html, https://www.postgresql.org/docs/17/ddl-rowsecurity.html |

## 1. Goal

Give the Reviewer and the owner one honest comparison of where SKIW can run for less than §8.2 Step 1,
with verified prices, the PDPA effect, the security controls each option keeps or loses, and the spec
work each option needs, so the owner can choose (or keep AWS) before any spec change is written.

**Owner input (2026-10-11), quoted:** "the HA option is still ok as this is not a huge application, it is being
used by a small internal team of 5 people, so HA can be the afterthought."

How this paper reads it, and no further:
- **Accepted:** no database standby (no HA) in v1. HA becomes a later upgrade. The v1 comparison (§3.2, §3.4)
  therefore uses the no-standby totals.
- **Still required** unless the owner says otherwise: backups, PITR where the option has it, and a timed,
  recorded restore test (UNI-16, T13).
- **Not answered:** whether this also accepts **one web instance**. The spec asks for min 2 web tasks for
  no-downtime deploys (D3, D15, §8.3). That stays an open question (Q10). Also open: the RTO and RPO numbers,
  and how long a failed node may stay down (Q3).

**Owner input 2 (2026-10-11), quoted:** "as long as there is a backup of the database, the criticalness of the
High Availability is still ok. if happen that something is down, it is still fine to look into it and bring it
back online later on. so a short downtime still bearable. have a thought that it will have a cron job to export
the database out to a cloud storage provider like google drive or something is fine."

How this paper reads it, and no further:
- **(a) Downtime.** A short downtime and a manual recovery ("look into it and bring it back online later on")
  are acceptable in v1. In practice this answers Q10: one web instance is acceptable. Status: *owner words imply
  yes; confirm in the adopting spec.* For Q3, the words support "RTO in hours, manual recovery, no on-call
  rota". They give no RTO number and no RPO number; both stay open.
- **(b) Backup mechanism.** The owner proposes a scheduled job that exports the database to a cloud storage
  provider, for example Google Drive. §3.5 sets out what that design needs. A database backup is still
  required (as in the first input).

**Owner input 3 (2026-10-11), quoted:** "or i would say export it to the VPS's own file system that can easily
be downloaded when needed even if the DB is not accessible, the exported DB file can still have all the data
safely". This paper reads it as a second proposed mechanism: a scheduled dump to the host's own disk,
downloadable on demand (Option L, §3.5). The Drive export is Option G.

## 2. Non-goals

- No spec change, no code, no infra. This paper only informs an owner decision.
- No legal conclusion on PDPA. The owner records the decision with a PDPA adviser (§4).
- No change to the host-agnostic design: D1–D2, D5–D11, D16, D18, D25, D26, RLS and the tenant guard
  stay as they are. Only where things run changes.
- No Kubernetes, no multi-region (spec §2 non-goals still apply).

## 3. Decisions

### 3.1 Options

| # | Option | What it is | Why / rejected |
|---|---|---|---|
| A | AWS `ap-southeast-5`, as §8.2 | ECS Fargate, RDS, ALB+WAF, NAT+EIP, KMS, Secrets Manager, Backup vault in a 2nd account, X-Ray | All data in Malaysia; every spec control as written. ≈ US$245 [A: §8.2 uses Singapore-like prices ±25 %]. Kept as the baseline. |
| A2 | AWS `ap-southeast-5`, trimmed | Same CDK design. Cut: WAF (rate limits stay in app), managed NAT gateway (replaced by a NAT instance, which keeps a fixed IP, or by public-subnet tasks, which lose it), X-Ray, PR previews, 2nd-account locked Backup vault (RDS PITR stays); staging stopped out of hours; Fargate Savings Plan (provisional [A]) | Keeps in-country data, IAM roles, OIDC deploys, KMS, Secrets Manager, Bedrock via task role, WIF for Drive (D13). Loses WAF managed rules, locked vault copy, traces, PR previews, managed NAT. Each cut and its residual risk: §7.1. **Shortlisted.** |
| A3 | AWS Lightsail in Malaysia | Lightsail VMs + Lightsail LB + Lightsail managed DB + bucket, same AWS account | In country [V F24], but VM ops like B, and Lightsail DB availability in Malaysia and its role privileges are **not verified** [A]. Hold until verified. |
| B | DO Droplets + Managed PostgreSQL + Spaces (SGP1) | 2–3 Droplets running Docker Compose behind a DO Load Balancer (or Caddy), Managed PG (standby only on Advanced Edition after the F30 cutoff), Spaces | Cheapest at the low end, but **we operate the servers** (OS patches, Docker, TLS, log shipping), no OIDC (API token, F12), no in-country data, single datacentre [A]. Not shortlisted unless the owner names an operator. |
| B2 | DO VPS, lean (SGP1) | **One** 8 GB / 4 vCPU Droplet running web, worker, ClamAV and Caddy under Docker Compose; weekly Droplet backups; Managed PG 2 GiB single node (Standard Edition); Spaces | Variant of B. ≈ US$93 without staging (§3.2). One server is a single point of failure; we patch it; no OIDC [V F12]; data in Singapore. Single-node Standard Edition stays on sale after the F30 cutoffs [V F30]. Builder's estimate. |
| B3 | B2 with Postgres on the same VPS | As B2, but Postgres runs in a container on the Droplet | ≈ US$63 (§3.2). Saves US$30.45 a month; we run backups, WAL archiving, PITR, restore tests and DB patching ourselves; app and DB share one failure domain. |
| B4 | Malaysian VPS (iCore Technology) | One 8 GB / 4-core NVMe VPS in Cyberjaya or Kuala Lumpur [V F41], set up as B3; off-site backups to Azure Blob Malaysia West [V F40] | ≈ US$16 (RM 67) (§3.2). Data in Malaysia per the provider's page [V F41]; this is not a PDPA finding. No managed DB, object storage or API listed [V F41]; support, backups and security practice not verified [A]. Azure Malaysia West VM is the priced alternative (§3.2). |
| C | DO App Platform + Managed PostgreSQL + Spaces (SGP1) | Containers for `web` (2) and `worker` (1), pre-deploy job `migrate`, Managed PG, Spaces | Managed containers, workers and pre-deploy jobs exist [V F9]; one vendor, one region, object storage included. Data in Singapore. A DB standby now needs Advanced Edition (≈ US$260 for 2 nodes [V F31]). **Shortlisted without a standby** if the PDPA step is accepted (§3.4). |
| D | Render (Singapore) | Web services, background worker, pre-deploy command, Render Postgres; object storage elsewhere | Pre-deploy failure cancels the deploy [V F16]; good deploy model. No object storage of its own; dearer than C at equal sizing (§3.2); dedicated IP $100 [V F14]. Already the D24 fallback. Cheaper than C when a DB standby is added (a later upgrade, not v1; §3.2). |
| D2 | Render (Singapore), lean | Variant of D: Pro workspace, **one** web service `1c-2g`, one worker `1c-2g` (ClamAV inside), one Postgres `1c-2g` with no standby, Spaces SGP1 for files, no staging at first, no dedicated IP | Same platform, deploy model and PDPA step as D. Priced on Pro, not Hobby: Hobby has 3-day PITR, one seat and 7-day logs [V F35]. One web instance breaks "min 2 web tasks" (§8.2, §8.3): deploys stay zero-downtime [V F37], but a crash of that instance stops the service until it restarts [A]. ≈ US$135 without staging (§3.2). Builder's estimate; the owner can change it. |
| E | Vercel | Serverless functions + CDN | **Rejected.** No persistent worker process for Procrastinate (D5); functions end at 300/800 s [V F19]; default region `iad1`, no Malaysia [V F19, F20]; outage rerouting moves compute to other regions [V F20]; no managed Postgres of its own; the Django ASGI long-poll (D26) and ClamAV do not fit the function model. |
| F | Fly.io (`sin`) | Machines + Managed Postgres | Singapore, managed PG with HA [V F21]. Compute prices and role privileges not verified [A]. Same PDPA step as C. Not costed. |
| G | Railway (Singapore) | Services + Postgres | Singapore region [V F22]; database features (PITR, HA, roles) not verified [A]. Not costed. |
| H | Malaysia-region cloud other than AWS | Azure Malaysia West + Azure Database for PostgreSQL flexible server | In country, zone-redundant HA [V F26]. Not costed; the whole CDK/IAM/Bedrock/WIF design would be rewritten. No Malaysian-owned provider with a verifiable Malaysian region **and** managed PostgreSQL was verified. |
| — | Single VPS, everything on one host | One Droplet with app, worker and self-run Postgres | **Rejected.** About US$35–50 [A], but breaks "min 2 web tasks" (§8.3), has no managed PITR, and one host failure loses service and possibly data. |

### 3.2 Prices for Step 1 (USD/month, list prices)

Workload: 2 web + 1 worker (with ClamAV, needs ~2 GB [A]) + Postgres + staging + storage + backups + LB +
monitoring. **Low** = single DB node and minimum sizes. **High** = DB standby, larger web, extras named.
For B and C the high case is split: **no standby** (Standard Edition, the only DO price that stays below
US$200) and **HA** (Advanced Edition, the only DO standby a new cluster can have after 30 Nov 2026 [V F30]).

**v1 uses the no-standby totals** (owner input, §1). Every figure with a DB standby is a **later upgrade, not
v1**; the tables show what adding it would cost. A (§8.2 Step 1) is already a single-AZ DB with no standby, so
its total does not change.

Adoption date. This paper assumes the owner adopts after 30 Nov 2026, so the F30 rules apply to the
owner's account whatever its history. It does not assume a cluster is created early to stay exempt.

| Line item | A (§8.2) | A2 trimmed AWS | B DO Droplets | C DO App Platform | D Render |
|---|---|---|---|---|---|
| Web ×2 | 40 [A] | 32 (Savings Plan, provisional) [A] | 2 × 4 GB Droplet = 48 [V F2] (web+worker share) | 2 × 12 → 2 × 25 [V F8] | 2 × 7 → 2 × 25 [V F14] |
| Worker ×1 | 20 [A] | 16 [A] | 0 → 24 (3rd Droplet) [V F2] | 25 [V F8] | 25 [V F14] |
| Postgres | 45 single-AZ [A] | 45 single-AZ (v1); later 90 Multi-AZ [A] | 30.45 single 2 GiB, no standby [V F3]; later HA: 2 × 130 = 260 Advanced 8 GiB [V F31] | as B [V F3, F31] | 40 + 15 storage (v1); later HA 80 + 30 storage [V F14, F43] |
| Workspace / plan fee | — | — | — | — | 25 Pro (7-day PITR) [V F14] |
| LB / WAF | 35 [A] | 20 ALB only [A] | 12 [V F11] | included [A] | included [A] |
| NAT / fixed egress IP | 40 [A] | 5 NAT instance (0 for public-subnet tasks, no fixed IP) [A] | 0 (Droplet IP) [A] | 0 → 25 [V F8] | 0 → 100 [V F14] |
| KMS, secrets, registry, storage, logs, traces, backup vault | 30 [A] | 13 [A] | 5 Spaces [V F11] + 0–20 registry [V F11] + 0–20 logs [A] | 5 Spaces [V F11] + 0–20 logs [A] | 5 (Spaces SGP1) [V F11] + 0–20 logs [A] |
| Staging | 35 [A] | 15 (stopped off-hours) [A] | 12 + 15.15 [V F2, F3] | 12 + 12 + 15.15 [V F8, F3] | 7 + 7 + 19 [V F14] |
| **v1 total USD, no DB standby** (low–high) | **245** (185–305), single-AZ already | **≈ 145** | **≈ 122–187** | **≈ 123–195** | **≈ 157–313** |
| **v1 total RM @ 4.10, no DB standby** | **≈ 1 005** (760–1 250) | **≈ 595** | **≈ 500–765** | **≈ 505–800** | **≈ 645–1 285** |
| Later upgrade, not v1: cost to add a DB standby | +45 Multi-AZ [A]; convert in place [V F44] | +45 Multi-AZ [A]; convert in place [V F44] | +229.55 (2 × 130 Advanced in place of 30.45) [V F31]; a move to a new Advanced cluster [A] | as B | +55 (standby = same plan 40 + storage 15) [V F43]; DB restart, "usually for less than five minutes" [V F43] |
| Later upgrade, not v1: total USD with a DB standby | ≈ 290 [A] | **≈ 190** | **≈ 352–416** | **≈ 353–424** | **≈ 212–368** |
| Later upgrade, not v1: total RM @ 4.10 | ≈ 1 190 | **≈ 780** | **≈ 1 445–1 705** | **≈ 1 450–1 740** | **≈ 870–1 510** |
| Removed vs A | — | WAF, managed NAT, X-Ray, 2nd-account locked vault, PR previews (§7.1) | KMS, IAM, WAF, private VPC subnets, Secrets Manager, CloudTrail, X-Ray, locked vault, in-country data, OIDC | same as B, but no servers to patch | same as C; dedicated IP costs $100 |

**AWS vs lean options (D2, B2, B3, B4).** Same line items, in a second table so the main table stays readable.
The lean columns are single values, not low–high ranges. None of them has a DB standby or staging in its
base total. B3 and B4 are sub-variants of B2 and are shown apart from it.

| Line item | A (§8.2) | A2 trimmed AWS | D2 Render lean | B2 VPS lean (DO) | B3 = B2, Postgres on the VPS | B4 Malaysian VPS (iCore) |
|---|---|---|---|---|---|---|
| Web | ×2: 40 [A] | ×2: 32 (Savings Plan, provisional) [A] | **×1** `1c-2g` = 25 [V F36] | one 8 GB / 4 vCPU Droplet = 48 for web, worker, ClamAV and Caddy under Compose [V F2] | as B2: 48 [V F2] | one NVMe VPS 8 GB / 4 cores, RM 59.90 = 14.61 [V F41] |
| Worker ×1 | 20 [A] | 16 [A] | `1c-2g` = 25, ClamAV inside (~2 GB [A]) [V F36] | 0, same Droplet | 0, same Droplet | 0, same VPS |
| Postgres | 45 single-AZ [A] | 45 single-AZ (v1); later 90 Multi-AZ [A] | `1c-2g` 40 + storage 15 (50 GB × 0.30; size [A]) = 55, no standby [V F36] | 30.45 managed 2 GiB, single node, Standard Edition [V F3, F30] | 0, self-run container on the Droplet [A] | 0, self-run on the VPS [A] |
| Workspace / plan fee | — | — | 25 Pro [V F35] | — | — | — |
| LB / WAF | 35 [A] | 20 ALB only [A] | included [A]; "Firewall & DDoS mitigation" [V F14] | 0, Caddy on the Droplet ends TLS; no WAF [A] | as B2 | as B2 |
| NAT / fixed egress IP | 40 [A] | 5 NAT instance (0 for public-subnet tasks, no fixed IP) [A] | 0, no dedicated IP (+100 per IP set if needed [V F35]) | 0, Droplet IP [A] | as B2 | 0, VPS IP [A] |
| KMS, secrets, registry, storage, logs, traces, backup vault | 30 [A] | 13 [A] | 5 Spaces SGP1 [V F11]; Render logs 14 days on Pro [V F35]; a 90-day log store is not included (0–20 [A]) | 5 Spaces [V F11] + 9.60 weekly Droplet backup (20 %) [V F2]; registry GHCR 0 [A]; log store not included (0–20 [A]) | as B2: 5 + 9.60; Spaces also holds WAL and base backups [A] | 1.80 off-site backups in Azure Blob Malaysia West (100 GB × 0.018; size [A]) [V F40]; files on the VPS disk [A]; provider backup service price not verified [A] |
| Staging | 35 [A] | 15 (stopped off-hours) [A] | 0 at first; optional **+33** = 7 + 7 + 19 [V F36] | 0 at first; optional **+24**: a 2nd 4 GB Droplet with Postgres in a container [V F2] | optional **+24**, as B2 [V F2] | optional **+9.73**: NODE1 4 GB, RM 39.90 [V F41] |
| Optional: ClamAV as its own service | — | — | +25 (`1c-2g`), only if ClamAV does not fit in the worker [V F36, F38] | — (fits on 8 GB [A]) | — | — |
| **v1 total USD, no DB standby** | **245** (185–305) | **≈ 145** | **135** no staging · **168** with staging | **93.05** · **117.05** | **62.60** · **86.60** | **16.41** · **26.14** |
| **v1 total RM @ 4.10** | **≈ 1 005** (760–1 250) | **≈ 595** | **≈ 555** · **≈ 690** | **≈ 380** · **≈ 480** | **≈ 255** · **≈ 355** | **≈ 67** · **≈ 107** |
| Later upgrade, not v1: cost to add a DB standby | +45 [A], in place [V F44] | +45 [A], in place [V F44] | +55 (40 + 15 storage) [V F43]; DB restart < 5 min usually [V F43] | +229.55 Advanced 2 × 130 [V F31], via a new cluster [A] | a 2nd server (+48 + 9.60 = +57.60 [V F2]) plus replication we build and run [A] | a 2nd VPS (+RM 59.90 = +14.61 [V F41]) plus replication we build and run [A] |
| Removed vs A | — | WAF, managed NAT, X-Ray, 2nd-account locked vault, PR previews (§7.1) | same as D, plus a single web instance, no DB standby, no staging at first | same as B, plus one server for everything (no LB, no 2nd host) | as B2, plus managed PITR, managed patching of the DB | as B3, on a small local host with no verified API, IaC or managed services [A]; data stays in Malaysia [V F41] |

How the D2 totals are built (USD). D2 no staging = 25 web + 25 worker + 40 Postgres + 15 storage + 25 Pro +
5 Spaces = 135.00; × 4.10 = RM 553.50. D2 with staging = 135 + 7 web + 7 worker + 19 Postgres = 168.00;
× 4.10 = RM 688.80. Optional adds, not in the totals: ClamAV private service +25, a 90-day log store
0–20 [A], a dedicated IP +100. With staging, ClamAV split out and a US$20 log store, D2 = 213.00 (RM 873.30),
still below A. On Hobby instead of Pro, each D2 total is US$25 lower (110.00 / 143.00), but Hobby gives 3-day
PITR, one seat and 7-day logs [V F35], so D2 is not priced on it (Q8).

What D2 drops against D low (157). D low has two `0.5c-512mb` web instances (14) and staging (33). D2 has one
larger web instance (25) and no staging. The DB and worker are the same in both.

How the B2, B3 and B4 totals are built.
- B2 no staging = 48 Droplet + 9.60 backup (20 % of 48) + 30.45 Postgres + 5 Spaces = 93.05; × 4.10 = RM 381.50.
  With staging = 93.05 + 24 = 117.05; × 4.10 = RM 479.90.
- B2 on a 4 GB / 2 vCPU Droplet (24 + 4.80 backup + 30.45 + 5 = 64.25, RM 263.42) is **not** the base. ClamAV
  (~2 GB [A]) plus web, worker, Caddy and the OS leaves no headroom in 4 GB [A]. It works only if ClamAV moves out.
- B3 no staging = 48 + 9.60 + 5 = 62.60; × 4.10 = RM 256.66. With staging = 86.60; × 4.10 = RM 355.06.
  B3 saves 30.45 a month (RM 124.85) against B2. Whether 8 GB also holds Postgres is not verified [A].
- B4 no staging = RM 59.90 VPS + US$1.80 off-site backup (RM 7.38) = RM 67.28 (US$16.41). With staging
  = RM 59.90 + RM 39.90 + RM 7.38 = RM 107.18 (US$26.14). iCore prices are in RM; tax is excluded as for all options.
- Single-node Standard Edition stays on sale. After the F30 cutoffs a new Standard cluster still gets plans up to
  4 GiB; it only loses standby and read-only nodes [V F30]. So B2's 2 GiB single node is valid after 30 Nov 2026.

Staging for B2 and B3: a second small Droplet, not a Compose profile on the production box. A profile on the
same box would share CPU, memory, disk and the Docker daemon with production. A staging bug or load test could
then stop production, and staging secrets would sit on the production host [A]. The 4 GB size lets staging run
ClamAV too; a 2 GB Droplet (12 [V F2]) is enough if staging uses a stub scanner.

What B3 takes on (Postgres on the same VPS). The saving is US$30.45 a month. In return, we:
- run backups and WAL archiving for PITR ourselves (for example pgBackRest or WAL-G to Spaces) [A];
- run and record restore tests ourselves (UNI-16 restore runbook, T13 drill);
- patch Postgres and the OS ourselves;
- have no standby: a disk or host loss means restoring from the off-site copy;
- share one failure domain: app and DB fail together;
- control role setup fully (we have the superuser), so TEN-01/TEN-02 roles are easy to create. Spike S1 still
  proves `skiw_app` is NOSUPERUSER NOBYPASSRLS.

B4 alternative on a global cloud in Malaysia (Azure Malaysia West), not in the table. A B2as_v2 VM (2 vCPU,
8 GiB) 62.42 + a 64 GiB Standard SSD disk 4.80 (size [A]) + a static IP 3.65 + 100 GB Blob 1.80 = 72.67
(RM 297.95) with Postgres self-run [V F40]. Managed Postgres adds 21.05 (Burstable B1ms with 32 GiB storage),
total 93.72 (RM 384.25); Microsoft says Burstable is "Not recommended for production workloads" [V F40]. With a
General Purpose 2-vCore server it adds 164.28, total 236.95 (RM 971.49) [V F40]. These are list prices from
Microsoft's retail price API; whether the region suits SKIW's other services was not checked [A].

**v1 ranking, cheapest first** (no DB standby, with staging so every option is on the same footing; USD/month,
RM @ 4.10; low end where a range exists). "2 web" is the spec's min 2 web tasks (D3, D15, §8.3).

| Rank | Option | v1 USD | v1 RM | Data in Malaysia | 2 web | Needs a named server operator | HA later, + USD/month |
|---|---|---|---|---|---|---|---|
| 1 | B4 Malaysian VPS (iCore), Postgres on the VPS | 26.14 | 107.18 | yes [V F41] | no, one server | yes | +14.61 and self-built replication [A] |
| 2 | B3 DO VPS, Postgres on the VPS | 86.60 | 355.06 | no | no, one server | yes | +57.60 and self-built replication [A] |
| 3 | B2 DO VPS + managed Postgres | 117.05 | 479.90 | no | no, one server | yes | +229.55, new Advanced cluster [A] |
| 4 | B DO Droplets (low) | 122.60 | 502.66 | no | yes, 2 hosts | yes | +229.55, new Advanced cluster [A] |
| 5 | C DO App Platform (low) | 123.60 | 506.76 | no | yes | no | +229.55, new Advanced cluster [A] |
| 6 | A2 trimmed AWS | ≈ 145 [A] | ≈ 595 | yes | yes | no (NAT instance if chosen) | +45 in place [A] [V F44] |
| 7 | D Render (low) | 157.00 | 643.70 | no | yes, 2 × `0.5c-512mb` | no | +55 [V F43] |
| 8 | D2 Render lean | 168.00 | 688.80 | no | no, one instance | no | +55 [V F43] |
| 9 | A AWS as specified | 245 [A] | ≈ 1 005 | yes | yes | no | +45 in place [A] [V F44] |

The Azure Malaysia West alternative to B4 (72.67 without staging, Postgres self-run) is not ranked: its staging
was not costed. D low is cheaper than D2 with staging and keeps two (smaller) web instances; whether 512 MB is
enough for a Django ASGI web process is not verified [A].

How the B and C totals are built (USD). B low = 48 + 30.45 + 12 + 5 + 27.15 staging = 122.60. B high, no
standby = 48 + 24 + 30.45 + 12 + 5 + 20 + 20 + 27.15 = 186.60. B HA = low and high with 260 in place of
30.45 = 352.15–416.15. C low = 24 + 25 + 30.45 + 5 + 39.15 staging = 123.60. C high, no standby = 50 + 25 +
30.45 + 25 + 5 + 20 + 39.15 = 194.60. C HA = 353.15–424.15. Staging keeps a single 1 GiB node (15.15).
v1.0 used a US$60.90 Standard standby (B 122–217, C 123–225); a new cluster cannot buy that after
30 Nov 2026 [V F30]. Up to v1.3 the A2 and D high ends included a DB standby. From v1.4 the v1 rows exclude
it and the "later upgrade" rows add it: A2 v1 = 32 + 16 + 45 + 20 + 5 + 13 + 15 = 146 (≈ 145); D v1 high =
353 − 40 = 313. The D standby is now +55, not +40, because Render bills the standby's storage too [V F43];
so D with HA is 212–368. A (§8.2 Step 1) is single-AZ and its range is the spec's ±25 %.

DO HA price limits.
- US$260 is the only verified Advanced Edition price: 8 GiB/2 vCPU at US$130 per node [V F31]. That is four
  times the 2 GiB the workload needs.
- The new shared-CPU Advanced plans (8–64 GiB, from 15 Oct 2026 [V F30]) have no published price. Their
  cost is **blocked pending a DO quote**. It may be lower than US$260.
- Advanced Edition in SGP1 is **not verified** [A]; DO says regions depend on the plan [V F32].
- What this blocks: whether C with HA can undercut D with HA (D high with HA, US$368, is about US$56 below
  C HA high at today's verified prices). It does not block A2, or C without a standby. With HA out of v1, it
  blocks only the later-upgrade cost.
- Adding HA later on DO. A cluster created before the F30 restrictions apply to the account may still "add
  standby and read-only nodes" [V F42]. A cluster created after them cannot get a standby on Standard Edition
  [V F30]. DO's docs do not describe converting a Standard cluster to Advanced Edition [V F42], so this paper
  assumes HA later means a new Advanced cluster and a data move, with a cut-over window [A]. Creating the
  cluster before the cutoff (15 Oct 2026 for accounts that never had one) would keep the cheap standby
  option open; this paper does not assume it.

Uncertainty. AWS `ap-southeast-5` prices were not checked line by line (the spec's ±25 % stands). Every
non-AWS "logs" line is a placeholder: DO and Render have no in-country log store, so logs go to a host
or a third party [A]. In the main table no option is cheaper by more than about US$125/month (RM 510) at its
low end. The owner has accepted no DB standby in v1 (§1), so the low ends are valid v1 figures. If HA is added
later, DO (B, C, B2) is the dearest upgrade (+US$229.55 and a new cluster [A]); Render (+US$55) and AWS
(+US$45 [A]) add it in place [V F43, F44]. **D24 says ≈ US$100–150 for the Render fallback; current list prices give
US$157 or more** (Pro workspace + 2 GB worker + 1-CPU DB) for D. D2 fits inside the D24 range only by
dropping things: US$135 with one web instance, no DB standby and no staging; US$168 once staging is added
(above the range). D24's figure therefore matches D2 without staging, not D. Render's own deploy and price
facts for D2 are verified [V F35–F37]; the DB storage size, the log store and whether ClamAV fits in a 2 GB
worker are not [A].

Of A2, D2 and B2, **B2 is the cheapest**. Without staging B2 (US$93.05) is US$41.95 below D2 (US$135) and
US$51.95 below A2's low end (US$145; A2 always includes staging). With staging B2 (US$117.05) is US$50.95 below
D2 (US$168) and US$27.95–72.95 below A2 (US$145–190). B2 gives up: a second server (one Droplet runs
everything, so it is a single point of failure), a load balancer, a WAF, managed OS patching, OIDC to the host,
a DB standby and in-country data. B3 also gives up the managed DB and its PITR, for US$30.45 less. B4 keeps data
in Malaysia [V F41] at the lowest price, but only as a self-run server on a small provider whose API, backups and
support were not verified [A]. Whether 8 GB holds web, worker, ClamAV and (for B3, B4) Postgres is not verified [A].

### 3.3 Capability check against the spec

| Need (spec ref) | A / A2 | B Droplets | C App Platform | D Render |
|---|---|---|---|---|
| Malaysia region (D3, D19) | yes [V F23] | no, SGP1 [V F1] | no, SGP1 [V F1] | no, Singapore [V F13] |
| Roles `skiw_app` NOSUPERUSER NOBYPASSRLS, NOLOGIN definer owners (D4, TEN-02) | yes (RDS master can `CREATE ROLE`) [A, as spec] | No superuser for users [V F5]. Creating NOBYPASSRLS roles needs only `CREATEROLE` [V F27]; whether `doadmin` has it is **not verified** [A] | as B | not documented [A] |
| `ALTER FUNCTION … OWNER TO skiw_tenant_guard`, `ALTER DEFAULT PRIVILEGES` | yes [A] | needs `GRANT skiw_tenant_guard TO <admin> WITH SET TRUE` (allowed via ADMIN option, F27) [A — spike] | as B | as B [A] |
| `pgcrypto` (D18) | yes [A, M1 check] | yes [V F6] | yes [V F6] | yes [V F17] |
| `GRANT` on `django_migrations` | yes (migrator owns it) [A] | same if `skiw_migrator` owns the schema [A] | same [A] | same [A] |
| PITR / retention (T13: 14 d, RPO ≤ 5 min) | 14 d (max 35) [A] | 7 d [V F5] | 7 d [V F5] | 7 d on Pro [V F14] |
| DB standby for a new cluster (T13 step 2) | RDS Multi-AZ [A] | Advanced Edition only after 15 Oct / 30 Nov 2026 [V F30]; from 8 GiB, US$130 a node [V F31] | as B | ≥ 1 CPU plan, standby billed like primary [V F15] |
| DB private access | private subnet + SG | trusted sources [V F7]; VPC not verified [A] | trusted sources by App [V F7] | internal URL, IP allow list [V F17] |
| Persistent worker (D5) | ECS service | Compose service | worker component [V F9] | background worker [A] |
| Pre-deploy `migrate` (D16) | ECS one-off task | deploy script step | pre-deploy job [V F9]; fail-stop not stated [A] | pre-deploy command, fail cancels [V F16] |
| ≥ 2 web, zero-downtime | ECS rolling, min healthy 100 % | LB + script, one host at a time [A] | rolling with health checks [A] | zero-downtime deploys [V F16] |
| 25 s long-poll (D10, D26) | ALB idle timeout configurable [A] | Caddy/LB configurable [A] | 100 s limit [community F10] | 100 min [community F18] |
| Secrets (UNI-08, D23) | Secrets Manager | files/env on host [A] — weakest | encrypted app env vars [A] | env groups / secret files [A] |
| WAF / DDoS | AWS WAF (A only), Shield standard [V F23] | DO network-level only [A] | platform-level [A] | "Firewall & DDoS mitigation" [V F14] |
| Logs in-country, 90 d (D17) | CloudWatch in MY | self-run or 3rd party [A] | platform logs short retention [A] | plan-based retention [A] |
| Registry + scan (T17) | ECR scan on push | DOCR, no scan stated [V F11]; Trivy in CI | Trivy in CI | Trivy in CI |
| Deploy auth from GitHub (D15) | OIDC, no keys | API token / SSH [V F12] | API token [V F12] | API key or deploy hook [A] |
| Object storage, presigned GET ≤ 5 min, SSE (D14) | S3 SSE-KMS | Spaces S3 API [A]; SSE-KMS not offered [A] | as B | external (Spaces or S3) |
| ClamAV in worker (T14) | sidecar/container | container | worker container (2 GB) [A] | worker (2 GB) [A] |
| Drive keyless WIF (D13) | AWS task role → WIF | no workload identity → SA JSON key or another OIDC issuer [A] | as B | as B (Render "OIDC" on Pro is not verified for this use) [A] |
| Bedrock (D12) | task role, in-account | needs AWS credentials from outside AWS (IAM user key or IAM Roles Anywhere) [A] | as B | as B |

D2 (lean Render) matches the D column except in these rows:
- **≥ 2 web, zero-downtime.** D2 has one web instance, so it does not meet "min 2 web". Deploys still work
  with one instance: the new instance takes all new traffic after its health check, and the old one gets
  `SIGTERM` 60 s later [V F37]. A 25 s long-poll on the old instance should finish inside those 60 s, but Render
  does not say open requests are kept, and it does not state how long a deploy hiccup lasts: **could not
  verify** [A]. A crash or restart of the single instance stops the service until it is back [A].
- **DB standby.** None in D2; recovery is a PITR restore into a new instance (7 days on Pro) [V F35, F17].
- **ClamAV.** Render runs one container per service; no sidecar is described [V F38]. ClamAV runs inside the
  2 GB worker [A], or as its own private service at +US$25 [V F36].
- **Object storage.** Render has no managed object storage; only self-run MinIO on a disk [V F39]. D2 uses
  Spaces SGP1 (US$5) [V F11].

B2 (lean VPS) matches the B column except in these rows:
- **≥ 2 web, zero-downtime.** One host, no load balancer. Two `web` containers behind Caddy can be replaced one
  at a time, but a host fault stops everything until the host is rebuilt or restored [A].
- **WAF / DDoS.** No DO Load Balancer in front; only Caddy and the host firewall [A].
- **Malaysia region.** B2 and B3 stay in SGP1 [V F1]. B4 is in Cyberjaya or Kuala Lumpur per the provider's
  page [V F41].

B3 and B4 (Postgres on the VPS) differ from B in the database rows:
- **Roles (D4, TEN-02) and `ALTER FUNCTION … OWNER`.** Fully in our control: we hold the superuser, so every
  role and owner change is possible. Spike S1 still proves the runtime role has no superuser or BYPASSRLS.
- **PITR / standby.** None managed. PITR exists only if we run WAL archiving and base backups to an off-site
  bucket [A]; RPO and RTO depend on that setup and on tested restores (UNI-16). No standby.
- **DB private access.** Postgres listens only on the Docker network or localhost; no network rule needed [A].

### 3.4 Builder recommendation (not a decision)

Two options at most. From v1.4 both are judged on the v1 (no DB standby) totals, with staging (§3.2 v1 ranking).

1. **A2 — trimmed AWS in `ap-southeast-5`** (v1 ≈ US$145, RM ≈ 595 [A]), only if the owner accepts the A2 cuts
   and their residual risks (§7.1, Q6). About US$21 above C, keeps two web tasks, no new cross-border flow, the
   smallest spec change. HA later is +US$45 [A], added in place [V F44].
2. **C — DO App Platform + Managed PostgreSQL + Spaces in SGP1, without a DB standby** (v1 ≈ US$123.60–194.60,
   RM ≈ 505–800 [V/A mix]), only if the owner accepts the Singapore PDPA step and the gaps in §7. It is the
   cheapest option that keeps two web instances and needs no named server operator. Its HA upgrade is the
   dearest: +US$229.55 and a move to a new Advanced cluster [V F31, F42] [A]. If the owner expects to add HA
   within a year or two, **D Render** (v1 US$157, HA later +US$55 in place [V F43]) is the better second
   choice.

Did the ranking change? No. With HA out of v1, C (123.60), A2 (≈ 145) and D (157) sit in one band, about
US$33 apart. A2 stays first because it keeps data in Malaysia at about US$21 more than C. What changed is the
reason D can replace C: no longer "a standby is needed now", but "HA is likely later".

D2 (lean Render) costs US$135 without staging and US$168 with it, above A2 (≈ US$145) and D low (US$157) on
the same footing. It has one web instance and the Singapore PDPA step, while A2 keeps two web tasks and data in
Malaysia. It does not change the ranking above.

B2 (lean VPS, US$93.05 without staging, US$117.05 with it) is the cheapest of A2, D2 and B2, and B3 and B4 are
cheaper still (§3.2). All three need a named person to patch, back up and restore one server (Q4, Q9). Without
that person they stay out of the shortlist, so the ranking above does not change. If the owner names an
operator, B4 and its Azure Malaysia West alternative (US$72.67–93.72) are the only options under US$100 that
keep data in Malaysia. iCore is not verified beyond its price page [A].

Owner inputs 2 and 3 (downtime and manual restore accepted; backups by export, §1, §3.5) change the points below.
They change no ranking:
- **One web instance (D2, B2–B4)** no longer conflicts with the owner's stated availability, pending
  confirmation in the adopting spec (Q10).
- **The hard rules still decide the shortlist.** On non-AWS options, TEN-01/TEN-02 hold only if spike S1 passes;
  S1 now also tests a `BYPASSRLS` backup role (§3.5). B, B2, B3 and B4 still need a named operator (Q4, Q9).
- **The backup line adds US$0–2 a month** to any option (Drive within the Workspace pool, or Azure Blob Malaysia
  West), or RM 39.90 for a second iCore VPS (§3.5). No ranking moves.
- A2 stays first and C second. For A2 the extra copy can stay in `ap-southeast-5`, with no new flow. For C and
  D a Drive copy would add a second foreign location. D low (US$157) still costs less than D2 with staging
  (US$168) and keeps two web instances.

Decision tree:

- Owner does **not** accept moving primary data, backups, files and logs to Singapore → **A2**.
  If A2 is still too dear → ask which A2 cut is acceptable next (single `web` is not, §8.2).
- Owner **accepts** the Singapore step (the PDPA adviser names the applicable section 129 condition and its
  evidence, the transfer notice is in place, Q15 contracts checked — §4) →
  - v1 has no DB standby (owner input, §1), lowest operations load → **C** (D Render if pre-deploy
    fail-stop and longer timeouts matter more than ≈ US$33–120/month, both without a standby);
  - HA expected later → **D Render** (+US$55 in place), or C only after a DO quote and SGP1 check for
    shared-CPU Advanced Edition (§3.2). DO HA at today's verified price (≈ US$353–424) costs more than A (US$245);
  - has a named person to patch and run servers → B is possible, but saves little over C.
- Whichever is chosen, a **database spike** (§9, S1) must pass on the chosen managed Postgres before the spec
  is changed for real.

### 3.5 Backup design for the owner's proposal

The owner proposes a scheduled job that exports the database to a cloud storage provider such as Google Drive
(§1, input 2). This section is provider-neutral, except where it names Drive. The export adds to the
platform's own backups where an option has them; it does not replace them.

1. **What is exported.** A logical dump in custom format (`pg_dump -Fc`, compressed, restored with
   `pg_restore`) [V F48]. **Row security matters here.** The spec puts `FORCE ROW LEVEL SECURITY` on every
   tenant table (spec §7, T1), so even the owner `skiw_migrator` is subject to RLS. `pg_dump` turns row
   security off and **throws an error** if its role cannot bypass RLS; it does not silently dump part of the
   data [V F48]. The job therefore needs its own read-only login role with `BYPASSRLS` (for example
   `skiw_backup`), or the vendor admin role if that role has `BYPASSRLS`.
   - On a managed DB with no superuser, a `CREATEROLE` user cannot grant `BYPASSRLS` [V F27]. Whether the DO or
     Render admin role can is **not verified** [A]; spike S1 must test it (§9).
   - On self-run Postgres (B3, B4) we hold the superuser.
   - This role reads every tenant's data. Its password is a production secret (UNI-08), and only the backup
     job uses it.
2. **Schedule and RPO.** The RPO equals the interval: daily loses up to 24 h of work, 6-hourly up to 6 h, hourly
   up to 1 h. A shorter interval costs no extra money at this size [A: database assumed to be a few GB at
   most], but each run adds load and storage. Compare the platforms' own PITR:
   - AWS RDS uploads transaction logs every five minutes and restores to any point in the retention period
     [V F47]; the spec sets 14 days (T13).
   - Render PITR: 3 days on Hobby, 7 days on Pro [V F35].
   - DO managed PostgreSQL: daily full backups plus WAL, PITR over the last 7 days [V F5].
   - B3 and B4 (self-run): no PITR unless we set up WAL archiving [A]. There the dump is the **only** copy,
     and RPO is the interval.
3. **RTO and the restore drill.** Recovery is manual: create a clean instance → `pg_restore` with the
   migrator or admin role → check row counts and run the audit-chain verification → point the app at it →
   `/readyz` returns 200. How long this takes depends on the database size [A]. **Drill:** every quarter, restore
   the latest dump into a clean instance, time it, and record it in the UNI-16 restore runbook (T13). A backup
   that has never been restored does not count.
4. **Encrypt before upload.** Encrypt on the host before upload, with a public key (for example `age` or
   `gpg`). The host holds only the public key. The private key is held by the owner offline, with a sealed second
   copy for a named second person [O]. It is never in the backup storage, the platform secret store or the
   repo (UNI-07, UNI-08). Losing the private key loses every backup. This paper holds no key material.
5. **Upload credential (Drive).** A service account has no storage quota and cannot own files. It must upload
   into a **shared drive**, or use OAuth on behalf of a person [V F45]. D13's keyless route (WIF from the AWS task
   role) does not exist off AWS (§3.3), so the host must hold a service-account key or an OAuth refresh token.
   That is a **downgrade** from D13/T15 and conflicts with PROJECT.md §10 (as for T15 in §7). If the owner
   accepts it, the credential:
   - is separate from the Drive filing identity of D13;
   - can reach only one shared drive, at the lowest role that can add files [A];
   - lives in the platform secret store and is rotated on a schedule (for example 90 days [A]).
6. **Integrity.** Store a SHA-256 checksum with each file and check it after upload. Run `pg_restore --list`
   on each new file. The quarterly drill restores one. A **dead-man switch** raises an alarm if no new file
   arrives within the interval plus a margin. It runs off the host, so a dead host also raises it [A].
7. **Retention, deletion and ransomware.**
   - Backups hold all client data, including data past the spec's `retention.*` periods (§8: ai_conversations
     90 d, raw_html 7 d, scans_quarantine 1 d, audit_export 1 y [O], ex-client data [O]). Backups need their own
     retention (for example 35 days [A]), agreed with the PDPA adviser. A client's deletion notice must say how
     long their data stays in backups.
   - A compromised host holding the upload credential can delete or overwrite backups. Drive trash and version
     history are not a lock: a shared-drive manager can empty the trash [A]. Mitigations: an append-only or
     versioned target with object lock, or a second copy the job cannot delete (owned by the owner, pulled
     rather than pushed) [A].
8. **Size and quotas (Drive).**
   - Each user can upload 750 GB in 24 hours. Files can be up to 5 TB. A shared drive holds at most 500 000
     items [V F45]. The API quota is far above one upload an hour [V F45].
   - Shared-drive content counts toward the Workspace pool: Business Starter gives 30 GB per user [V F46]. With
     5 users that is 150 GB. A 1 GB dump kept 35 days uses 35 GB [A].
9. **Who can read the backups.** Any member of the shared drive can open the files. With encryption before
   upload they see only ciphertext. Without it, anyone with access sees the whole client database. Keep
   membership to the owner and the job's identity [A].

**PDPA and D19 (not legal advice).** A database backup in Google Drive is the **whole client dataset** (IC
numbers, holdings, cases), stored wherever Google stores it. Workspace data regions offer only the United States,
the European Union or "No preference", not Malaysia, and Business Starter is not covered [V F46]. This flow is
much larger than D19 flow (2), which covers documents filed to Drive. Encrypting before upload, with the key
kept outside Google, reduces exposure. This paper does **not** say it makes the transfer lawful. D19 says
backups stay in Malaysia, so a Drive copy needs the §4 process (condition and evidence, notice, record) and a
D19 rewording in the adopting spec. It is an owner decision with the PDPA adviser (§4 item 9, Q11).

Two alternatives keep the backup copy in Malaysia:
- **(i) Object storage or a second small host in Malaysia.** Azure Blob Malaysia West at US$0.018 per GB-month,
  about US$1.80 for 100 GB [V F40]. A second iCore VPS, NODE1 at RM 39.90 [V F41]. AWS S3 is listed in
  `ap-southeast-5` [V F23] (price not verified [A]); for A and A2 the copy can stay in the same region.
- **(ii) The platform's own managed backups.** RDS in `ap-southeast-5` [V F23, F47]. DO and Render keep
  backups in their own region; the exact location is not stated [A]. For B, C, D this is Singapore (§4 row 2).

Cost. Drive uses the existing Workspace pool [V F46]; Workspace is outside this paper's totals, so the line is
US$0 while the pool has room. Azure Blob Malaysia West is about US$1.80/month for 100 GB [V F40]. A second
iCore VPS is RM 39.90. None of these changes any ranking in §3.2.

**Option L: dump to the host's own disk (owner input 3, quoted in §1).** The Drive proposal is **Option G**. Items 1–4 and 6–7 above apply to L as well: the `BYPASSRLS` dump role, the RPO equal to the
interval, the restore drill, encryption with an offline key, checksums, and retention.

What L covers:
- a DB crash, a bad migration, or DB corruption;
- the DB being unreachable while the host is up: the file is on the host and can be downloaded.
- **Residency:** data stays in the host's country. There is no new cross-border flow beyond the host itself.

What L does **not** cover:
- loss of the host or its disk, or accidental deletion of the VM;
- loss of the provider account;
- an intruder or ransomware on the host, who can read (if not encrypted) or delete the dumps;
- for B3 and B4, the fact that the dumps sit in the same failure domain as the database (same host, same disk).

Mitigations:
- **Provider snapshots of the host disk.** On DO, Droplet backups cost 20 % of the Droplet price (weekly) or
  30 % (daily) [V F2]. B2 and B3 already include the weekly 9.60 (§3.2); daily would be 14.40. With weekly
  backups a host loss can still lose up to 7 days of dumps. For B4 (iCore) and the Azure VM alternative, snapshot
  products and prices were not verified [A].
- **Encryption at rest** of each dump with the offline public-key pattern (item 4). File permissions limited
  to the backup user (for example mode 0600) [A].
- **Rotation**, for example keep 7 daily and 4 weekly [A]. A **disk-full guard**: skip and alarm if free space is
  below about twice the last dump size [A].
- **Dead-man alarm** (item 6).
- **Periodic pull** of the latest encrypted dump to the owner's own machine or another Malaysia-resident
  location (for example a second iCore VPS [V F41] or Azure Blob Malaysia West [V F40]). A pull is started from
  outside the host, so **the host stores no upload credential**. An intruder on the host cannot reach or
  delete the pulled copies. That is a security advantage over G.

Where L can run:
- **Yes:** the VPS options B2, B3, B4 (and the Azure VM alternative) have their own file system.
- **No:** A and A2 run on ECS Fargate, which has no lasting host disk [A]. The AWS-native equivalent is a dump
  to S3 in `ap-southeast-5` [V F23], or RDS's own backups. L would apply only to an EC2- or Lightsail-based
  variant (A3).
- **No:** C (DO App Platform) has no persistent disk for components [A].
- **D and D2 (Render): only with a persistent disk.** A persistent disk **disables zero-downtime deploys**
  [V F37] and costs $0.25/GB-month [V F36]. So for C, D and D2 "the VPS file system" does not exist; the
  equivalent is the platform's PITR plus G or an object-storage copy.

| | G: Drive export | L: dump on host disk | L + pull (to owner or a Malaysia-resident store) |
|---|---|---|---|
| Covers | DB loss; host loss; provider-account loss | DB crash, bad migration, corruption, DB unreachable | as L, plus host or disk loss, account loss, an intruder deleting the dumps (copies already pulled) |
| Does not cover | a host intruder using the upload credential to delete or overwrite (unless versioned or locked) [A] | host or disk loss, account loss, an intruder on the host, VM deletion | dumps written after the last pull |
| Credential on host | **yes**: Drive key or token (D13 downgrade) | none | **none** (the pull starts outside the host) |
| Residency | **Google's location**, not selectable as Malaysia [V F46]: whole-dataset cross-border flow | host country (Malaysia for B4; Singapore for B2, B3) | host country plus the pull target (owner's machine, or Malaysia [V F40, F41]) |
| RPO | dump interval | dump interval | dump interval for DB faults; time since the last pull for host loss |
| Cost (USD/month) | 0 within the Workspace pool [V F46] | 0 extra disk at this size [A]; DO daily snapshots +4.80 over weekly [V F2] | as L, plus about 1.80 (Azure Blob, 100 GB) [V F40], or RM 39.90 (second iCore VPS) [V F41], or 0 (owner's own machine) |

**Builder recommendation (not a decision).** For a 5-person internal team on a VPS option, use **L + pull** (or
L plus provider snapshots) as the default. The pull goes to a Malaysia-resident target or the owner's machine,
keeps an encrypted copy off the host, and leaves no upload credential on the host. Use **G** only after the
PDPA adviser accepts the whole-dataset transfer (§4 item 9), and then in addition to L + pull, not instead
of it. On A2, C, D and D2 the platform's own backups are the first line; the extra copy is a dump to
in-region object storage, or G under the same PDPA condition.

## 4. Data-residency matrix (PDPA)

Not legal advice. Nothing here says Singapore, or any place, is acceptable for SKIW data.

D19 today (quotation from the spec, kept as written): "primary store, backups, object storage, logs in
Malaysia. Cross-border flows are listed and each needs a Transfer Impact Assessment or a s129 exception
(e.g. consent)" [V F28]. PROJECT.md §11 adds: any new cross-border flow needs a reviewed spec change and the
owner first.

What the current JPDP guideline says (Guideline 3/2025 [V F33]), in short:
- **Basis.** A transfer needs one condition of section 129: s129(2)(a) a substantially similar law,
  s129(2)(b) adequate protection, or one of the s129(3) conditions (for example consent, contract necessity,
  or all reasonable precautions and due diligence through contractual clauses or a certificate).
- **Assessment.** A TIA is how the controller supports a finding under s129(2)(a) or (b) (§§5.3, 6.2). It is
  evidence for that condition, not a basis on its own. Its findings last at most 3 years.
- **Notice.** The controller must tell data subjects about the transfer in its personal data protection
  notice or another written notice (§4.3). This applies whatever condition is used.
- **Records.** The controller keeps records that prove each transfer meets section 129 (§16.2).

| Data class | A / A2 | B / C (DO SGP1) | D Render SG (and F, G) |
|---|---|---|---|
| Client PII in Postgres (IC, holdings) | Malaysia | **Singapore** | **Singapore** |
| DB backups / PITR | Malaysia | **Singapore** (location not stated) [A] | **Singapore** [A] |
| Object storage (scans, IC images, drafts) | Malaysia | **Singapore** | **Singapore** (Spaces) or Malaysia (S3, keys needed) |
| Logs, metrics, traces | Malaysia (CloudWatch) | **Singapore** or log vendor country [A] | **Singapore** or vendor [A] |
| Secrets and app-held MAC keys | Malaysia (Secrets Manager) | **Singapore** (platform env) | **Singapore** |
| AI prompts (D12) | Global route, gate G-AI (unchanged) | same + an extra SG→MY hop | same |
| Google Drive / Calendar (D13) | Google's location (unchanged) | same | same |
| Code, images (no PII) | GitHub (unchanged) | same | same |

Owner checklist before choosing B, C, D, F or G:

1. Name each new flow (rows 1–5 above), its receiver and country in a spec change to D19 (it replaces
   "Stay in Singapore" rejected in D19).
2. For each flow, the owner's PDPA adviser identifies the **applicable section 129 condition** and the
   **evidence** that supports it. Where the condition is s129(2)(a) or (b), the evidence includes a TIA and its
   findings. Other conditions need their own evidence (for example consent records, the contract, or signed
   contractual clauses or a certificate) [V F33 §16.2]. The owner does not pick a condition without the adviser.
3. The adviser also considers Guideline §8.3.3: storage abroad is not "necessary" for a contract where a local
   data centre offers it at a lower or similar cost. A2 keeps data in Malaysia at a similar cost (§3.2).
4. Before any real client data moves, give data subjects a **transfer notice** that meets Guideline §4.3:
   update the client personal data protection notice (Q14) or send another written notice. This is required,
   not optional.
5. Record in `docs/DECISIONS.md`, per flow: the condition, its evidence (TIA date and review date where used),
   how the notice was satisfied (which notice, version, date, how delivered), the receiver record of
   Guideline §16.1, and the adviser's sign-off and date.
6. Answer Q15: do Great Eastern / Phillip agent agreements or SC/BNM rules restrict storing their data abroad?
7. Confirm the breach runbook still meets 72 h / 7 days with the new provider's logs.
8. The adopting spec change rewords D19 so its rule matches the guideline (condition + evidence + notice),
   instead of "TIA or s129 exception".
9. **Database backups outside Malaysia (any option, including A and A2).** A database export to Google Drive
   (Option G, §3.5) moves the whole client dataset to Google's storage location [V F46]. This is a new flow,
   separate from D19 flow (2). The adviser decides whether it can rely on a section 129 condition; encryption
   before upload is evidence of a precaution, not a basis on its own. If the owner does not take this step,
   backups stay in Malaysia (§3.5 alternatives).

## 5. Flows

Deploy / rollback / restore per shortlisted or compared option. Failure paths in brackets.

**A / A2.** Unchanged from §8.3: CI → image to ECR → CDK deploy to staging → manual approval → `migrate`
task as `skiw_migrator` (fails → stop) → ECS rolling, min healthy 100 %, circuit breaker rolls back.
Restore: RDS PITR to a new instance → swap the secret → `/readyz` → timed drill (T13).
A2 drops the locked vault copy and the per-PR preview deploy (§7.1).

**B Droplets.**
1. CI builds, Trivy-scans, pushes the image by digest (GHCR or DOCR, token) [A].
2. Deploy job (GitHub environment with approval) uses a scoped DO token; the host pulls the digest
   through a restricted deploy command or a pull agent [A]. No OIDC exists [V F12].
3. `compose run --rm migrate` as `skiw_migrator` (fails → stop, old containers keep serving).
4. Drain host 1 from the LB, start new containers, wait for `/readyz`, re-add; repeat for host 2.
5. Rollback: redeploy the previous digest; expand/contract (UNI-15) keeps the old code valid.
6. Restore: DO PITR (≤ 7 days) into a new cluster [V F5] → change `DATABASE_URL` → `/readyz` → drill.
7. Host loss: rebuild from an image/script; until then one host serves (RTO depends on the operator) [A].

**C DO App Platform.**
1. CI builds and scans; deploys the app spec from the repo with a DO token [A].
2. Pre-deploy job runs `migrate` [V F9] (if a failed job does not stop the deploy, add a `/readyz`
   migration gate — already D16 "startup fails closed").
3. Rolling replace of 2 `web` and 1 `worker` with health checks [A].
4. Rollback: platform rollback to the previous deployment [A]; else redeploy the previous image.
5. Restore: as B step 6.

**D Render.**
1. CI builds; auto-deploy off; CI calls a deploy hook or the API after checks pass [A].
2. Pre-deploy command `migrate`; failure cancels the deploy [V F16].
3. Zero-downtime switch after health checks; old instance gets the configured grace [V F16].
4. Rollback to a previous deploy [A].
5. Restore: PITR into a new instance [V F17] → repoint → drill.

## 6. Permissions

Not applicable. Hosting does not change the role × action matrix (§6 of the spec). One operator point:
platform dashboard access (DO, Render) shows env secrets, so platform accounts need 2FA/SSO and the
break-glass list of Q19 [O].

## 7. Threat model (only what changes)

| Threat (spec) | Control under B / C / D | How tested |
|---|---|---|
| T1 DB reachable by others | Trusted sources / IP allow list instead of private subnet + SG [V F7]; TLS `verify-full` | Connection attempt from a non-listed IP fails (scripted check in M1) |
| T1/TEN-02 role attributes | Spike S1 (§9) proves `skiw_app` is NOSUPERUSER NOBYPASSRLS and definer owners are NOLOGIN on the vendor DB | M0c + M4 live tests run against the vendor DB as `skiw_app` |
| T2 CRM cookie-jar keys | **Replacement:** app-held KEK in platform secrets instead of KMS CMK; **lost:** CloudTrail record per Decrypt and its alarm | Unit test: no plaintext jar at rest; rotation drill |
| T8 Bedrock route | AWS credentials outside AWS: IAM Roles Anywhere (cert) preferred over an IAM user key [A]; gate G-AI unchanged | Config test: adapter fails closed without credentials or decision |
| T13 data loss | PITR 7 days instead of 14 [V F5, F14]; **lost:** locked vault copy in a 2nd account; **replacement:** nightly `pg_dump` (encrypted) to an object-locked bucket at a second provider [A] | Quarterly timed restore drill (UNI-16 runbook); RTO/RPO per Q3 below |
| T15 Drive access | **Lost:** keyless WIF from the AWS task role. Options: SA JSON key in platform secrets (conflicts with D13, T15 and PROJECT.md §10) or WIF with another OIDC issuer [A] | Repo scan for SA keys stays; SA-cannot-list-non-member test stays |
| T16 secrets | Platform env secrets; manual rotation (no Secrets Manager rotation); 2FA on platform accounts | Rotation runbook drill; gitleaks unchanged |
| T17 supply chain | Trivy in CI replaces ECR scan-on-push; actions pinned | CI gate fails on high/critical (unchanged) |
| T18 abuse / DoS | **Lost:** AWS WAF managed rules; app rate limits stay; a CDN/WAF in front would decrypt traffic outside Malaysia [A] — a new PDPA flow | Rate-limit tests (unchanged); load test |
| T19 audit anchors | S3 Object Lock anchors need a WORM bucket: keep one in AWS `ap-southeast-5` (needs credentials) or verify Spaces object lock [A]; CloudWatch alarms → platform alerts | Anchor tamper tests (unchanged) on the chosen bucket |
| New: host compromise / unpatched OS (B only) | Unattended security updates, SSH closed or key-only, firewall, CIS baseline [A] | Monthly patch check; external port scan |
| New: single datacentre (B, C, D) | Accepted risk if chosen; DB standby only within the region [A]; on DO a new cluster gets a standby only on Advanced Edition [V F30] | Restore drill into a fresh cluster |

D2 loses the same controls as D, plus a second web instance (single web instance).

B2, B3 and B4 lose the same controls as B, plus a second host: one server is a single point of failure, so a
timed restore test (UNI-16, T13) is required before go-live; deploys go over SSH from GitHub Actions with a
token or SSH key (no OIDC to the host); we own the firewall and OS patching, and in B3 and B4 also Postgres
backups, WAL archiving and patching.

### 7.1 A2: controls retained, replaced or removed

A2 keeps AWS, so the B/C/D table above does not apply to it. Being in Malaysia does not keep the controls
A2 cuts. The spec references are F34.

**Unchanged in A2** (as the spec says today): data, backups, files and logs in `ap-southeast-5`; private
subnets for RDS; KMS CMK with CloudTrail per Decrypt (T2); Secrets Manager (UNI-08, T16); GitHub OIDC, no
cloud keys (D15); ECR scan on push (T17); manual approval to production and ECS rolling with circuit breaker
(D15); min 2 `web` tasks (D3); separate staging and production accounts (§8.3); RDS PITR 14 days and
deletion protection (T13); S3 Object Lock audit anchors (T19); CloudWatch Logs 90 days and alarms (D17);
Bedrock via task role (D12); keyless WIF to Drive (D13); app rate limits (T18).

**Changed in A2:**

| Control (spec) | A2 status | What is lost | Residual risk | Owner decision |
|---|---|---|---|---|
| AWS WAF managed core, known-bad-inputs, IP reputation, rate rule 1 000 req/5 min/IP (T18, D3) | **Removed** (or **replaced** by a WAF with only the rate rule, cost not verified [A]) | Edge filtering of known-bad inputs and bad IPs; per-IP flood limit before the app | Floods and scans reach the ALB and app. App limits are per user, so unauthenticated paths (login) are guarded only by app code. Shield Standard stays (network level) [V F23]. T18's "WAF rule set in IaC snapshot test" can no longer pass | Q6a |
| AWS Backup daily snapshot to a Vault Lock vault in a separate account, 35 days (T13, M6) | **Removed** (or **replaced** by a vault lock in the same account, or a weekly cross-account copy [A]) | An immutable copy that an admin of the production account cannot delete | Ransomware, a stolen admin credential or an operator error in the production account can delete the DB and its automated backups. Deletion protection can be turned off by the same admin. PITR 14 days covers bad data, not a hostile admin. M6 "Backup vault lock" cannot be met as written | Q6b |
| X-Ray traces (D17) | **Removed** | Request traces across `web`, `worker` and outbound calls | Slower diagnosis of latency, timeouts and connector faults; logs and metrics stay. Not a data-protection control | Q6c |
| Preview-per-PR environment (§8.3) | **Removed** | A live, isolated URL and DB per PR before merge | Changes are first seen running in shared staging after merge. CI tests and Playwright e2e stay (§8.3 CI row). A bad migration reaches staging before anyone runs it by hand | Q6d |
| Managed NAT gateway with a fixed EIP (D3, §5.2, M1) | **Replaced** — two different options | AWS-run, highly available egress | (a) **NAT instance** with an EIP: the fixed IP stays, so TechVision can still be asked to allow-list it. We patch its OS and own its uptime; one instance is a single point of failure for all outbound calls (CRM, Google, Bedrock unless VPC endpoints are added [A]). Needs a patch and recovery runbook. (b) **Public-subnet tasks**: no NAT cost, but **no fixed egress IP** (it changes when a task restarts), so allow-listing (D3, §5.2) is not possible; tasks have public IPs, so security groups must deny all inbound | Q6e |
| Staging stopped out of office hours (§8.2, §8.3) | **Retained, modified** | Always-on staging | Off-hours testing and restore drills need staging started first | Q6f |
| Fargate Savings Plan (§8.2 cost line) | Cost assumption, **provisional** [A] | — | Commits spend for 1 or 3 years; `ap-southeast-5` rates and the ~20 % saving are not verified. If not bought, web + worker cost ≈ US$60, not US$48 | Q6f |

Guardrail map:

| Rule | A2 | B | C / D |
|---|---|---|---|
| TEN-01, TEN-02 (hard) | unchanged | survives only if spike S1 passes | same as B |
| TEN-09, TEN-11 (hard) | unchanged (app code) | unchanged | unchanged |
| UNI-07 (hard) | unchanged | unchanged | unchanged |
| UNI-08 | Secrets Manager | needs a design (host secret store) | platform secret store meets the rule's text |
| UNI-10 | unchanged | WORM anchor needs replacement | same as B |
| UNI-13 | unchanged | image scan moves to CI | same |
| UNI-16 | deploy (no preview), restore (no locked copy), backup, and NAT-instance patch and recovery runbooks updated in the same PR as each cut (§7.1) | deploy, rollback, restore, host-rebuild runbooks rewritten | deploy, rollback, restore rewritten |
| D16 | unchanged | deploy-script step | pre-deploy job / command |

Availability. Single VPS: any host fault stops the service; restore time is however long the operator takes
[A]. Every option needs a **timed restore drill** recorded in the restore runbook (UNI-16, T13).

## 8. Configurable values

| Value | Today (spec) | A2 | B | C | D |
|---|---|---|---|---|---|
| Infra sizes, counts, regions | CDK context | CDK context | `infra/` Compose + host vars | `.do/app.yaml` app spec | `render.yaml` blueprint |
| Secrets | Secrets Manager | Secrets Manager | host secret files [A] | app-level encrypted env [A] | env groups [A] |
| Budget alert | AWS Budgets | AWS Budgets | DO billing alert [A] | DO billing alert [A] | Render spend limit [A] |
| Bedrock alert (D12) | AWS Budgets | unchanged | AWS Budgets in the AWS account still used for Bedrock | same | same |
| Business values | `setting` table | unchanged | unchanged | unchanged | unchanged |

## 9. Milestones

What an adopting spec change (v1.14) and the M1 plan would contain.

| # | Scope | Done when (testable) |
|---|---|---|
| S1 | **DB spike** (non-AWS only): on the vendor's managed PG 17, as the vendor admin: create `skiw_migrator`, `skiw_app` (NOSUPERUSER NOBYPASSRLS), NOLOGIN `skiw_tenant_guard`/`skiw_auth_lookup`, a SECURITY DEFINER function owned by a NOLOGIN role, `pgcrypto`, `ALTER DEFAULT PRIVILEGES`, grants on `django_migrations` and the Procrastinate tables; a read-only `skiw_backup` login role with `BYPASSRLS` and a full `pg_dump -Fc` as that role (§3.5) | `make test-live` (M0c tests) passes against the vendor DB as `skiw_app`; a script prints the role attributes; result in `docs/DECISIONS.md` |
| SC | **Spec change** per the list below, with the owner's §4 record | Reviewer approves; owner records the decision; PROJECT.md §9 residency line updated |
| M1' | **Infra staging** on the chosen target | Deploy to staging from CI with no long-lived cloud key where the vendor allows it; `/readyz` 200 via the LB; 25 s long-poll survives the platform timeout; `pgcrypto` confirmed |
| M6' | **Production + backups** | Timed restore drill into a fresh cluster ≤ the agreed RTO; manual approval blocks prod deploy |

Spec sections that change, and review effort (rounds, not days):

| Spec item | A2 | B | C | D |
|---|---|---|---|---|
| D3 hosting | edit: WAF removed or reduced; NAT choice (instance or public subnet); fixed-EIP wording | rewrite | rewrite | rewrite (D24 becomes D3) |
| D4 database | — | rewrite (vendor PG, PITR 7 d, edition/standby) | rewrite | rewrite |
| D12 Bedrock credentials | — | new credential route | same | same |
| D13 Drive WIF | — | replace or accept SA key | same | same |
| D14 object storage | — | Spaces, no SSE-KMS | same | external bucket |
| D15 CI/CD | edit: preview-per-PR job removed; staging schedule | token deploy, no OIDC | same | same |
| D17 observability | drop X-Ray | new log store | same | same |
| D19 residency | — | new cross-border flows; reword per §4 item 8 | same | same |
| D23 config / secrets | — | new secret store | platform env | platform env |
| D24 fallback | update numbers | update | update | merge into D3 |
| §5.2 CRM connect (egress via NAT fixed EIP) | edit only if public-subnet tasks (no fixed IP) | egress IP source | same | same |
| §8.2 cost | new numbers; Savings Plan marked provisional | rewrite | rewrite | rewrite |
| §8.3 environments | remove preview-per-PR row; staging hours | rewrite | rewrite | rewrite |
| M1 infra staging | stacks without WAF / NAT gateway; NAT instance or public subnets; "done when" updated | rewrite | rewrite | rewrite |
| M6 production + backups | "Backup vault lock" replaced or removed; restore proof without a locked copy | rewrite | rewrite | rewrite |
| T13 data loss | locked copy removed or replaced; residual risk recorded | rewrite | rewrite | rewrite |
| T18 abuse / DoS | WAF removed or reduced; WAF snapshot test replaced by rate-limit and load tests | rewrite | rewrite | rewrite |
| T1/T2/T15/T16/T19 | — | all | all | all |
| UNI-16 runbooks | deploy, restore, backup; NAT-instance patch and recovery if chosen | all rewritten | deploy, rollback, restore | deploy, rollback, restore |
| **Estimated review rounds** | **2–3** | **4–6** | **3–5** | **3–5** |

D2 has the same adoption scope as D; D3 and §8.3 must also accept one web instance in place of "min 2 web".

B2, B3 and B4 have the same adoption scope as B, plus: D3 and §8.3 accept one server; M6' needs a recorded
restore of the whole server (and, for B3 and B4, of self-run Postgres from WAL); in B4, data and backups stay
in Malaysia per the providers' pages [V F40, F41], so D19 only names the two new receivers.

## 10. Open questions (owner)

1. **PDPA step:** may primary data, backups, files and logs move to Singapore? If yes, your PDPA adviser must
   name the applicable section 129 condition for each flow and its evidence (a TIA where the condition is
   s129(2)), the transfer notice to clients must be in place, and the adviser's sign-off recorded (§4). This
   paper does not say Singapore qualifies. If no, only A or A2 remain.
2. **Monthly cap:** what is the most you will pay for hosting per month (USD or RM), excluding AI tokens?
3. **Availability target:** what RTO and RPO do you need (spec today: RTO ≤ 2 h, RPO ≤ 5 min, 14-day PITR)?
   Is 7-day PITR and no locked backup copy acceptable?
   *Partly answered 2026-10-11 (§1):* no DB standby (HA) in v1; HA is a later upgrade. Still required: backups,
   PITR where the option has it, and a timed, recorded restore test (UNI-16, T13). Still open: the RTO and RPO
   numbers, and how long a failed DB node or server may be down before it is restored.
   *Further answered 2026-10-11 (§1, inputs 2 and 3):* a short downtime with manual recovery is acceptable, so
   RTO is "hours, manual, no on-call rota"; no number given. Backups by scheduled export (Drive or the host's own
   disk). Still open: the RPO (Q11a), who restores (Q11b), and the RTO number.
4. **Operator:** who patches servers and answers alerts? If nobody, B is out.
5. **AI route:** if hosting leaves AWS, should Bedrock still be called with AWS credentials from outside
   AWS, should AI use the Anthropic API fallback (D12), or stay off until Q13 is decided?
6. **A2 cuts (§7.1):** for each, accept, keep, or pick the cheaper replacement, and accept the residual risk:
   a. WAF: none, rate rule only, or the full spec rule set (T18)?
   b. Locked backup: none, vault lock in the same account, or the spec's second-account vault (T13, M6)?
   c. X-Ray: drop?
   d. PR previews: drop, so changes are first seen in staging?
   e. Egress: NAT instance (fixed IP; who patches it and restores it when it fails?) or public-subnet tasks
      (no fixed IP, so TechVision cannot allow-list us)?
   f. Staging hours, and a 1- or 3-year Savings Plan commitment (rates not yet verified)?
7. **DB standby on DO (C only):** is a single DB node acceptable (recovery by PITR restore, RTO per Q3)? If not,
   should we ask DO for a shared-CPU Advanced Edition quote in SGP1, or move to D Render (§3.2, §3.4)?
   *Answered 2026-10-11 (§1):* a single DB node is acceptable for v1. Remaining point: on DO, adding HA later
   means a new Advanced cluster [A] [V F42]; on Render or AWS it is added in place [V F43, F44].
8. **Lean Render (D2 only):**
   a. Workspace: Pro (US$25, 7-day PITR, unlimited seats, 14-day logs) or Hobby (US$0, 3-day PITR, one seat,
      7-day logs) [V F35]? Render calls Hobby "for individuals building personal projects and prototypes". No
      ban on commercial use was found, but none was ruled out either. The paper prices Pro.
   b. One web instance: is a service stop while that instance restarts acceptable? Render documents
      zero-downtime deploys with one instance [V F37], but not crash-restart time or whether open long-polls
      survive a deploy (could not verify).
9. **Lean VPS (B2, B3, B4 only):**
   a. Who operates the server: patches the OS (and Postgres in B3, B4), watches alerts, and rebuilds or restores
      it when it fails? If nobody, these options are out (as Q4).
   b. Do you accept a single node's RTO and RPO: the service stops while the one server is rebuilt or restored,
      and data since the last backup or archived WAL may be lost (RTO/RPO per Q3)?
   c. B4: is a small Malaysian host acceptable before its support, backups and security practice are checked?
10. **One web instance:** *owner words imply yes (§1, input 2: "a short downtime still bearable"); confirm in
    the adopting spec.* Original question: does "HA can be the afterthought" also cover running **one** web instance? The spec
    asks for min 2 web tasks for no-downtime deploys (D3, D15, §8.3), and this paper did not read the first input
    as changing that. What is known: Render documents zero-downtime deploys with one instance (the new
    instance takes traffic after its health check; the old one gets `SIGTERM` 60 s later) [V F37], but not how
    long a crashed instance takes to restart [A]. DO App Platform's behaviour with one instance was not checked
    [A]. With one instance (D2, B2–B4), a crash stops the service until it restarts or is rebuilt.
11. **Backups (§3.5):**
    a. RPO: how much recent work may be lost? Hourly, 6-hourly or daily dumps (the RPO equals the interval).
    b. Who runs the restore when something is down, and who runs the quarterly restore drill?
    c. Where is the private decryption key kept (owner, offline), and who holds the sealed second copy?
    d. Where does the off-host copy live? Google Drive (Option G: needs the PDPA step in §4 item 9 and a Drive
       credential on the host), or a Malaysia-resident target pulled from outside (L + pull: owner's machine,
       a second Malaysian VPS, or Azure Blob Malaysia West)?
