# CLAUDE.md

Personal Claude Code configuration with five plugins: `decaf` (core), `decaf-review` (code review ecosystem), `decaf-planning` (planning), `decaf-memory` (memory), and `decaf-experimental` (experimental).

## Plugins

### `decaf` — Core

General-purpose agents and skills for development workflows.

**Skills** (invoked as `/decaf:skill-name`):

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `decision-critic` | Both | Stress-test decisions through adversarial analysis |
| `incoherence-detector` | Both | Detect doc/code/spec inconsistencies |
| `note` | Both | Capture a follow-up task as a bean without interrupting current work |
| `powershell-expert` | Both | PowerShell development patterns |
| `problem-analysis` | Both | Root cause investigation |

**Agents** (referenced as `decaf:agent-name`):

| Agent | Purpose |
|-------|---------|
| `architect` | Feature architecture design |
| `csharp-developer` | C# implementation with idiomatic patterns |
| `go-developer` | Go implementation with idiomatic patterns |
| `debugger` | Systematic debugging with evidence gathering |
| `planner` | Implementation planning |
| `technical-writer` | LLM-optimized documentation |

### `decaf-review` — Code Review

Multi-agent code review, coverage analysis, and refactoring.

**Skills** (invoked as `/decaf-review:skill-name`):

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `code-review` | Both | Parallel multi-agent code review with consolidation |
| `coverage-review` | Both | Run code coverage analysis and review gaps for severity |
| `refactor` | Both | Analyze code for structural improvement opportunities and produce a prioritized plan |
| `handle-cr` | Both | Walk through code review findings interactively, or use `auto` for autonomous fixing with TDD |
| `handle-coverage` | Both | Walk through coverage gaps interactively, writing tests |
| `handle-refactoring` | Both | Walk through refactoring opportunities interactively |
| `auto-review` | Both | Automated review-fix-recheck loop: reviews, triages, fixes via subagent, re-reviews until stable |

**Agents** (referenced as `decaf-review:agent-name`):

| Agent | Purpose |
|-------|---------|
| `code-reviewer-broad` | Broad review across 5 categories with confidence scoring |
| `code-reviewer-quick` | Fast generalist: bugs, security, code quality, project conventions (sonnet) |
| `code-reviewer-knowledge` | Knowledge preservation, production risks, RULE 0/1/2 hierarchy |
| `coherence-analyst` | Cross-file structural patterns: duplication, naming consistency, interface drift, module boundaries |
| `coverage-reviewer` | Assess coverage gap severity and suggest targeted test improvements |
| `design-reviewer` | System-level design: API contracts, boundaries, concurrency, evolution |
| `security-reviewer` | System-level security: threat modeling, missing controls, architectural gaps |
| `spec-compliance-reviewer` | Spec compliance: requirement gaps, deviations, partial implementations, scope creep |
| `structural-analyst` | Per-file structural quality: naming, composition, complexity, domain modeling, error handling |
| `test-reviewer` | Test anti-patterns, silent failures, false positives |

### `decaf-memory` — Memory (Vestige)

Memory skills backed by [Vestige](https://github.com/samvallad33/vestige) ([fork](https://github.com/alphaleonis/vestige)). FSRS-6 spaced repetition, hybrid semantic search (vector + keyword + HyDE), automatic deduplication via prediction error gating, memory decay, and 3D visualization dashboard. Requires the Vestige MCP server (`vestige-mcp` or `vestige-sync`) to be configured separately.

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `init-memory` | Both | Manually load Vestige session context (fallback when the hook doesn't trigger the call) |
| `remember` | Both | Store a memory via `smart_ingest` (auto-dedup) |
| `recall` | Both | Search memories via semantic search |
| `memory-dashboard` | Both | Open the Vestige 3D memory dashboard in the browser |

A `SessionStart` hook automatically loads user preferences, project context, and memory protocol on every session start, resume, clear, and context compaction. If the model doesn't act on it, use `/init-memory` as a manual fallback.

### `decaf-planning` — Planning

Planning skills for PRDs, implementation plans, and phase breakdowns.

**Skills** (invoked as `/decaf-planning:skill-name`):

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `research` | Both | Explore an unfamiliar problem space through multi-phase parallel research with synthesis |
| `grill-me` | Both | Stress-test a plan or design through depth-first interviewing with progress tracking |
| `write-a-prd` | Both | Create a PRD through user interview and codebase exploration |
| `prd-to-plan` | Both | Break a PRD into phased vertical slices and create work items (GitHub, Azure DevOps, Beans, or markdown) |
| `breakdown-phase` | Both | Break a plan phase (epic) into implementable features with acceptance criteria |
| `close-plan` | Both | Reconcile planned vs. actual, record deviations, and close a phase or plan |

### `decaf-experimental` — Experimental

Experimental skills being tested before promotion to core plugins.

**Skills** (invoked as `/decaf-experimental:skill-name`):

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `tdd` | Both | Test-driven development with red-green-refactor loop (C#, Go, Rust, and others) |
| `auto-tdd` | Both | TDD-first development with automated review: plan → red-green-refactor → auto-review loop |
| `auto-dev` | Both | Direct development with automated review: plan → implement → auto-review loop (for non-testable work) |
| `design-an-interface` | Both | Generate multiple radically different interface designs using parallel sub-agents ("Design It Twice") |
| `improve-codebase-architecture` | Both | Explore codebase for module-deepening opportunities and save candidates |
| `handle-architecture-improvements` | Both | Walk through architecture improvement candidates interactively, creating RFCs |

## Installation

### As a Local Marketplace

```bash
# 1. From the plugin directory, register as a marketplace
/plugin marketplace add ./

# 2. Install plugins
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
/plugin install decaf-claude-config@decaf-planning
/plugin install decaf-claude-config@decaf-memory
/plugin install decaf-claude-config@decaf-experimental

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
decaf-claude-config/
├── .claude-plugin/
│   └── marketplace.json          # Lists all plugins
├── conventions/                  # Shared convention files (@file references)
├── decaf/                        # Core plugin
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf"
│   ├── agents/                   # 6 agents
│   └── skills/                   # 5 skills
├── decaf-review/                 # Review plugin
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-review"
│   ├── agents/                   # 10 agents
│   └── skills/                   # 6 skills
├── decaf-planning/               # Planning plugin
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-planning"
│   └── skills/                   # 6 skills
├── decaf-memory/                 # Memory plugin (Vestige)
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-memory"
│   └── skills/                   # 4 skills
├── decaf-experimental/           # Experimental plugin
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-experimental"
│   └── skills/                   # 5 skills
├── CLAUDE.md
└── README.md
```

## Updating the Plugin

After pushing changes to this repo, update the cached marketplace so Claude Code sees the new version:

```bash
git -C ~/.claude/plugins/marketplaces/decaf-claude-config pull
claude plugin install decaf@decaf-claude-config
claude plugin install decaf-review@decaf-claude-config
claude plugin install decaf-planning@decaf-claude-config
claude plugin install decaf-memory@decaf-claude-config
claude plugin install decaf-experimental@decaf-claude-config
```

Then restart Claude Code to load the updated plugins.

## Versioning

These plugins have **no version field** in their `plugin.json` files. Changes take effect on Claude Code restart (continuous deployment via git commits).

## Related Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Original inspiration
