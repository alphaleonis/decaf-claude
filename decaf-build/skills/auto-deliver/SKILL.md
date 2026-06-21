---
name: auto-deliver
description: Autonomously drive a whole plan to completion — loop SELECT → BREAKDOWN → EXECUTE → VERIFY → RECONCILE → LEARN → REPLAN → MERGE, one phase at a time, WITHOUT stopping at phase boundaries. Use when you have a phased plan (work items in a tracker) and want it built end-to-end unattended. Stops only when the plan is complete (or it genuinely cannot proceed).
argument-hint: "<plan reference or root work-item id> [--base-branch <name>] [--review quick|std|max] [--tracker nibs|ado|github|markdown]"
---

# Auto-Deliver

You are the autonomous driver for an **entire plan**. Pick the next ready phase, build it,
verify it, close it, learn, replan, merge — then **immediately start the next phase**. This
is the one skill in the suite that self-drives across many phases.

> **Do not stop at phase boundaries. That is the entire point of this skill.** A single run
> drives one whole plan to completion. The human owns *"which plan next,"* never *"should we
> keep going."* You exit only on **plan completion** or a genuine **blocked/failure
> escalation** (defined below) — never for a check-in, an approval, or reassurance.

## What you orchestrate

You **call** these; you do not reimplement them. Each already supports unattended operation:

- **Tracker adapter contract** — every work-item read/write goes through the six ops
  (`create` / `next-ready` / `read` / `set-status` / `close` / `create-followup`). Never
  touch a backend directly; never assume which backend is in use.

  @../../conventions/work-items.md

- **`/decaf-plan:breakdown-phase <phase> --unattended`** — phase → feature work items (JIT).
- **`/decaf-build:batch-dev --unattended`** — execute a phase's features (with review).
- **`/decaf-plan:close-out <phase> --unattended`** — reconcile + close + file follow-ups.
- **Acceptance format** — VERIFY parses the `## Acceptance` section the planning skills emit.

  @../../conventions/acceptance-criteria.md

- **On-disk state/artifacts** in `.decaf/auto-deliver/` (in the target project, git-tracked).

  @artifact-layout.md

## Non-negotiable invariants

1. **No gate-stops.** You never pause for approval, confirmation, or a status check. The
   only exits are *plan complete* and *escalation* (a real inability to proceed). Pass
   `--unattended` to every sub-skill so none of them prompts.
2. **Scope is immutable per phase.** During a phase you **fix gaps now, in scope** — never
   silently shrink it. Genuinely out-of-scope discoveries become **follow-ups** (and, if they
   need their own phase, an **injected** phase) — never silent drops. **Only a human cuts
   remaining scope;** if scope *should* shrink, you record and surface the need but keep
   going.
3. **You own tracker status, in the main context.** Subagents that batch-dev launches get
   fresh, work-item-unaware contexts and cannot be trusted to update the tracker. So **you**
   `set-status` → `in-progress` before dispatch and `close` after RECONCILE. Never delegate
   status transitions.
4. **Tracker is the system of record; `.decaf/auto-deliver/` is a breadcrumb, not a mirror.** At
   each lap re-derive "what's next" from the tracker via `next-ready`; `.decaf/auto-deliver/state.json`
   only resumes the in-flight step.

## Setup / resume

1. Resolve the **plan** (root work-item id from the argument) and the **tracker** (the
   `--tracker` value, else detect per the adapter contract).
2. Resolve the **integration branch** (`--base-branch`, else the repo's default branch). Create
   or check it out; every phase merges here. Do **not** push to or merge into `main` — that
   stays a human decision.
3. Read `.decaf/auto-deliver/state.json` if it exists: if a `current_phase` + `step` is in flight,
   **resume at that step**; otherwise start a fresh lap at SELECT. Create `.decaf/auto-deliver/`
   (with its `.gitignore`) if missing, per @artifact-layout.md.

## The loop

Run these steps in order, then loop back to SELECT. Rewrite `state.json` at each step
boundary so a crash resumes cleanly.

### 1. SELECT

Call `next-ready(plan)` on the tracker. **If it returns nothing → the plan is complete →
go to STOP.** Otherwise set `current_phase`, write `state.json` (`step: SELECT`), and
`set-status(current_phase, in-progress)`.

### 2. BREAKDOWN

`/decaf-plan:breakdown-phase <current_phase> --unattended` → feature work items as children
of the phase. JIT: the breakdown is planned against the code earlier phases actually produced.

### 3. EXECUTE

`/decaf-build:batch-dev --unattended` scoped to **this phase's feature children only** (pass
their ids / a phase-scoped filter), forwarding `--review` and `--base-branch <integration
branch>`. batch-dev selects mechanisms, executes, reviews, and merges its clusters per its own
protocol. You do not micromanage it.

### 4. VERIFY  *(verify-and-fix sub-routine)*

`read(current_phase)` and parse `## Acceptance`. Then:

- **`[run]` items** — run each command; compare output to its `expect:` condition.
  - On failure: dispatch a **focused fix** (reuse the batch-dev / dev execution machinery — a
    scoped `Agent` with a pre-approved prompt), then **re-run the check**. Bounded retry
    (default **3** attempts per check); if still failing → **ESCALATE** (you cannot honestly
    call the phase done).
  - **Fix now, in scope.** Do not defer an in-scope gap. Do not narrow the criterion.
- **`[manual]` items** — verify by subagent inspection, mark **lower-confidence**, and
  **surface + hold** for human confirmation. These **never block** the loop.
- **Out-of-scope discoveries** (real, but not this phase's job) → note them for RECONCILE to
  file as follow-ups; do **not** fix them here and do **not** silently absorb them.

Write raw results to `.decaf/auto-deliver/phases/<phase>/verify.log` and begin the phase's
`reflection.md` (acceptance results, fixes applied, manual items held, deviations).

### 5. RECONCILE

`/decaf-plan:close-out <current_phase> --unattended` → reconciles built vs planned, appends
the closure summary, marks the phase done, and files **follow-ups** for deferred / out-of-scope
work. (close-out files follow-ups; it does **not** reassess future phases — that is REPLAN's
job, below.) Finish `reflection.md`.

### 6. LEARN

Append a dated entry to `.decaf/auto-deliver/lessons.md`: patterns, gotchas, or conventions
discovered this phase that make the next one easier. v1 accumulates on disk only — durable
promotion to CLAUDE.md / docs / erinra is a **deferred hook**; do not over-promote.

### 7. REPLAN

Reassess the **remaining** plan against what now exists. Most adaptivity is already free
(each next phase is broken down JIT against current reality). Here, act only on cross-phase
changes:

- If this phase produced **deferred or newly-discovered work that warrants its own phase**,
  **inject** a phase: `create` a work item under the plan, ordered and `blocked-by` set so
  `next-ready` will surface it at the right time.
- **Never autonomously cut remaining scope.** If a remaining phase now looks unnecessary or
  wrong, record the recommendation in `reflection.md` and the final report and **leave the
  phase in place** — scope cuts are human-only.

Update `state.json`.

### 8. MERGE

Ensure the phase's work is integrated onto the **integration branch** (batch-dev merges its
clusters; you confirm the phase as a whole has landed). Confirm the phase is `closed`/done in
the tracker. Then **loop back to SELECT immediately** — no pause, no check-in.

## STOP — plan complete

Reached only when SELECT finds **no ready phase**. Emit a final report:

- phases delivered (with their closure summaries),
- follow-ups filed and any phases injected,
- `[manual]` acceptance criteria awaiting human confirmation,
- accumulated lessons (`.decaf/auto-deliver/lessons.md`),
- any scope-cut recommendations you surfaced but did not act on.

Leave the **merge-to-main / push** decision and **"which plan next"** to the human. Done.

## Escalation — the only non-completion exit

You stop early **only** when you genuinely cannot proceed safely — never for convenience.
Legitimate escalations:

- a `[run]` acceptance check still fails after its bounded retries (the phase cannot honestly
  pass);
- `next-ready` keeps returning a phase whose blockers never clear (a dependency cycle or
  no-progress loop);
- a merge conflict you cannot resolve;
- a situation that genuinely requires human judgment (notably: scope that ought to be cut —
  which you may not do yourself).

On escalation, write the in-flight `state.json` and a clear reason to the run report, then
stop. This is a **failure-stop, resumable** — re-invoking auto-deliver picks up from
`state.json`. It is not a gate-stop, and you must not manufacture one.
