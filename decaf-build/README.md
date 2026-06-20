# decaf-build

Build **new** functionality with Claude Code: test-driven development, automated dev-with-review loops, and multi-work-item orchestration. The companion to [`decaf-quality`](../decaf-quality) (which improves *existing* code) — `decaf-build` **depends on** `decaf-quality` and pulls it in automatically, because its automated loops call the review skills.

## Skills

| Skill | Purpose |
|-------|---------|
| `tdd` | Test-driven development — red → green → refactor, one vertical slice (tracer bullet) at a time. Ships supporting guides for deep modules, interface design, mocking, and the final refactor pass. |
| `auto-tdd` | TDD-first feature work with a quality gate: plan → red-green-refactor (via subagent) → `/decaf-quality:auto-code-review`. |
| `auto-dev` | Direct (non-test-first) work with a quality gate: plan → implement (via subagent) → `/decaf-quality:auto-code-review`. For UI, config, scaffolding, infrastructure. |
| `batch-dev` | Orchestrate **multiple nibs** in one run — triage into clusters, pick the best mechanism per cluster (single series / parallel fan-out / scripted workflow / agent team), and dispatch behind one approval gate. |

```
/decaf-build:tdd                        # test-first, interactive
/decaf-build:auto-tdd "<feature>"       # TDD + auto-review loop
/decaf-build:auto-dev "<feature>"       # implement + auto-review loop
/decaf-build:batch-dev --ready          # batch all ready nibs
/decaf-build:batch-dev <id...>          # batch specific nibs
```

## Dependency

`decaf-build` declares a dependency on **`decaf-quality`** in its `plugin.json`, so installing build pulls quality in automatically (Claude Code resolves plugin dependencies on install/enable). The `auto-*` loops and `batch-dev` call `/decaf-quality:auto-code-review` (and `code-review`) for their review gate. `decaf-build` itself declares no other dependencies.

## Coming in vNext

`auto-deliver` — the autonomous plan→execute→reflect loop that drives a whole plan to completion — will live here. It needs an unattended mode on `batch-dev` (a planned `--unattended` flag, currently a documented stub near the Phase 5 gate) plus the plan-plugin and tracker-adapter work. Not yet implemented.
