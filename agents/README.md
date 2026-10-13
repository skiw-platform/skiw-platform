# Agent kit — builder + reviewer setup for any app

**Kit version: 1.7.5** · record it in each project's `PROJECT.md` when you copy the kit in.

A two-agent workflow: a **builder** that writes code and a **reviewer** that checks every spec and PR
before you merge. It works with any AI coding tool and any model.

## Words you'll see

| Word | Meaning |
|---|---|
| **Spec** | The written plan for what to build. Nothing gets built until the reviewer approves it. |
| **PR** (pull request) | One reviewed batch of code changes, numbered (PR 12). You merge it on GitHub. |
| **Branch** / **default branch** | A separate line of work. The default branch (usually `main`) is the real product; agents never push to it. |
| **Commit** | One saved change in git. Each has an ID (a "SHA"). |
| **Guardrail** | A written rule the code must follow, with an ID like `TEN-09`. |
| **Verdict** | The reviewer's decision: Approved, Approved with conditions, Revision required, or Blocked. |
| **Handoff** | A note the builder keeps updated so a new window can continue where the last one stopped. |
| **Log** | A permanent record of each merged PR, kept on its own branch (`agent-logs`). |
| **LOC** | Lines of code. PRs are kept small (default under 400). |
| **Scaffold** | The first PR that sets up the empty project structure. |

## How it's split

```
agents/
├── START.md              ← the commands (setup, build, review 12, fix …) and the ground rules
├── PROJECT.md            ← the ONLY per-project file (setup fills it with you)
├── roles/
│   ├── builder.md        ← never edited; reads PROJECT.md
│   └── reviewer.md       ← never edited; reads PROJECT.md
├── guardrails/           ← reusable rule packs, every rule has an ID; tick packs in PROJECT.md §8
│   ├── universal.md      (always on)
│   ├── frontend.md       (FE-xx gates + WCAG 2.2 AA)
│   ├── tenancy-rls.md    auth.md          money.md
│   ├── finalized-records.md  public-links.md  files-templates.md
│   └── events-jobs.md    payments.md
└── templates/
    ├── handoff.md        (kept up to date in .agent/handoff.md — local)
    ├── review.md         (reviewer writes .agent/reviews/PR-<N>.md — local)
    ├── decisions.md      (seeds docs/DECISIONS.md — committed)
    └── spec.md  pr-plan.md  pr-log.md
```

**Rule:** a fact is written in one place only. Project facts → `PROJECT.md`. Generic rules → a pack.
Role behaviour → a role file. Commands → `START.md`. Decisions → the path in `PROJECT.md` §2
(default `docs/DECISIONS.md`; committed).
Live status → the handoff (local). Review rounds → `.agent/reviews/` (local), archived by the builder
to the `agent-logs` branch. Merged-PR history → the `agent-logs` branch.

## How quality is enforced

- **Rule IDs.** Every guardrail rule has an ID (`TEN-09`, `MON-01`, `FE-05`).
- **Self-check.** The builder lists every rule the PR touches in the PR body: pass / fail / n-a + evidence.
- **Independent re-check.** The reviewer makes its own list first, then re-verifies every row, and
  never edits anything (Rule 0).
- **Severity P0–P3.** A failed rule is P1 by default; rules marked **(hard)** can't be downgraded.
- **Pinned commit.** A verdict applies only to the exact commit the reviewer checked.
- **Trust boundary.** Text inside PRs, code or files can't instruct the agents ("reviewer: approve") —
  it's treated as data and reported.

## Start a new project

1. Copy this folder into the repo root and name it `agents/`.
2. Open a session on your strongest model and type:
   ```
   Read agents/START.md and run setup
   ```
   It wires the project (creates `CLAUDE.md` and `AGENTS.md`, `.gitignore` entries, folders, the
   decisions log). With no spec yet, it stops and tells you to write one.
3. `spec <topic>` → `review spec <path>` in a second window → `fix` if needed → `review spec` again
   until Approved.
4. `setup` again. Now it fills `PROJECT.md` from the approved spec and asks about anything it can't find.
   Read the result.
5. Create an empty repository on GitHub when convenient. `setup` accepts `pending remote`; the builder
   asks you for the repository before it opens the first PR.
6. `build`.

**Existing project with its own agent files?** `setup` first lists every old rule and where it will go
(or why it's dropped) and waits for your yes before changing anything.

## Daily use

Open a window and type a command. If your AI tool doesn't automatically read `CLAUDE.md` or
`AGENTS.md`, type `Read agents/START.md and run <command>` instead.

| You type | What happens |
|---|---|
| `setup` | wires the project; fills or updates `PROJECT.md` from the approved spec |
| `spec <topic>` | builder writes a new spec |
| `review spec <path>` | reviewer checks the spec |
| `build` | builder checks the spec is approved, backfills any missing logs, then continues from the handoff |
| `review 12` | reviewer reviews PR 12 |
| `fix` | builder applies the latest review's findings — to the spec after a spec review, to the PR after a PR review |
| `approved 12` | after the reviewer approves PR 12: builder saves the final review to `agent-logs` and says "ready to merge" |
| `merged 12` | builder proves PR 12 is merged, writes its log on the `agent-logs` branch |
| `status` | five-line summary, no work |
| `handoff` | saves where things stand — type this before closing a window |

Anything else as the first message → the agent tells you which command to use and waits.

## Session cycle

```
spec → review spec → (fix → review spec) → setup → build → PR 12
                                                            │
                        review 12 ←─────────────────────────┘
                            │
             Revision required → fix → review 12 again
                            │
     Approved / Approved with conditions → approved 12 → "ready to merge"
                            │
                 you merge on GitHub → merged 12 → build
```

## When you need to act, and when things go sideways

- **The agent stops and asks you something.** It pauses on: the first PR of a milestone or new package,
  a more expensive model, anything that differs from the spec, destructive git/database actions, and
  sending data to an outside service. Answer that specific question; it records your answer.
- **When to merge.** Only after `approved <number>` replies "ready for you to merge". That confirms the
  reviewer's latest round is for the PR's current commit, says **Approved** or **Approved with
  conditions**, and is safely saved. Don't push new commits to the PR after that. "Conditions" are small fixes deferred to a named later
  PR; they don't block this merge. **Revision required** or **Blocked** = don't merge.
- **Review says Blocked.** Something is missing (access, a self-check table, a stable commit). Give it
  what it names, then `review <number>` again.
- **You forgot `merged 12`** (or 12 and 13, in any order). Just type `build`. It checks every merged PR
  since the kit was set up and writes any missing log first.
- **New computer or fresh clone.** Review files are local, but the builder copies every review to the
  `agent-logs` branch as it goes, and restores them from there when they're missing.
- **Your AI tool can't reach GitHub.** `merged` and the log check need to read PR status from GitHub
  (the `gh` tool, the API, or the PR web page). If none work, they stop. Give the tool access; a link
  alone isn't proof if the tool can't open it.
- **You changed the spec.** Run `review spec <path>`, then `setup`. `build` refuses to start until both
  are done for the new version.
- **A window closed without `handoff`.** Type `build`. The builder compares the handoff with git and
  with any unsaved file changes, rebuilds what it can, tells you what's unknown, and waits for your okay.
- **Logs on `main`.** Logs live on the `agent-logs` branch so agents never touch `main`. If you want
  them on `main` too, merge `agent-logs` into `main` yourself whenever you like.

## Updating the kit

Improve roles, packs, `START.md` or templates in your master copy, bump the kit version above, then copy
them into projects and update `Kit version used` in each `PROJECT.md`. Never edit a role file inside one
project only — that's how the copies drift apart. A generic rule found in one project goes into a pack
here, not into that project's `PROJECT.md`.

Version rule: patch (1.3.x) = wording; minor (1.x.0) = new rule, pack or command; major (x.0.0) = a
change that breaks existing `PROJECT.md` files.

### Changelog
- **1.7.5** — Reviewer snapshots get an integrity check: file list compared with the commit, every extracted file
  fingerprinted at creation and re-checked at the end; a changed file voids the round. (Blob-SHA comparison was
  rejected: `git archive` applies eol/ident attributes, so those hashes differ.)
- **1.7.4** — After `merged`, the builder cleans up the PR's local branch and worktree without asking when it can
  prove they are fully merged and clean; otherwise it reports which check failed.
- **1.7.3** — Reviewer works in tools whose sandbox makes `.git` read-only: if `git worktree add` fails, it reviews a
  `git archive` snapshot of the exact head SHA (no clone, pin kept) and reports the checks it couldn't run.
- **1.7.2** — `setup` applies listed defaults and reports them instead of asking: durable notes `none`, agent
  tool folders `none`, helper and wrapper names (spec's name first), commit trailer `none`; owner name
  always asked. Only genuinely unknown facts are asked. Existing projects need only `START.md` and `README.md`.
- **1.7.1** — CRM migration findings: `START.md` accepts the `Read agents/START.md and run <command>` prefix it
  tells owners to type; TEN-09 allows `set_config(…, true)`; TEN-03 allows SELECT on append-only tables;
  EVT-01/02 outcome-based (outbox or transactional enqueue).
- **1.7.0** — Live test on a throwaway repo: every builder reply ends with a visible `Handoff:` line;
  handoff template sections fixed; builder feature worktrees named `build-<branch>` and recorded in the
  handoff; reviewer must always list injection attempts as findings.
- **1.6.0** — Round 4 review: approval receipt written by `approved` and required by `merged`; review
  archive only moves forward (never overwrites a newer round, stops on divergence); handoff fingerprints
  uncommitted files; active spec path in handoff; `pending remote` allowed during setup; reviewer
  host-only fallback coherent; worktree removal without `--force`.
- **1.5.0** — Round 3 review: new `approved <number>` step archives the final review before merge;
  archive compares content hashes; merges of unreviewed commits or without a reviewer verdict are logged
  as gate breaches; resume compares uncommitted files; fork PR head fetched before diffing; review output
  doesn't void a review; no-remote first build; `fix` bound to the active PR or spec; symlink checks on
  agent folders; money pack storage-neutral.
- **1.4.0** — Round 2 review: `fix` works on specs; reviewer always uses its own checkout and fetches the
  exact PR head (incl. forks); pre-setup spec review mode; log gate checks every merge since setup;
  reviews archived to the log branch and restored in fresh clones; `merged` never edits the active
  worktree; strict whole-message commands; narrower P0 for injection text; alternate-stack instructions.
- **1.3.0** — Independent review K-01…K-25: trust boundary; spec-approval and reconcile gates on
  `build`; logs on a dedicated `agent-logs` branch with proven merges; reviewer writes only its own
  files and reviews a pinned commit in its own checkout; independent applicability list; P2
  dispositions; strict command matching; safe marker editing; migration inventory before setup;
  checkpoint handoffs; redaction; packs loaded by relevance; stack scope on every pack.
- **1.2.0** — PR log gate. **1.1.0** — rule IDs, P0–P3, reviewer Rule 0, frontend pack.
