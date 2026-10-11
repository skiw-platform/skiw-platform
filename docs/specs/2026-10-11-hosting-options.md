# SKIW Platform — hosting options (decision paper)

- Date: 2026-10-11 · Author: Builder (deep tier) · Status: draft
- Version: 1.0 · Spec hash: not required (this paper changes no spec text)
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

## Facts checked

All rows checked 2026-10-11 unless stated.

| # | Fact | Value | Source URL |
|---|---|---|---|
| F1 | DigitalOcean (DO) regions | 16 regions; **no Malaysia**; SGP1 (Singapore) has Droplets, Managed PostgreSQL, App Platform, Load Balancers, Container Registry, Spaces | https://docs.digitalocean.com/platform/regional-availability/ |
| F2 | DO Basic Droplets | 2 GB/1 vCPU $12; 4 GB/2 vCPU **$24**; 8 GB/4 vCPU $48; backups 20 % (weekly) or 30 % (daily) of Droplet price | https://www.digitalocean.com/pricing/droplets |
| F3 | DO Managed PostgreSQL price | 1 GiB single node **$15.15**; 2 GiB $30.45; 4 GiB $60.90; extra storage $0.215/GiB | https://www.digitalocean.com/pricing/managed-databases |
| F4 | DO PostgreSQL HA pricing | Docs: single node "begin at $15.00"; HA = 2 GiB primary $30 + matching standby $30 | https://docs.digitalocean.com/products/databases/postgresql/details/pricing/ |
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
| F16 | Render deploys | Pre-deploy command runs after build, before deploy; on failure the deploy is cancelled; zero-downtime deploys; old instance gets 30 s grace (up to 300 s) | https://render.com/docs/deploys |
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
| F28 | Spec D19 / D3 / D24 | D19: "primary store, backups, object storage, logs in Malaysia"; each cross-border flow needs a TIA or s129 exception; D19 rejected "Stay in Singapore"; D24 already documents a Render Singapore fallback | spec §3 (repo) |
| F29 | USD→MYR | BNM 2026-10-09: buying 4.071, selling 4.096 | https://api.bnm.gov.my/public/exchange-rate/USD |

## 1. Goal

Give the Reviewer and the owner one honest comparison of where SKIW can run for less than §8.2 Step 1,
with verified prices, the PDPA effect, the security controls each option keeps or loses, and the spec
work each option needs, so the owner can choose (or keep AWS) before any spec change is written.

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
| A2 | AWS `ap-southeast-5`, trimmed | Same CDK design. Cut: WAF (rate limits stay in app), NAT gateway (NAT instance or public-subnet tasks), X-Ray, PR previews, 2nd-account Backup vault (RDS PITR stays); staging stopped out of hours; Fargate Savings Plan | Keeps in-country data, IAM roles, OIDC deploys, KMS, Secrets Manager, Bedrock via task role, WIF for Drive (D13). Loses WAF managed rules, locked vault copy, traces, fixed egress via managed NAT. **Shortlisted.** |
| A3 | AWS Lightsail in Malaysia | Lightsail VMs + Lightsail LB + Lightsail managed DB + bucket, same AWS account | In country [V F24], but VM ops like B, and Lightsail DB availability in Malaysia and its role privileges are **not verified** [A]. Hold until verified. |
| B | DO Droplets + Managed PostgreSQL + Spaces (SGP1) | 2–3 Droplets running Docker Compose behind a DO Load Balancer (or Caddy), Managed PG with standby, Spaces | Cheapest at the low end, but **we operate the servers** (OS patches, Docker, TLS, log shipping), no OIDC (API token, F12), no in-country data, single datacentre [A]. Not shortlisted unless the owner names an operator. |
| C | DO App Platform + Managed PostgreSQL + Spaces (SGP1) | Containers for `web` (2) and `worker` (1), pre-deploy job `migrate`, Managed PG, Spaces | Managed containers, workers and pre-deploy jobs exist [V F9]; one vendor, one region, object storage included. Data in Singapore. **Shortlisted** if the PDPA step is accepted. |
| D | Render (Singapore) | Web services, background worker, pre-deploy command, Render Postgres; object storage elsewhere | Pre-deploy failure cancels the deploy [V F16]; good deploy model. No object storage of its own; dearer than C at equal sizing (§3.2); dedicated IP $100 [V F14]. Already the D24 fallback. Second choice to C. |
| E | Vercel | Serverless functions + CDN | **Rejected.** No persistent worker process for Procrastinate (D5); functions end at 300/800 s [V F19]; default region `iad1`, no Malaysia [V F19, F20]; outage rerouting moves compute to other regions [V F20]; no managed Postgres of its own; the Django ASGI long-poll (D26) and ClamAV do not fit the function model. |
| F | Fly.io (`sin`) | Machines + Managed Postgres | Singapore, managed PG with HA [V F21]. Compute prices and role privileges not verified [A]. Same PDPA step as C. Not costed. |
| G | Railway (Singapore) | Services + Postgres | Singapore region [V F22]; database features (PITR, HA, roles) not verified [A]. Not costed. |
| H | Malaysia-region cloud other than AWS | Azure Malaysia West + Azure Database for PostgreSQL flexible server | In country, zone-redundant HA [V F26]. Not costed; the whole CDK/IAM/Bedrock/WIF design would be rewritten. No Malaysian-owned provider with a verifiable Malaysian region **and** managed PostgreSQL was verified. |
| — | Single VPS, everything on one host | One Droplet with app, worker and self-run Postgres | **Rejected.** About US$35–50 [A], but breaks "min 2 web tasks" (§8.3), has no managed PITR, and one host failure loses service and possibly data. |

### 3.2 Prices for Step 1 (USD/month, list prices)

Workload: 2 web + 1 worker (with ClamAV, needs ~2 GB [A]) + Postgres + staging + storage + backups + LB +
monitoring. **Low** = single DB node and minimum sizes. **High** = DB standby, larger web, extras named.

| Line item | A (§8.2) | A2 trimmed AWS | B DO Droplets | C DO App Platform | D Render |
|---|---|---|---|---|---|
| Web ×2 | 40 [A] | 32 (Savings Plan) [A] | 2 × 4 GB Droplet = 48 [V F2] (web+worker share) | 2 × 12 → 2 × 25 [V F8] | 2 × 7 → 2 × 25 [V F14] |
| Worker ×1 | 20 [A] | 16 [A] | 0 → 24 (3rd Droplet) [V F2] | 25 [V F8] | 25 [V F14] |
| Postgres | 45 single-AZ [A] | 45 → 90 Multi-AZ [A] | 30.45 → 60.90 with standby [V F3, F4] | 30.45 → 60.90 [V F3, F4] | 40 → 80 HA + 15 storage [V F14, F15] |
| Workspace / plan fee | — | — | — | — | 25 Pro (7-day PITR) [V F14] |
| LB / WAF | 35 [A] | 20 ALB only [A] | 12 [V F11] | included [A] | included [A] |
| NAT / fixed egress IP | 40 [A] | 5 NAT instance [A] | 0 (Droplet IP) [A] | 0 → 25 [V F8] | 0 → 100 [V F14] |
| KMS, secrets, registry, storage, logs, traces, backup vault | 30 [A] | 13 [A] | 5 Spaces [V F11] + 0–20 registry [V F11] + 0–20 logs [A] | 5 Spaces [V F11] + 0–20 logs [A] | 5 (Spaces SGP1) [V F11] + 0–20 logs [A] |
| Staging | 35 [A] | 15 (stopped off-hours) [A] | 12 + 15.15 [V F2, F3] | 12 + 12 + 15.15 [V F8, F3] | 7 + 7 + 19 [V F14] |
| **Total USD** | **245** (185–305) | **≈ 145–190** | **≈ 122–217** | **≈ 123–225** | **≈ 157–353** |
| **Total RM @ 4.10** | **≈ 1 005** (760–1 250) | **≈ 595–780** | **≈ 500–890** | **≈ 505–920** | **≈ 645–1 445** |
| Removed vs A | — | WAF, managed NAT, X-Ray, 2nd-account locked vault, PR previews | KMS, IAM, WAF, private VPC subnets, Secrets Manager, CloudTrail, X-Ray, locked vault, in-country data, OIDC | same as B, but no servers to patch | same as C; dedicated IP costs $100 |

Uncertainty. AWS `ap-southeast-5` prices were not checked line by line (the spec's ±25 % stands). Every
non-AWS "logs" line is a placeholder: DO and Render have no in-country log store, so logs go to a host
or a third party [A]. No option is cheaper by more than about US$125/month (RM 510) at its low end, and the
low ends drop the DB standby that the owner's workload list asks for. **D24 says ≈ US$100–150 for the Render
fallback; current list prices give US$157 or more** (Pro workspace + 2 GB worker + 1-CPU DB).

### 3.3 Capability check against the spec

| Need (spec ref) | A / A2 | B Droplets | C App Platform | D Render |
|---|---|---|---|---|
| Malaysia region (D3, D19) | yes [V F23] | no, SGP1 [V F1] | no, SGP1 [V F1] | no, Singapore [V F13] |
| Roles `skiw_app` NOSUPERUSER NOBYPASSRLS, NOLOGIN definer owners (D4, TEN-02) | yes (RDS master can `CREATE ROLE`) [A, as spec] | No superuser for users [V F5]. Creating NOBYPASSRLS roles needs only `CREATEROLE` [V F27]; whether `doadmin` has it is **not verified** [A] | as B | not documented [A] |
| `ALTER FUNCTION … OWNER TO skiw_tenant_guard`, `ALTER DEFAULT PRIVILEGES` | yes [A] | needs `GRANT skiw_tenant_guard TO <admin> WITH SET TRUE` (allowed via ADMIN option, F27) [A — spike] | as B | as B [A] |
| `pgcrypto` (D18) | yes [A, M1 check] | yes [V F6] | yes [V F6] | yes [V F17] |
| `GRANT` on `django_migrations` | yes (migrator owns it) [A] | same if `skiw_migrator` owns the schema [A] | same [A] | same [A] |
| PITR / retention (T13: 14 d, RPO ≤ 5 min) | 14 d (max 35) [A] | 7 d [V F5] | 7 d [V F5] | 7 d on Pro [V F14] |
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

### 3.4 Builder recommendation (not a decision)

Two options at most:

1. **A2 — trimmed AWS in `ap-southeast-5`** (target ≈ US$145–190, RM 595–780 [A]). Same price band as the
   PaaS options, no new cross-border flow, smallest spec change.
2. **C — DO App Platform + Managed PostgreSQL + Spaces in SGP1** (≈ US$123–225 [V/A mix]), only if the owner
   accepts the Singapore PDPA step and the gaps in §7.

Decision tree:

- Owner does **not** accept moving primary data, backups, files and logs to Singapore → **A2**.
  If A2 is still too dear → ask which A2 cut is acceptable next (single `web` is not, §8.2).
- Owner **accepts** the Singapore step (TIA or s129 basis, adviser sign-off, Q15 contracts checked) →
  - wants the lowest operations load → **C** (D Render if pre-deploy fail-stop and longer timeouts matter more
    than ≈ US$30–130/month);
  - has a named person to patch and run servers → B is possible, but saves little over C.
- Whichever is chosen, a **database spike** (§9, S1) must pass on the chosen managed Postgres before the spec
  is changed for real.

## 4. Data-residency matrix (PDPA)

Not legal advice. D19 today: "primary store, backups, object storage, logs in Malaysia. Cross-border flows
are listed and each needs a Transfer Impact Assessment or a s129 exception (e.g. consent)" [V F28].
PROJECT.md §11 adds: any new cross-border flow needs a reviewed spec change and the owner first.

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

1. Name each new flow (rows 1–5 above) in a spec change to D19 (it replaces "Stay in Singapore" rejected in D19).
2. Pick the basis per flow: a Transfer Impact Assessment, or a s129 exception (for example consent) — the
   PDPA adviser says which applies.
3. Record the adviser's sign-off and date in `docs/DECISIONS.md`.
4. Answer Q15: do Great Eastern / Phillip agent agreements or SC/BNM rules restrict storing their data abroad?
5. Update the client privacy notice if the adviser says so (Q14).
6. Confirm the breach runbook still meets 72 h / 7 days with the new provider's logs.

## 5. Flows

Deploy / rollback / restore per shortlisted or compared option. Failure paths in brackets.

**A / A2.** Unchanged from §8.3: CI → image to ECR → CDK deploy to staging → manual approval → `migrate`
task as `skiw_migrator` (fails → stop) → ECS rolling, min healthy 100 %, circuit breaker rolls back.
Restore: RDS PITR to a new instance → swap the secret → `/readyz` → timed drill (T13). A2 drops the vault copy.

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
| New: single datacentre (B, C, D) | Accepted risk if chosen; DB standby only within the region [A] | Restore drill into a fresh cluster |

Guardrail map:

| Rule | A2 | B | C / D |
|---|---|---|---|
| TEN-01, TEN-02 (hard) | unchanged | survives only if spike S1 passes | same as B |
| TEN-09, TEN-11 (hard) | unchanged (app code) | unchanged | unchanged |
| UNI-07 (hard) | unchanged | unchanged | unchanged |
| UNI-08 | Secrets Manager | needs a design (host secret store) | platform secret store meets the rule's text |
| UNI-10 | unchanged | WORM anchor needs replacement | same as B |
| UNI-13 | unchanged | image scan moves to CI | same |
| UNI-16 | runbooks updated for cuts | deploy, rollback, restore, host-rebuild runbooks rewritten | deploy, rollback, restore rewritten |
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
| S1 | **DB spike** (non-AWS only): on the vendor's managed PG 17, as the vendor admin: create `skiw_migrator`, `skiw_app` (NOSUPERUSER NOBYPASSRLS), NOLOGIN `skiw_tenant_guard`/`skiw_auth_lookup`, a SECURITY DEFINER function owned by a NOLOGIN role, `pgcrypto`, `ALTER DEFAULT PRIVILEGES`, grants on `django_migrations` and the Procrastinate tables | `make test-live` (M0c tests) passes against the vendor DB as `skiw_app`; a script prints the role attributes; result in `docs/DECISIONS.md` |
| SC | **Spec change** per the list below, with the owner's §4 record | Reviewer approves; owner records the decision; PROJECT.md §9 residency line updated |
| M1' | **Infra staging** on the chosen target | Deploy to staging from CI with no long-lived cloud key where the vendor allows it; `/readyz` 200 via the LB; 25 s long-poll survives the platform timeout; `pgcrypto` confirmed |
| M6' | **Production + backups** | Timed restore drill into a fresh cluster ≤ the agreed RTO; manual approval blocks prod deploy |

Spec sections that change, and review effort (rounds, not days):

| Spec item | A2 | B | C | D |
|---|---|---|---|---|
| D3 hosting | edit (cuts) | rewrite | rewrite | rewrite (D24 becomes D3) |
| D4 database | — | rewrite (vendor PG, PITR 7 d) | rewrite | rewrite |
| D12 Bedrock credentials | — | new credential route | same | same |
| D13 Drive WIF | — | replace or accept SA key | same | same |
| D14 object storage | — | Spaces, no SSE-KMS | same | external bucket |
| D15 CI/CD | — | token deploy, no OIDC | same | same |
| D17 observability | drop X-Ray | new log store | same | same |
| D19 residency | — | new cross-border flows | same | same |
| D23 config / secrets | — | new secret store | platform env | platform env |
| D24 fallback | update numbers | update | update | merge into D3 |
| §8.2, §8.3, M1, M6, T1/T2/T13/T15/T16/T18/T19 | §8.2, M1 | all | all | all |
| **Estimated review rounds** | **1–2** | **4–6** | **3–5** | **3–5** |

## 10. Open questions (owner)

1. **PDPA step:** may primary data, backups, files and logs move to Singapore, with a TIA or s129 basis and a
   PDPA adviser's sign-off (§4)? If no, only A or A2 remain.
2. **Monthly cap:** what is the most you will pay for hosting per month (USD or RM), excluding AI tokens?
3. **Availability target:** what RTO and RPO do you need (spec today: RTO ≤ 2 h, RPO ≤ 5 min, 14-day PITR)?
   Is 7-day PITR and no locked backup copy acceptable?
4. **Operator:** who patches servers and answers alerts? If nobody, B is out.
5. **AI route:** if hosting leaves AWS, should Bedrock still be called with AWS credentials from outside
   AWS, should AI use the Anthropic API fallback (D12), or stay off until Q13 is decided?
