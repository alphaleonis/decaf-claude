# decaf's Claude Plugins

Personalized Claude Code plugins with specialized agents, skills, and conventions for planning, building, and reviewing code.

Originally forked from [everything-claude-code](https://github.com/affaan-m/everything-claude-code). You probably want that one rather than this one, which has been tailored to my own personal workflow.

> **vNext rewrite in progress.** The plugin suite is being reorganized around what each plugin *does*: **build** (create new behavior), **quality** (improve existing code), **plan** (decide what/how). These three ship today. The original **core**, **memory**, and **protection** plugins are deferred (still under `old/`, pending their own rewrite — they keep their names).

## Plugins

Three plugins ship from this marketplace and can be installed independently (build pulls quality in automatically):

| Plugin | Boundary | Description |
|--------|----------|-------------|
| **`decaf-quality`** | improve existing code | Multi-agent code review, coverage-gap analysis, refactoring, PR-feedback resolution |
| **`decaf-build`** | create new behavior | TDD, automated dev-with-review loops, multi-work-item orchestration (**depends on** `decaf-quality`) |
| **`decaf-plan`** | decide what/how | Research, specs, phased plans, phase breakdowns, design exploration, architecture review |

Deferred (pending vnext rewrite, currently under `old/`): **`decaf`** (core), **`decaf-memory`**, **`decaf-protection`**.

## Installation

```bash
# Add as a marketplace
/plugin marketplace add alphaleonis/decaf-claude-config

# Install plugins (build pulls quality in automatically)
/plugin install decaf-claude-config@decaf-quality
/plugin install decaf-claude-config@decaf-build
/plugin install decaf-claude-config@decaf-plan
```

Or install from a local clone:

```bash
cd /path/to/decaf-claude-config
/plugin marketplace add ./
/plugin install decaf-claude-config@decaf-quality
/plugin install decaf-claude-config@decaf-build
/plugin install decaf-claude-config@decaf-plan
```

## What's Inside

```
decaf-claude-config/
├── .claude-plugin/               # Marketplace manifest (quality, build, plan)
├── conventions/                  # Canonical shared convention files (see Conventions)
├── decaf-quality/                # Code-quality plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # review roster + language + specialist agents
│   ├── conventions/              # symlinks → ../conventions
│   └── skills/
├── decaf-build/                  # Build plugin (depends on decaf-quality)
│   ├── .claude-plugin/plugin.json
│   └── skills/
├── decaf-plan/                   # Planning plugin
│   ├── .claude-plugin/plugin.json
│   ├── conventions/              # symlinks → ../conventions
│   └── skills/
├── old/                          # Deferred plugins + superseded originals (reference only)
├── CLAUDE.md
└── README.md
```

## `decaf-quality` — Skills

Invoked as `/decaf-quality:<skill-name>`. Analysis skills produce findings; matching `resolve-*` skills walk them one at a time.

| Skill | Description |
|-------|-------------|
| `code-review` | Run parallel review agents and consolidate findings into a deduplicated report |
| `auto-code-review` | Automated review → triage → fix (subagent) → re-review loop until the code stabilizes |
| `resolve-code-review` | Walk findings one at a time — fix / skip / dismiss / defer (`auto` for autonomous TDD) |
| `resolve-pr-feedback` | Walk unresolved PR threads (Azure DevOps / GitHub) — fix / reply / decline / escalate |
| `coverage-review` | Run code coverage analysis and review gaps for severity + test suggestions |
| `resolve-coverage-review` | Walk coverage gaps — write tests / skip / dismiss / defer (`auto` available) |
| `refactor` | Analyze code for structural improvements → prioritized refactoring plan |
| `resolve-refactor` | Walk refactoring opportunities — apply / apply incrementally / skip / dismiss / defer |

## `decaf-quality` — Agents

Referenced via the Task tool as `decaf-quality:<agent-name>`.

**Review roster** (spawned by `code-review`):

| Agent | Purpose |
|-------|---------|
| `broad-reviewer` | Broad review across 5 categories with confidence scoring (review floor, always) |
| `quick-reviewer` | Fast generalist: bugs, logic, security patterns, code quality, conventions (review floor, always) |
| `adversarial-reviewer` | Emergent failure scenarios — assumption violations, composition/cascade failures, abuse cases |
| `consistency-reviewer` | Sibling-consistency / unwritten-convention drift; every finding quotes its source |
| `knowledge-reviewer` | Knowledge preservation — undocumented decisions, implicit assumptions, comprehension risk |
| `design-reviewer` | API contracts, data models, boundaries, concurrency, evolution readiness |
| `security-reviewer` | Threat modeling, architectural security gaps, missing controls |
| `performance-reviewer` | Throughput/latency/resource cost — N+1, unbounded growth, hot-path work |
| `spec-compliance-reviewer` | Implementation vs. a drafted spec — gaps, deviations, scope creep (gated on a spec) |
| `prior-feedback-reviewer` | Diff vs. the PR's existing review threads — unaddressed/regressed feedback (gated on threads) |
| `test-reviewer` | Test files only — silent failures, false positives, flaky patterns (gated on test files) |
| `data-migration-reviewer` | EF Core / SQL migrations — schema drift, data loss, rollback safety (gated on migrations) |

**Language stack reviewers** (hard-gated by file type): `cpp-reviewer`, `dotnet-reviewer`, `go-reviewer`, `rust-reviewer`, `typescript-reviewer`.

**Validators & skill specialists**: `finding-validator` (adversarially re-verifies a consolidated finding), `pr-thread-resolver` (resolves a single PR thread), `coverage-reviewer` (assesses gap severity), `structural-analyst` (per-file refactor scoring), `coherence-analyst` (cross-file refactor scoring).

## `decaf-build` — Skills

Invoked as `/decaf-build:<skill-name>`. `decaf-build` declares a dependency on `decaf-quality`; the automated loops call `/decaf-quality:auto-code-review` for their review gate.

| Skill | Description |
|-------|-------------|
| `tdd` | Test-driven development — red → green → refactor, one vertical slice (tracer bullet) at a time |
| `auto-tdd` | TDD session (plan → red-green-refactor via subagent) then auto-review |
| `auto-dev` | Direct (non-test-first) work then auto-review — for UI, config, scaffolding, infrastructure |
| `batch-dev` | Orchestrate **multiple nibs** in one run — cluster, pick the best mechanism per cluster, dispatch behind one approval gate |

## `decaf-plan` — Skills

Invoked as `/decaf-plan:<skill-name>`. Output is plans, RFCs, and decisions — not code. The skills chain into a path from unfamiliar problem to ready-to-build work items.

| Skill | Description |
|-------|-------------|
| `research` | Dig into an unfamiliar problem or technology from several angles; write up findings |
| `draft-spec` | Interview the user and explore the code to write a spec (PRD): what to build and why |
| `grill-me` | Interview one decision at a time to stress-test a plan or design until it holds up |
| `draft-plan` | Turn a spec into an ordered, phased build plan + work-item nibs (vertical-slice tracer bullets) |
| `breakdown-phase` | Break one phase into concrete, buildable features, each with a done-checklist |
| `close-out` | Reconcile built vs. planned, record decisions/deviations, close a phase or whole plan, file follow-ups |
| `explore-designs` | "Design it twice": generate several radically different designs for a decision and compare |
| `architecture-review` | Find structural/testability improvements in existing code → recommendations (RFCs), not code |
| `resolve-architecture-review` | Walk `architecture-review` proposals one at a time → RFCs |

## Deferred plugins (pending vnext rewrite)

These still live under `old/` and are not yet in the marketplace; they will be ported (keeping their names):

- **`decaf`** (core) — `commit`, `note`, `problem-analysis`, `decision-critic`, `incoherence-detector`, `powershell-expert`; agents `architect`, `csharp-developer`, `go-developer`, `debugger`, `planner`, `technical-writer`.
- **`decaf-memory`** — `remember`, `recall`, `init-memory`, `memory-dashboard`, backed by the [erinra MCP server](https://github.com/alphaleonis/erinra) (`claude mcp add erinra -- erinra serve -s user`).
- **`decaf-protection`** — PreToolUse safety hooks only (`block-op-secrets` blocks 1Password CLI invocations that could leak secrets into the session transcript).

## Conventions

Shared reference files at repo-root `conventions/`, pulled into skills and agents via `@file` references:

| Convention | Used by |
|------------|---------|
| `code-review-consolidation.md` | `decaf-quality` — `code-review` |
| `coverage-config.md` | `decaf-quality` — `coverage-review` |
| `refactoring.md` | `decaf-quality` — `refactor` |
| `severity.md`, `intent-markers.md`, `structural.md`, `temporal.md`, `security.md`, `code-quality/` | `decaf-quality` — review agents |
| `documentation.md` | `decaf-quality` — documentation guidance |
| `pr-etiquette.md` | `decaf-quality` — `resolve-pr-feedback`, `code-review` |
| `persona-authoring.md` | `decaf-quality` — reviewer-persona authoring |
| `work-items.md` | `decaf-plan` — planning skills (tracker detection / work-item creation) |

### Development: sharing conventions across plugins (symlinks)

**Installed plugins cannot read files outside their own directory.** When a plugin is installed from a marketplace, Claude Code copies *only that plugin's own subtree* into `~/.claude/plugins/cache/<marketplace>/<plugin>/<sha>/` and runs from there — the rest of the repo (including the repo-root `conventions/`) is **not** present. So a skill reference that escapes the plugin root, e.g. `@../../../conventions/work-items.md`, resolves fine when run from this repo but **silently fails once the plugin is installed** (the file simply isn't in the cache). See the docs: [Plugin caching and file resolution](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution).

The fix is the **symlink pattern** (the officially recommended way to share files within a marketplace):

- The repo keeps **one canonical copy** of every convention at repo-root `conventions/`.
- Each plugin that uses a convention has a `<plugin>/conventions/` directory containing **symlinks** into the repo-root copy — e.g. `decaf-plan/conventions/work-items.md → ../../conventions/work-items.md`. Git stores these as symlinks (no duplicated content).
- On install, Claude Code **dereferences** symlinks whose target is elsewhere in the same marketplace and copies the real content into the plugin's cache, so the reference resolves at runtime.
- Skills/agents therefore always reference conventions by the **plugin-local** path: `@../../conventions/<file>.md` from `skills/<skill>/SKILL.md` (or `@../conventions/<file>.md` from `agents/<agent>.md`) — never a path that climbs out of the plugin.

To give a plugin a convention:

```bash
mkdir -p <plugin>/conventions
ln -s ../../conventions/<file>.md <plugin>/conventions/<file>.md   # relative; target must stay inside the repo
```

Edit conventions in **one place** (repo-root `conventions/`); every plugin's symlink sees the change. Caveat: symlinks require `git config core.symlinks true` — automatic on Linux/macOS/WSL; on native Windows it needs Developer Mode or an elevated `git clone -c core.symlinks=true`.

## License

MIT
