# CLAUDE.md

Personal Claude Code configuration — the **`decaf`** marketplace, five plugins organized around what each one *does* (see [README.md](README.md) for per-skill usage and examples):

- **`decaf-build`** — create new behavior (features, capabilities)
- **`decaf-quality`** — improve existing code, behavior-preserving (review, coverage, refactor, audit, diagnose)
- **`decaf-plan`** — decide what/how (research, specs, plans, designs, architecture, decisions)
- **`decaf-memory`** — store/recall knowledge (erinra MCP server)
- **`decaf-protection`** — PreToolUse safety hooks

All five ship from the repo root and are listed in `marketplace.json`. The old `decaf` (core) plugin is **dissolved** — its skills/agents were absorbed into build/quality/plan and a few dropped (see [The dissolved core](#the-dissolved-core)). The superseded originals (`decaf-dev`/`decaf-review`/`decaf-planning`) and the old core have been removed; they remain in git history if ever needed. Not yet merged to `main`.

## Plugins

### `decaf-quality` — Code Quality

Improve existing code without adding behavior: multi-agent code review, coverage-gap analysis, refactoring, and PR-feedback resolution. Standalone (no outward dependencies). Analysis skills produce findings; matching `resolve-*` skills walk them one at a time.

**Skills** (invoked as `/decaf-quality:skill-name`):

| Skill | Purpose |
|-------|---------|
| `code-review` | Run parallel review agents and consolidate into a deduplicated report |
| `auto-code-review` | Automated review → triage → fix (subagent) → re-review loop until stable |
| `resolve-code-review` | Walk findings one at a time — fix / skip / dismiss / defer (`auto` for autonomous TDD) |
| `resolve-pr-feedback` | Walk unresolved PR threads (Azure DevOps / GitHub) — fix / reply / decline / escalate |
| `coverage-review` | Run coverage analysis and review gaps for severity + test suggestions |
| `resolve-coverage-review` | Walk coverage gaps — write tests / skip / dismiss / defer (`auto` available) |
| `refactor` | Analyze code for structural improvements → prioritized refactoring plan |
| `resolve-refactor` | Walk refactoring opportunities — apply / apply incrementally / skip / dismiss / defer |
| `coherence-audit` | Audit docs/specs/comments/config/names vs. the code; find + resolve inconsistencies |
| `diagnose` | Root-cause investigation via competing hypotheses + evidence; diagnoses, never fixes |

**Agents** (referenced as `decaf-quality:agent-name`):

- **Review roster** (spawned by `code-review`): `broad-reviewer`, `quick-reviewer`, `adversarial-reviewer`, `consistency-reviewer`, `knowledge-reviewer`, `design-reviewer`, `security-reviewer`, `performance-reviewer`, `spec-compliance-reviewer`, `prior-feedback-reviewer`, `test-reviewer`, `data-migration-reviewer`
- **Language stack reviewers** (hard-gated by file type): `cpp-reviewer`, `dotnet-reviewer`, `go-reviewer`, `rust-reviewer`, `typescript-reviewer`
- **Validators & skill specialists**: `finding-validator` (re-verifies a consolidated finding), `pr-thread-resolver` (resolves one PR thread), `coverage-reviewer`, `structural-analyst`, `coherence-analyst`, `debugger` (delegated root-cause deep dive for `diagnose`)

### `decaf-build` — Build

Create new behavior: TDD, automated dev-with-review loops, multi-work-item orchestration, and the autonomous whole-plan delivery loop. **Depends on `decaf-quality` and `decaf-plan`** (its loops call the review and planning skills) — installing build pulls both in automatically.

**Skills** (invoked as `/decaf-build:skill-name`):

| Skill | Purpose |
|-------|---------|
| `tdd` | Test-driven development — red → green → refactor, one vertical slice at a time |
| `auto-tdd` | TDD session (plan → red-green-refactor via subagent) then `/decaf-quality:auto-code-review` |
| `auto-dev` | Direct (non-test-first) work then auto-review — for UI, config, scaffolding, infrastructure |
| `batch-dev` | Orchestrate MULTIPLE nibs in one run — cluster, pick the best mechanism per cluster, dispatch behind one gate |
| `auto-deliver` | Autonomous whole-plan loop: SELECT→BREAKDOWN→EXECUTE→VERIFY→RECONCILE→LEARN→REPLAN→MERGE per phase, no stops at phase boundaries; composes breakdown-phase / batch-dev / close-out (`--unattended`) over the tracker-adapter contract |

**Agents** (referenced as `decaf-build:agent-name`): `technical-writer` (LLM-optimized docs). Build skills dispatch general-purpose subagents for implementation.

### `decaf-plan` — Plan

Decide what and how to build; output is plans, RFCs, and decisions, not code. No outward dependencies. Analysis (`architecture-review`) + matching `resolve-architecture-review` follow the same analyze/resolve convention as quality.

**Skills** (invoked as `/decaf-plan:skill-name`):

| Skill | Purpose |
|-------|---------|
| `research` | Dig into an unfamiliar problem/tech from several angles; write up findings |
| `draft-spec` | Interview + read code to write a spec (PRD): what to build and why |
| `grill-me` | Interview one decision at a time to stress-test a plan/design |
| `draft-plan` | Turn a spec into an ordered, phased build plan + work-item nibs |
| `breakdown-phase` | Break one phase into concrete, buildable features with done-checklists |
| `close-out` | Reconcile built vs. planned, record decisions/deviations, close a phase or whole plan, file follow-ups |
| `explore-designs` | "Design it twice": generate several radically different designs for a decision and compare |
| `architecture-review` | Find structural/testability improvements in existing code → recommendations (RFCs), not code |
| `resolve-architecture-review` | Walk those proposals one at a time → RFCs |
| `challenge-decision` | Stress-test a decision by arguing against it → STAND/REVISE/ESCALATE verdict |
| `capture` | Jot a follow-up idea/task as a work-item draft without interrupting current work (created `draft` — excluded from ready work until refined) |

**Agents** (referenced as `decaf-plan:agent-name`): `architect` — design a feature's architecture end-to-end → implementation blueprint (distinct from `explore-designs` and `architecture-review`).

### `decaf-memory` — Memory

Store and recall knowledge via the [erinra](https://github.com/alphaleonis/erinra) MCP server (`claude mcp add erinra -- erinra serve -s user`); a `SessionStart` hook loads the memory protocol automatically.

**Skills** (invoked as `/decaf-memory:skill-name`): `remember` (store), `recall` (hybrid search), `init-memory` (manual context-load fallback), `memory-dashboard` (open the dashboard).

### `decaf-protection` — Safety hooks

No skills or agents — PreToolUse guardrails only. `block-op-secrets` blocks 1Password CLI invocations (`op read`, `op item get`, …) that could emit secret values into the session transcript.

### The dissolved core

The old `decaf` core plugin no longer exists; its contents were absorbed:

- `decision-critic` → `decaf-plan:challenge-decision`; `note` → `decaf-plan:capture`; `architect` → `decaf-plan` agent
- `incoherence-detector` → `decaf-quality:coherence-audit`; `problem-analysis` → `decaf-quality:diagnose`; `debugger` → `decaf-quality` agent
- `technical-writer` → `decaf-build` agent
- **Dropped**: `commit` (project conventions vary too much), `powershell-expert` (out of scope), `planner` (redundant with `draft-plan` + `breakdown-phase`); `csharp-developer`, `go-developer` (briefly ported to `decaf-build`, then removed — no skill dispatches them and the spec-executor persona conflicts with the TDD loop)

## Installation

### As a Local Marketplace

```bash
# 1. From the plugin directory, register as a marketplace
/plugin marketplace add ./

# 2. Install plugins (build pulls quality + plan in automatically)
/plugin install decaf-quality@decaf
/plugin install decaf-build@decaf
/plugin install decaf-plan@decaf
/plugin install decaf-memory@decaf       # needs the erinra MCP server
/plugin install decaf-protection@decaf

# 3. Restart Claude Code to load the plugins
```

### Useful Commands

| Command | Purpose |
|---------|---------|
| `/plugin marketplace list` | Show configured marketplaces |
| `/plugin marketplace remove <name>` | Unregister a marketplace |
| `/plugin` | Open interactive plugin manager |

## Directory Structure

```
decaf-claude/
├── .claude-plugin/
│   └── marketplace.json          # Lists all five plugins
├── conventions/                  # Canonical shared convention files (see symlinks below)
├── decaf-quality/                # Code-quality plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # review roster + language + specialist agents (+ debugger)
│   ├── conventions/              # symlinks → ../conventions
│   └── skills/
├── decaf-build/                  # Build plugin (depends on decaf-quality + decaf-plan)
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # technical-writer
│   ├── conventions/              # symlinks → ../conventions
│   └── skills/
├── decaf-plan/                   # Planning plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # architect
│   ├── conventions/              # symlinks → ../conventions
│   └── skills/
├── decaf-memory/                 # Memory plugin (erinra) — skills + session hooks
├── decaf-protection/             # Safety hooks (block-op-secrets)
├── CLAUDE.md
└── README.md
```

## Updating the Plugin

After pushing changes to this repo, update the cached marketplace so Claude Code sees the new version:

```bash
git -C ~/.claude/plugins/marketplaces/decaf pull
claude plugin install decaf-quality@decaf
claude plugin install decaf-build@decaf
claude plugin install decaf-plan@decaf
claude plugin install decaf-memory@decaf
claude plugin install decaf-protection@decaf
```

Then restart Claude Code to load the updated plugins.

## Conventions & shared files (symlinks — IMPORTANT)

Installed plugins can only read files **inside their own directory** — on install, Claude Code copies just that plugin's subtree into the plugin cache, so any `@file` reference that climbs out of the plugin root (e.g. `@../../../conventions/x.md`) resolves in this repo but **silently fails once installed**.

Rules when editing skills/agents:

- Reference conventions only by a **plugin-local** path: `@../../conventions/<file>.md` from `skills/<skill>/SKILL.md` (or `@../conventions/<file>.md` from `agents/<agent>.md`). Never write a path that escapes the plugin root.
- The single canonical copy of each convention lives at **repo-root `conventions/`**. Each plugin's `conventions/` holds **symlinks** into it (`ln -s ../../conventions/<file>.md <plugin>/conventions/<file>.md`). Claude Code dereferences within-marketplace symlinks into the cache on install. Edit the canonical file at the root; do not create a divergent copy inside a plugin.
- Full rationale and the doc link are in [README.md](README.md#development-sharing-conventions-across-plugins-symlinks).

Generated **artifacts** (review reports, refactor plans, loop state) go under one per-project root, `.decaf/` — see [`conventions/artifacts.md`](conventions/artifacts.md). Not the same as the shared `@`-referenced convention files above.

## Working notes

- **Plugin agents auto-discover** from `<plugin>/agents/` — no `plugin.json` key needed (skills need `"skills": "./skills"`; agents do not). Add an agent by dropping its `.md` in `agents/`.
- **Marketplace name is `decaf`; the repo/clone is `decaf-claude`** (they intentionally differ): add via `alphaleonis/decaf-claude`, install as `<plugin>@decaf` — the order is `<plugin>@<marketplace>`. The local cache dir is `~/.claude/plugins/marketplaces/decaf` (keyed by marketplace name, not repo name).
- **Work tracking is nibs** (`.nibs/`, committed alongside the related changes). Gotchas: `nibs update` accepts only one `--body-replace-old`/`--body-replace-new` pair per call (use several calls); a task's parent must be milestone/epic/feature/bug (not `research`); `nibs list --ready` = unblocked, not-started items.

## Versioning

These plugins have **no version field** in their `plugin.json` files. Changes take effect on Claude Code restart (continuous deployment via git commits).

## Related Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Original inspiration
