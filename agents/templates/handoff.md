# Handoff — <date> <time> · branch <branch> · HEAD <sha>

> In-flight state only. Never committed. Updated after every decision, owner answer, verification,
> commit and PR change (roles/builder.md §11), not only at session end. Redact per START.md.

<!-- Fixed sections 0–10. Don't add, rename or renumber sections. -->

## 0. Active target
- Active spec path:            · Active PR number:
- Working folder: <repo root, or .agent/worktrees/build-<branch>>

## 1. Current PR / branch
- Branch:            · Base:
- Status: draft / ready / in review / merged
- Link:

## 2. Milestones
- Done:
- In progress:
- Pending:

## 3. Git state
```
<paste: git status>
```
Uncommitted files — fingerprint every staged, modified or untracked path when writing this handoff:
| Path | Status | Content hash (`git hash-object <path>`, or `deleted`) |
|---|---|---|

```
<paste: git log --oneline <default branch>..HEAD>
```

## 4. Just finished
One paragraph. Mark what is **verified** (tests/CI/browser actually run) vs only **claimed**.

## 5. Next step (file-level)
Not "continue auth". Say which function, in which file, calling what.

## 6. Open ASK items, blockers, and owner answers
- Open:
- Answered this session (question → answer):

## 7. Open review findings (P0/P1) and verdict
- Review file:            · Verdict:

## 8. Decisions made this session, not yet in the decisions log
-

## 9. Files touched but not committed
-

## 10. Model for the next session
Tier + model, and why.
