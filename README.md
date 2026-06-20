# decaf's Claude Plugins

Personalized Claude Code plugins with specialized agents, skills, and conventions for development and code review.

Originally forked from [everything-claude-code](https://github.com/affaan-m/everything-claude-code).  You probably want that one rather than this one that has been tailored to my own personal workflow.

## Plugins

This repo provides six plugins that can be installed independently:

| Plugin | Description |
|--------|-------------|
| **`decaf`** | General-purpose agents and skills (analysis, development) |
| **`decaf-review`** | Multi-agent code review, coverage analysis, and refactoring |
| **`decaf-planning`** | Planning skills for PRDs, implementation plans, and phase breakdowns |
| **`decaf-memory`** | Memory skills backed by [erinra](https://github.com/alphaleonis/erinra-mcp) (hybrid semantic search, knowledge graphs) |
| **`decaf-dev`** | Development skills — TDD, automated dev with review |
| **`decaf-protection`** | PreToolUse safety hooks — blocks commands that would leak secrets into the session |

## Installation

```bash
# Add as a marketplace
/plugin marketplace add alphaleonis/decaf-claude-config

# Install plugins
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
/plugin install decaf-claude-config@decaf-planning
/plugin install decaf-claude-config@decaf-memory
/plugin install decaf-claude-config@decaf-dev
/plugin install decaf-claude-config@decaf-protection
```

Or install from a local clone:

```bash
cd /path/to/decaf-claude-config
/plugin marketplace add ./
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
/plugin install decaf-claude-config@decaf-planning
/plugin install decaf-claude-config@decaf-memory
/plugin install decaf-claude-config@decaf-dev
/plugin install decaf-claude-config@decaf-protection
```

### Memory Plugin Setup

Memory skills require the [erinra MCP server](https://github.com/alphaleonis/erinra-mcp). See the erinra repo for installation options.

```bash
# Install erinra — see https://github.com/alphaleonis/erinra-mcp#installation

# Register the MCP server
claude mcp add erinra -- erinra serve -s user

# Install the plugin
/plugin install decaf-claude-config@decaf-memory
```

## What's Inside

```
decaf-claude-config/
├── .claude-plugin/               # Marketplace manifest
├── conventions/                  # Shared convention files (@file references)
├── decaf/                        # Core plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # 6 agents
│   └── skills/                   # 6 skills
├── decaf-review/                 # Review plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # 10 agents
│   └── skills/                   # 6 skills
├── decaf-planning/               # Planning plugin
│   ├── .claude-plugin/plugin.json
│   └── skills/                   # 9 skills
├── decaf-memory/                 # Memory plugin (erinra)
│   ├── .claude-plugin/plugin.json
│   └── skills/                   # 4 skills
├── decaf-dev/                    # Development plugin
│   ├── .claude-plugin/plugin.json
│   └── skills/                   # 3 skills
├── decaf-protection/             # Safety hooks plugin
│   ├── .claude-plugin/plugin.json
│   └── hooks/                    # PreToolUse guardrails
├── CLAUDE.md
└── README.md
```

## `decaf` — Core Skills

Skills are invoked as `/decaf:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `commit` | Stage, commit, and optionally push changes |
| `decision-critic` | Stress-test decisions through adversarial analysis |
| `incoherence-detector` | Detect doc/code/spec inconsistencies |
| `note` | Capture a follow-up task as a nib without interrupting current work |
| `powershell-expert` | PowerShell development patterns |
| `problem-analysis` | Root cause investigation |

## `decaf` — Core Agents

Agents are referenced via the Task tool as `decaf:<agent-name>`.

| Agent | Purpose |
|-------|---------|
| `architect` | Feature architecture design |
| `csharp-developer` | C# implementation with idiomatic patterns |
| `go-developer` | Go implementation with idiomatic patterns |
| `debugger` | Systematic debugging with evidence gathering |
| `planner` | Implementation planning |
| `technical-writer` | LLM-optimized documentation |

## `decaf-review` — Review Skills

Skills are invoked as `/decaf-review:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `code-review` | Parallel multi-agent code review with consolidation |
| `coverage-review` | Run code coverage analysis and review gaps for severity |
| `refactor` | Analyze code for structural improvement opportunities and produce a prioritized plan |
| `handle-cr` | Walk through code review findings interactively |
| `handle-coverage` | Walk through coverage gaps interactively, writing tests |
| `handle-refactoring` | Walk through refactoring opportunities interactively |

## `decaf-review` — Review Agents

Agents are referenced via the Task tool as `decaf-review:<agent-name>`.

| Agent | Purpose |
|-------|---------|
| `code-reviewer-broad` | Broad review across 5 categories with confidence scoring |
| `code-reviewer-quick` | Fast generalist: bugs, security, code quality, project conventions |
| `code-reviewer-knowledge` | Knowledge preservation, production risks, RULE 0/1/2 hierarchy |
| `coherence-analyst` | Cross-file structural patterns: duplication, naming consistency, interface drift, module boundaries |
| `coverage-reviewer` | Assess coverage gap severity and suggest targeted test improvements |
| `design-reviewer` | System-level design: API contracts, boundaries, concurrency, evolution |
| `security-reviewer` | System-level security: threat modeling, missing controls, architectural gaps |
| `spec-compliance-reviewer` | Spec compliance: requirement gaps, deviations, partial implementations, scope creep |
| `structural-analyst` | Per-file structural quality: naming, composition, complexity, domain modeling, error handling |
| `test-reviewer` | Test anti-patterns, silent failures, false positives |

## `decaf-memory` — Memory Skills

Skills are invoked as `/decaf-memory:<skill-name>`. Requires the [erinra MCP server](https://github.com/alphaleonis/erinra-mcp).

| Skill | Description |
|-------|-------------|
| `init-memory` | Manually load erinra session context (fallback when the hook doesn't trigger) |
| `remember` | Store a memory via erinra (LLM-driven dedup) |
| `recall` | Search memories via hybrid semantic search |
| `memory-dashboard` | Open the erinra memory dashboard in the browser |

## `decaf-planning` — Planning Skills

Skills are invoked as `/decaf-planning:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `research` | Explore an unfamiliar problem space through multi-phase parallel research with synthesis |
| `grill-me` | Stress-test a plan or design through depth-first interviewing with progress tracking |
| `write-a-prd` | Create a PRD through user interview and codebase exploration |
| `prd-to-plan` | Break a PRD into phased vertical slices and create work items (GitHub, Azure DevOps, Nibs, or markdown) |
| `breakdown-phase` | Break a plan phase (epic) into implementable features with acceptance criteria |
| `close-plan` | Reconcile planned vs. actual, record deviations, and close a phase or plan |
| `design-an-interface` | Generate multiple radically different interface designs using parallel sub-agents ("Design It Twice") |
| `improve-codebase-architecture` | Explore codebase for module-deepening opportunities and save candidates |
| `handle-architecture-improvements` | Walk through architecture improvement candidates interactively, creating RFCs |

## `decaf-protection` — Safety Hooks

No skills or agents — just PreToolUse hooks. Installs automatically once the plugin is enabled; no configuration required.

| Hook | Event | Description |
|------|-------|-------------|
| `block-op-secrets` | `PreToolUse` (Bash) | Blocks 1Password CLI invocations (`op read`, `op item get`, `op inject`, `op run`, `op document get`, `op signin`, …) that may emit secret values into the session. Allowlist: `op --version`, `op --help`, `op whoami`. Uses exit code 2, so the block holds under `--dangerously-skip-permissions`. |

If the operator needs to run `op` (e.g. to prime the 1Password desktop approval before an Ansible run), they should run it themselves in their own shell using the `!` prefix in the Claude Code prompt, e.g. `! op read "op://Vault/Item/field" > /dev/null` — that bypasses the Bash tool entirely and nothing lands in the session transcript.

## `decaf-dev` — Development Skills

Skills are invoked as `/decaf-dev:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `tdd` | Test-driven development with red-green-refactor loop (C#, Go, Rust, and others) |
| `auto-tdd` | TDD-first development with automated review: plan → red-green-refactor → auto-review loop |
| `auto-dev` | Direct development with automated review: plan → implement → auto-review loop (for non-testable work) |

## Conventions

Shared reference files used by skills and agents via `@file` references:

| Convention | Used by |
|------------|---------|
| `code-review-consolidation.md` | `code-review` skill |
| `coverage-config.md` | `coverage-review` skill |
| `refactoring.md` | `refactor` skill |
| `work-items.md` | `prd-to-plan`, `breakdown-phase`, `write-a-prd`, `handle-refactoring`, `handle-architecture-improvements` skills |
| `severity.md` | Review agents |
| `security.md` | Security reviewer |
| `code-quality/` | Code review agents |
| `structural.md` | Code review agents |
| `temporal.md` | Code review agents |
| `documentation.md` | Technical writer |
| `intent-markers.md` | Code review agents |

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
