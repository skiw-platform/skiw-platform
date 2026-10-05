# Decisions log

<!-- Committed. Newest at the top. One entry per decision. A settled decision is reopened only by the owner. -->

## 2026-10-05 — New platform repo created: charliekhc/skiw-platform (private)
- **Decision:** The new platform repo is `https://github.com/charliekhc/skiw-platform`, private, created under the owner's personal GitHub account `charliekhc` (the `apiskiw` account was not used because the builder cannot create repos there). Local repo initialised on `main` with `origin` set. Nothing pushed yet.
- **Why:** Owner chose option A (create now, personal account first). The old repo stays reference only.
- **Alternatives rejected:** Creating under `apiskiw` (no access to create there). Building inside the old repo.
- **Scope / affects:** `agents/PROJECT.md` §4 Remote; log branch `agent-logs` is created on this remote by the first `merged <number>`. Moving the repo to an org later is the owner's call.
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

## 2026-10-05 — Setup field values and REC-12 ruling for form PDFs
- **Decision:** (1) Owner name is Ying. (2) Durable notes path = `none`. (3) Admin transaction helper is named `with_admin_operation`; action wrapper is named `authorized_action`; both are implemented in M3/M4. (4) Agent tool folders never committed = `none` beyond `.agent/`; exclude specific local state or secrets under `.claude/` or `.codex/` individually if they appear. (5) Commit trailer = `none`. (6) REC-12 ruling: saved form data may persist; a draft PDF preview is watermarked and temporary; the final PDF is stored when issued or signed. This replaces "decide per PR".
- **Why:** The spec names no concrete helper or wrapper; naming them now fixes the contract for M3/M4. A fixed Sonnet trailer is wrong when other models commit. A standing REC-12 rule avoids deciding it again in every PR.
- **Alternatives rejected:** Blanket ban on `.claude/` and `.codex/` (could hide useful project config). A fixed Sonnet commit trailer. Per-PR REC-11/12 decisions.
- **Scope / affects:** `agents/PROJECT.md` §2, §4, §8, §9, §10; spec §4.1 `form_instance`, M16 form filling (draft preview vs stored final PDF; M16's byte-compare test must use the final PDF, not a watermarked preview).
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

## 2026-10-05 — New platform gets a new repo; old repo is reference only
- **Decision:** The new platform is built in a new repository. `https://github.com/apiskiw/skiw-assistant` (private, default branch `main`) is the old app. It is read-only reference. Do not clone it. Do not copy code from it unless the owner asks. Read single files with `gh api` only when a spec or review needs a fact.
- **Why:** The old app is live and used daily. A new repo avoids a deploy accident and gives a clean start.
- **Alternatives rejected:** Build inside the old repo.
- **Scope / affects:** `agents/PROJECT.md` §4 Remote stays `pending remote` until the owner creates the new repo.
- **Versions:** none
- **Exception to a rule?** no
- **Decided by:** owner

