---
# dcc-kk29
version: 1
title: 'vnext: decide skill set and plugin layout'
status: completed
type: research
priority: normal
created_at: 2026-06-20T17:38:27Z
updated_at: 2026-06-21T13:30:28Z
documents:
    - vnext.md
order: a0
---

## Question

For the vnext rewrite of the decaf plugins, exactly which skills do we want to keep / rewrite / drop / add, and which plugin should each one live in? Naming consistency is an explicit goal. See the design doc `vnext.md`.

Scope: the `decaf-*` plugin skills. The `decaf-review` plugin (promoted from `decaf-exp`) is in good shape and not being rewritten now, though it stays extensible (more skills may be added). `course/` skills (Atomic-CRM-specific) and `devmeta/` commands are reference-only in `old/` and out of scope. `decaf-protection` has no skills (hooks only).

## Current Skills Inventory

Source material for the decision — every current skill grouped by its current plugin (all under `old/` except the kept `decaf-review`).

### decaf (core)
- **commit** — Stage, commit, optionally push; honors project commit-message / topic-branch conventions.
- **decision-critic** — Stress-test a decision through adversarial analysis before committing to it.
- **incoherence-detector** — Detect inconsistencies between docs, code, and specs (codebase audits).
- **note** — Capture a follow-up idea/task as a nib without interrupting current work.
- **powershell-expert** — PowerShell script/module/GUI development per Microsoft best practices.
- **problem-analysis** — Structured root-cause investigation before attempting fixes.

### decaf-dev
- **tdd** — Test-driven development red-green-refactor loop.
- **auto-tdd** — TDD session (plan -> red-green-refactor) then auto-review; test-first features.
- **auto-dev** — Plan -> implement via subagent -> auto-review; for non-test-driven work (UI, config, scaffolding).
- **batch-dev** — Orchestrate execution of MULTIPLE nibs in one run; picks mechanism per cluster (single series / fan-out parallel / workflow / agent team).

### decaf-memory (erinra)
- **remember** — Store a memory in erinra.
- **recall** — Search erinra for stored memories.
- **init-memory** — Manually load erinra session context (fallback when the startup hook doesn't fire).
- **memory-dashboard** — Open the erinra memory dashboard in the browser.

### decaf-planning
- **research** — Multi-phase parallel research with synthesis, before writing a PRD.
- **write-a-prd** — Create a PRD via user interview + codebase exploration (delegates to grill-me).
- **grill-me** — Relentless depth-first interview to stress-test a plan/design.
- **prd-to-plan** — Turn a PRD into a phased tracer-bullet plan; create work items (GitHub/ADO/Nibs/markdown).
- **breakdown-phase** — Break a plan phase (epic) into implementable features with acceptance criteria.
- **close-plan** — Reconcile planned vs actual, record deviations/decisions, close phase/plan, create follow-ups.
- **design-an-interface** — Generate multiple radically different interface designs via parallel subagents ("design it twice").
- **improve-codebase-architecture** — Explore codebase for architectural improvements (deepen shallow modules, testability).
- **handle-architecture-improvements** — Walk through architecture-improvement candidates, creating RFCs one at a time.

### old/decaf-review (OLD — superseded by the current decaf-review below)
- **code-review** — Parallel review agents -> consolidated report.
- **auto-review** — Automated review-fix-recheck loop.
- **coverage-review** — Coverage analysis + gap-severity review with test suggestions.
- **handle-coverage** — Walk through coverage gaps interactively, writing tests.
- **handle-cr** — Walk through code-review findings interactively (auto = autonomous TDD).
- **handle-refactoring** — Walk through refactoring opportunities one at a time.
- **refactor** — Analyze code for structural improvements -> prioritized plan.

### decaf-review (current, promoted from decaf-exp; in good shape, extensible)
- **code-review** — Parallel reviewer agents -> consolidated, deduplicated findings (low/mid/high/max modes).
- **auto-code-review** — Review -> triage -> fix (subagent) -> re-review loop until stable.
- **resolve-code-review** — Walk through findings one at a time; fix / skip / dismiss / defer (auto available).
- **resolve-pr-feedback** — Walk through unresolved PR threads (ADO/GitHub); fix / reply / decline / escalate.

## Decision

> **Layout v4 — decisions locked.** Nothing dropped; every current skill has a target home. The autonomous whole-plan driver is `auto-deliver`.

### Plugin renames (LOCKED)
The three active plugins are renamed around what they *do*, keeping the `decaf-` prefix for namespacing / family consistency:
- **`decaf-dev` → `decaf-build`** — create new behavior
- **`decaf-review` → `decaf-quality`** — improve existing code (behavior-preserving)
- **`decaf-planning` → `decaf-plan`** — decide what/how

Short forms `build` / `quality` / `plan` are the domain labels; skills invoke as `/decaf-build:…`, `/decaf-quality:…`, `/decaf-plan:…`. Deferred plugins (`decaf` core, `decaf-memory`, `decaf-protection`) are not renamed yet.

### Boundary (LOCKED): the crisp test
> **Adds new user-facing behavior? → build. Improves existing code without adding behavior? → quality. Decides what/how (output: plans, RFCs, decisions)? → plan.**

- **build** = new behavior (features, capabilities).
- **quality** = improve existing code, **behavior-preserving** (review finds issues, refactor restructures, coverage adds tests). The resolve-* halves edit code — fine; what unites quality skills is "they add no new behavior," not "they don't touch code."
- **plan** = decide what/how; output is plans / RFCs / decisions, not code.
- build, quality, plan call across plugin boundaries; backed by declared **plugin dependencies** (see below).

### Naming conventions (LOCKED)
- **Analysis skill:** `<domain>-review` (`code-review`, `coverage-review`, `architecture-review`); a domain verb where `-review` doesn't fit (`refactor`).
- **Resolve skill:** `resolve-<analysis-skill-name>` — mirrors its analysis exactly: `resolve-code-review`, `resolve-coverage-review`, `resolve-architecture-review`, `resolve-refactor`, `resolve-pr-feedback`. (Replaces every `handle-*`.)
- **Automated loop:** `auto-<x>` (`auto-tdd`, `auto-dev`, `auto-code-review`).
- **The driver:** `auto-deliver` — the one `auto-*` that loops across a whole *plan*, not a single unit.

### Refactor rationale (LOCKED → quality)
`refactor` + `resolve-refactor` belong in **quality**, not build. Refactoring is **behavior-preserving by definition** (same outputs, better structure) → adds zero new behavior → quality. "It edits code" does not push it to build: every quality `resolve-*` edits code. Output-type discriminator:

| Skill | Analyzes | Produces | Plugin |
|---|---|---|---|
| `code-review` / `coverage-review` / `refactor` | existing code | findings → code fixes | **quality** |
| `architecture-review` | existing code | RFCs / decisions | **plan** |
| `prd-to-plan` / `breakdown-phase` | requirements | plans / work items | **plan** |

The near-cousin that stays in **plan** is `architecture-review` (was `improve-codebase-architecture`): it analyzes existing code like refactor, but its output is RFCs/design decisions (analyze → *decide*), whereas refactor is analyze → *improve the code*.

### decaf-plan (was decaf-planning) — decide what/how
Final skill names + plain one-liners (LOCKED):
- `research` — dig into an unfamiliar problem/tech from several angles; write up findings.
- `draft-spec` (← write-a-prd) — interview + read code to write a **spec** (PRD): what to build and why.
- `grill-me` (kept) — relentless decision-by-decision interview to stress-test a plan/design.
- `draft-plan` (← prd-to-plan) — turn the spec into an ordered, **phased** build plan + work-item nibs.
- `breakdown-phase` — break one phase into concrete, buildable features with done-checklists.
- `close-out` (← close-plan) — reconcile built vs planned, record decisions/deviations, close the item (a phase OR the whole plan), file follow-ups for deferred work.
- `explore-designs` (← design-an-interface) — "Design It Twice": generate several radically different designs/approaches for a decision (a method up to a whole architecture) and compare; writes up the chosen design. Used for module APIs and larger design decisions/docs alike.
- `architecture-review` (← improve-codebase-architecture) — find structural/testability improvements in existing code; output = recommendations (RFCs), not code.
- `resolve-architecture-review` (← handle-architecture-improvements) — walk those proposals one at a time → RFCs.

⚠ draft-plan / breakdown-phase / close-out gain unattended modes for the loop (Face 2 — see #dcc-c7gu). Rewrite each skill's `description:` in this plain language during the port (P3).

### decaf-build (was decaf-dev) — create new behavior
- tdd, auto-tdd, auto-dev, batch-dev
- `auto-deliver` (NEW — autonomous whole-plan delivery driver; lives HERE in build, not its own plugin; see Future)
- ⚠ batch-dev gains an unattended / gate-suppressed mode for the loop
- Declares a **dependency on decaf-quality** (its auto-* loops and `auto-deliver` call `code-review`).

### decaf-quality (was decaf-review / decaf-exp) — improve existing code, behavior-preserving (active; not being rewritten now, but extensible)
- code-review, auto-code-review, resolve-code-review, resolve-pr-feedback (current — happy with these)
- `coverage-review` + `resolve-coverage-review` (← `handle-coverage`) — MOVED IN from old review
- `refactor` + `resolve-refactor` (← `handle-refactoring`) — MOVED IN; its analysis agents (`structural-analyst`, `coherence-analyst`) come with it
- Standalone: declares no outward dependencies, so "I just want code review" stays a one-plugin install.

### core / memory / protection — DEFERRED (revisit later)
- core (`decaf`): commit, note, problem-analysis, decision-critic, incoherence-detector, powershell-expert
- memory (`decaf-memory`): remember, recall, init-memory, memory-dashboard
- protection (`decaf-protection`): hooks only (no skills)

### Superseded by current decaf-quality (keep in old/ for reference; evaluate before removing)
- old `code-review` → `decaf-quality:code-review`
- old `auto-review` → `decaf-quality:auto-code-review`
- old `handle-cr` → `decaf-quality:resolve-code-review`

### Cross-plugin dependencies (RESOLVED — supported)
Per official Claude Code docs (`plugin-dependencies`), a plugin declares a `dependencies` array in `plugin.json`; Claude Code auto-installs declared deps on install/enable (semver-constrained). So decaf-build → decaf-quality (and the loop's cross-plugin calls) are backed by real dependencies: install one plugin and its deps come with it — no manual multi-install. Cross-plugin skill invocation by namespaced name (`/decaf-quality:code-review`) works when the dependency is present.

### Future — the autonomous loop (`auto-deliver`)  [phase 2]
The plan→execute→reflect driver from `vnext.md`, living in decaf-build, composing existing pieces:
1. select next ready phase (nibs `--ready` + topo order)
2. `breakdown-phase` (unattended) → feature nibs
3. `batch-dev` (unattended, scoped to the phase)
4. reflect = verify-and-fix + `close-plan` (reconcile) + learn + replan
5. merge phase; loop until the plan is complete

New pieces it needs: the `auto-deliver` driver skill; executable acceptance criteria (convention in nib bodies + a verify step); unattended modes on `breakdown-phase` and `batch-dev`; a learn/replan step (could lean on decaf-memory / erinra). Because it lives in decaf-build, it inherits build's dependency on decaf-quality and adds one on decaf-plan.

### Open questions
1. (Deferred with core) `powershell-expert` — keep in core or split domain skills out?

### Resolved
- Driver name → `auto-deliver`, lives in decaf-build. [Q3]
- go's home → lives in decaf-build (no separate decaf-flow plugin). [Q1 v3]
- `improve-codebase-architecture` → renamed `architecture-review`. [Q2 v3]
- Package names keep the `decaf-` prefix. [Q4 v3]

## Follow-ups

All decisions LOCKED and shipped in the vnext merge (f678c22). Disposition of deferred items, resolved by later work:
- **core (`decaf`) deferral** → resolved: core was dissolved (#dcc-f5dj). Skills absorbed (decision-critic→challenge-decision, note→capture, incoherence-detector→coherence-audit, problem-analysis→diagnose); agents placed (architect→plan, debugger→quality, technical-writer→build).
- **Open question #1 `powershell-expert`** → resolved: **dropped** (out of scope), along with `commit` and `planner`.
- **memory / protection deferral** → resolved: both ship as plugins (`decaf-memory`, `decaf-protection`).
- `csharp-developer` / `go-developer` were placed in build, then later dropped (#dcc-d6d1) — no skill dispatches them.

## Summary

vnext skill-set and plugin-layout decision research. Outcome: Layout v4 LOCKED — nothing dropped from the skill set; three active plugins renamed by function (decaf-dev→build, decaf-review→quality, decaf-planning→plan) with the crisp boundary test (new behavior→build, behavior-preserving→quality, decide what/how→plan), resolve-<analysis> naming replacing handle-*, and auto-deliver as the whole-plan driver in build. Shipped in the vnext merge (f678c22); all child/referencing nibs completed. Deferred items (core, powershell-expert, memory/protection) resolved by later work — see Follow-ups.
