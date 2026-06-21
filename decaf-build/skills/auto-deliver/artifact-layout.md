# `.decaf/auto-deliver/` artifact layout

The on-disk home for `auto-deliver` loop state and artifacts, created in the **target
project root** when the loop runs (not in this plugin repo). It is the `auto-deliver` subdir
of the shared `.decaf/` artifact root (see `conventions/artifacts.md`). Per the design
(`dcc-c7gu`): loop **state and artifacts** live on disk here; **work items** live in the
tracker. This directory holds documents and logs, never tickets.

The tracker remains the **system of record** for what's done — there is **no local
mirror** of work items. `.decaf/auto-deliver/` records only the loop's own run state and the
narrative/output it produces. On resume, the loop reads `state.json` for the in-flight step,
then re-derives "what's next" from the tracker (`next-ready`), so a stale breadcrumb can
never disagree with the tracker about completion.

## Layout

```
.decaf/auto-deliver/
├── state.json              # current run state — the resume breadcrumb (git-tracked)
├── lessons.md              # accumulated lessons from the LEARN step (git-tracked)
├── phases/
│   └── <phase-id>/         # one dir per phase the loop has worked, keyed by tracker id
│       ├── reflection.md   # per-phase reflection report (git-tracked)
│       ├── verify.log      # raw output of the VERIFY acceptance checks (gitignored)
│       └── context.log     # narrative log of what the loop did this phase (gitignored)
└── .gitignore             # ignores the regenerable logs (see below)
```

## Files

### `state.json` — the resume breadcrumb

Lightweight crash-resume state, **not** a mirror. Just enough to resume the current phase
mid-step; everything authoritative about completion comes from the tracker.

```json
{
  "plan": "<root work-item id>",
  "tracker": "nibs | ado | github | markdown",
  "integration_branch": "<branch the loop merges phases into>",
  "current_phase": "<phase work-item id, or null between phases>",
  "step": "SELECT | BREAKDOWN | EXECUTE | VERIFY | RECONCILE | LEARN | REPLAN | MERGE",
  "started_at": "<ISO8601>",
  "updated_at": "<ISO8601>"
}
```

On start/resume: read `state.json`; if a `current_phase` + `step` is in flight, resume there;
otherwise call `next-ready` on the tracker to pick the next phase. The loop rewrites
`state.json` at each step boundary.

### `lessons.md` — accumulated learnings

The LEARN step appends a dated entry per phase (what was learned, what to do differently).
v1 just accumulates on disk; durable promotion to CLAUDE.md / docs / erinra is a deferred
hook (waits on the memory plugin) — **don't over-promote**.

```markdown
## <phase-id> — <phase title> (<date>)
- <lesson: a pattern, gotcha, or convention discovered this phase>
- <lesson: ...>
```

### `phases/<phase-id>/reflection.md` — per-phase reflection report

Written during VERIFY/RECONCILE: acceptance results (which `[run]` checks passed/failed and
the fixes applied), `[manual]` criteria surfaced for human confirmation, deviations,
decisions made, and follow-ups filed. The durable, reviewable record of the phase.

### `phases/<phase-id>/verify.log`, `context.log` — raw logs

Regenerable, noisy: raw acceptance-check output and a running narrative of dispatches. Kept
for debugging a run; **gitignored** (not durable artifacts).

## Git-tracking decision

Track the **durable** artifacts; ignore the **regenerable** logs. The directory ships its
own `.gitignore`:

```gitignore
# .decaf/auto-deliver/.gitignore
phases/*/verify.log
phases/*/context.log
```

Tracking `state.json`, `lessons.md`, and `phases/*/reflection.md` makes a run resumable
across machines/sessions and leaves a reviewable trail in the project's history; ignoring the
raw logs keeps that trail signal-dense.
