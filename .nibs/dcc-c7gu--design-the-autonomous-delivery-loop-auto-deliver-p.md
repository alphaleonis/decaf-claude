---
# dcc-c7gu
version: 1
title: Design the autonomous delivery loop (auto-deliver + plan-side machinery)
status: completed
type: research
priority: normal
created_at: 2026-06-20T18:33:58Z
updated_at: 2026-06-20T19:42:51Z
parent: dcc-33j0
order: as
---

## Question
How should the autonomous plan→execute→reflect loop (`auto-deliver`) work end-to-end, and what plan-side machinery + tracker support does it need? Resolve the open design questions BEFORE implementing Face 2 of decaf-plan or the `auto-deliver` driver (#dcc-1wuy). Context: `vnext.md`, the layout research in #dcc-kk29.

## Findings

### The loop (one run = one plan, looping per phase)
SELECT next ready phase → BREAKDOWN (`breakdown-phase`, unattended) → EXECUTE (`batch-dev`, unattended, phase-scoped) → VERIFY (run acceptance, fix gaps NOW) → RECONCILE (`close-out`, unattended) → LEARN → REPLAN → MERGE → loop. STOP at plan completion (human owns "which plan next").

### Two kinds of data
- **Work items** (epics/phases/features, status, acceptance criteria) → the project's **system of record** (tracker).
- **Loop artifacts & state** (run state, per-phase reflection reports, lessons, context logs, verify output) → **on disk**, git-tracked, in `.auto-deliver/`. Documents/logs, not tickets — they belong in NO tracker.

### Tracker-agnostic adapter contract
The loop only ever calls a thin tracker interface (grow `conventions/work-items.md` into it): `create`, `next-ready` (dependency order), `read` (spec + acceptance), `set-status`, `close`+summary, `create-followup`. Design to the WEAKEST backend — `next-ready` is native in nibs, expressible in ADO (links + WIQL), weakest in GitHub (no native deps → satisfy by convention: sub-issues / parent ordering / labels).

## Decision

### Resolved (LOCKED)

**Architecture**
1. **Tracker-agnostic.** Loop talks only to the adapter contract; ADO, GitHub, nibs first-class, markdown fallback; nibs not special; no backend privileged.
2. **Design to the weakest backend** — `next-ready` satisfiable by convention where native deps are absent (GitHub).
3. **On-disk loop state always** in `.auto-deliver/` (git-tracked), regardless of tracker.
4. **No local mirror** — update the real tracker directly at phase boundaries.

**Loop mechanics**
5. **Executable acceptance criteria (keystone): A+C hybrid.** A structured `## Acceptance` section in the work-item body; each item is a runnable check (command/test → expected result, verified deterministically) OR a prose criterion tagged `manual` (subagent-verified, flagged lower-confidence, held for human confirmation — never blocks the loop forever). Body-based → travels across all trackers. draft-spec / draft-plan / breakdown-phase must emit criteria in this form.
6. **verify-and-fix = a sub-routine of `auto-deliver`, not a standalone skill.** Run the phase's runnable checks; on failure dispatch a focused fix (reuse batch-dev/dev machinery), re-verify, bounded retry then escalate. Posture: **fix-now for in-scope gaps** (current-phase scope is immutable — no silent shrink); **defer only genuinely out-of-scope discoveries** as follow-ups (via close-out). `manual` criteria are surfaced + held, never block.
7. **learn = per-phase, writes to `.auto-deliver/lessons.md`.** Durable promotion (CLAUDE.md/docs/erinra) is a thin deferred hook — full erinra integration waits on the memory plugin. v1 accumulates on disk; don't over-promote.
8. **replan folds into `auto-deliver`, NOT close-out** (close-out closes one item; replan touches future siblings — scope mismatch). Primary adaptivity is free from JIT `breakdown-phase` (each phase planned against current reality). auto-deliver may INJECT phases for deferred/discovered work; it NEVER autonomously cuts remaining scope (human-only) — it surfaces the need.
9. **unattended = a `--unattended` flag on the existing skills** (`breakdown-phase`, `batch-dev`, `close-out`), suppressing interactive gates/check-ins. NOT separate skill variants — one skill, one source of truth. The loop passes the flag.

Cross-plugin shape: `auto-deliver` (build) orchestrates → `breakdown-phase` / `close-out` (plan, `--unattended`) + `batch-dev` (build, `--unattended`) + `code-review` (quality) + learn (`.auto-deliver/`, erinra later).

### Still open
None — ready to break into Face 2 implementation tasks.

## Follow-ups
- Break this into Face 2 implementation tasks; un-draft `auto-deliver` (#dcc-1wuy).
- Requirements landing on other work:
  - `conventions/work-items.md` → grow create-only into the full tracker-adapter contract, implementable on the weakest backend.
  - draft-spec / draft-plan / breakdown-phase → emit `## Acceptance` criteria (runnable-where-possible, `manual`-tagged otherwise).
  - breakdown-phase / batch-dev / close-out → `--unattended` flag.
  - `.auto-deliver/` artifact layout to be specified (run state, per-phase reflection, lessons.md, context logs, verify output).

## Summary

Loop architecture + mechanics resolved (tracker-agnostic adapter contract designed to the weakest backend; on-disk .auto-deliver/ state, no mirror; A+C executable acceptance criteria; verify-and-fix/learn/replan as auto-deliver sub-routines; --unattended flags). Spawned the Face-2 epic + enablement tasks; auto-deliver un-drafted.
