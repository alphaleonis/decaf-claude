# decaf-build

Build **new** functionality with Claude Code: test-driven development, automated dev-with-review loops, multi-work-item orchestration, and the autonomous whole-plan delivery loop. The companion to [`decaf-quality`](../decaf-quality) (which improves *existing* code) and [`decaf-plan`](../decaf-plan) (which decides what/how) — `decaf-build` **depends on both** and pulls them in automatically, because its automated loops call the review and planning skills.

## Skills

| Skill | Purpose |
|-------|---------|
| `tdd` | Test-driven development — red → green → refactor, one vertical slice (tracer bullet) at a time. Ships supporting guides for deep modules, interface design, mocking, and the final refactor pass. |
| `auto-tdd` | TDD-first feature work with a quality gate: plan → red-green-refactor (via subagent) → `/decaf-quality:auto-code-review`. |
| `auto-dev` | Direct (non-test-first) work with a quality gate: plan → implement (via subagent) → `/decaf-quality:auto-code-review`. For UI, config, scaffolding, infrastructure. |
| `batch-dev` | Orchestrate **multiple nibs** in one run — triage into clusters, pick the best mechanism per cluster (single series / parallel fan-out / scripted workflow / agent team), and dispatch behind one approval gate. |
| `auto-deliver` | The **autonomous whole-plan loop**: `SELECT → BREAKDOWN → EXECUTE → VERIFY → RECONCILE → LEARN → REPLAN → MERGE`, one phase at a time, **without stopping at phase boundaries**. Composes `breakdown-phase`, `batch-dev`, and `close-out` (all `--unattended`) over the tracker-adapter contract; stops only at plan completion. |

```
/decaf-build:tdd                        # test-first, interactive
/decaf-build:auto-tdd "<feature>"       # TDD + auto-review loop
/decaf-build:auto-dev "<feature>"       # implement + auto-review loop
/decaf-build:batch-dev --ready          # batch all ready nibs
/decaf-build:batch-dev <id...>          # batch specific nibs
/decaf-build:auto-deliver <plan-id>     # drive a whole plan to completion, unattended
```

## Dependencies

`decaf-build` declares dependencies on **`decaf-quality`** and **`decaf-plan`** in its `plugin.json`, so installing build pulls both in automatically (Claude Code resolves plugin dependencies on install/enable). The `auto-*` loops and `batch-dev` call `/decaf-quality:auto-code-review` (and `code-review`) for their review gate; `auto-deliver` additionally calls `/decaf-plan:breakdown-phase` and `/decaf-plan:close-out` (both `--unattended`).

## The autonomous delivery loop

`auto-deliver` is the one skill that **self-drives across many phases**. Given a phased plan
(work items in any supported tracker), it loops `SELECT → BREAKDOWN → EXECUTE → VERIFY →
RECONCILE → LEARN → REPLAN → MERGE` per phase and **does not stop at phase boundaries** —
only at plan completion (or a genuine blocked/failure escalation). It composes existing
skills under `--unattended`, talks to the tracker only through the adapter contract
(`conventions/work-items.md`), verifies against executable `## Acceptance` criteria
(`conventions/acceptance-criteria.md`), keeps resumable run state in `.auto-deliver/` (see
[`skills/auto-deliver/artifact-layout.md`](skills/auto-deliver/artifact-layout.md)), and
fixes in-scope gaps now while filing out-of-scope discoveries as follow-ups. Scope cuts are
human-only; the loop surfaces the need but never cuts.
