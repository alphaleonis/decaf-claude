# CLAUDE.md

Personal Claude Code configuration with five plugins: `decaf` (core), `decaf-review` (code review ecosystem), and three memory plugins (install one).

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
| `handle-cr` | Both | Walk through code review findings interactively |
| `handle-coverage` | Both | Walk through coverage gaps interactively, writing tests |
| `handle-refactoring` | Both | Walk through refactoring opportunities interactively |

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

### `decaf-memory-mcp` — Memory (server-memory)

Memory skills backed by [@modelcontextprotocol/server-memory](https://github.com/modelcontextprotocol/servers/tree/main/src/memory). Simple JSONL-based knowledge graph with keyword search. Requires the MCP server to be configured separately.

### `decaf-memory-vestige` — Memory (Vestige) **RECOMMENDED**

Memory skills backed by [Vestige](https://github.com/samvallad33/vestige) ([fork](https://github.com/alphaleonis/vestige)). FSRS-6 spaced repetition, hybrid semantic search (vector + keyword + HyDE), automatic deduplication via prediction error gating, memory decay, and 3D visualization dashboard. Requires the Vestige MCP server (`vestige-mcp`) to be configured separately.

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `remember` | Both | Store a memory via `smart_ingest` (auto-dedup) |
| `recall` | Both | Search memories via semantic search |
| `vestige-init` | Claude only | Session startup, proactive memory behaviors, trigger words |

### `decaf-memory-doobidoo` — Memory (mcp-memory-service) **DEPRECATED**

Memory skills backed by mcp-memory-service (doobidoo). The upstream repository has been suspended. Use `decaf-memory-vestige` instead.

**Install one memory plugin.** The legacy plugins (`decaf-memory-mcp`, `decaf-memory-doobidoo`) provide:

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `remember` | Both | Store a pattern in the knowledge graph (delegates to add-memory) |
| `recall` | Both | Search the knowledge graph for stored patterns |
| `add-memory` | Both | Store patterns in knowledge graph (backing for /remember) |
| `pattern-memory` | Claude only | Auto-query/store knowledge graph |

## Installation

### As a Local Marketplace

```bash
# 1. From the plugin directory, register as a marketplace
/plugin marketplace add ./

# 2. Install plugins
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
/plugin install decaf-claude-config@decaf-memory-vestige   # recommended (or decaf-memory-mcp, decaf-memory-doobidoo)

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
├── decaf-memory-mcp/             # Memory plugin (server-memory)
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-memory-mcp"
│   └── skills/                   # 4 skills
├── decaf-memory-vestige/          # Memory plugin (Vestige) — recommended
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-memory-vestige"
│   └── skills/                   # 3 skills
├── decaf-memory-doobidoo/        # Memory plugin (mcp-memory-service) — deprecated
│   ├── .claude-plugin/
│   │   └── plugin.json           # name: "decaf-memory-doobidoo"
│   └── skills/                   # 4 skills
├── CLAUDE.md
└── README.md
```

## Updating the Plugin

After pushing changes to this repo, update the cached marketplace so Claude Code sees the new version:

```bash
git -C ~/.claude/plugins/marketplaces/decaf-claude-config pull
claude plugin install decaf@decaf-claude-config
claude plugin install decaf-review@decaf-claude-config
claude plugin install decaf-memory-vestige@decaf-claude-config  # recommended (or decaf-memory-mcp, decaf-memory-doobidoo)
```

Then restart Claude Code to load the updated plugins.

## Versioning

These plugins have **no version field** in their `plugin.json` files. Changes take effect on Claude Code restart (continuous deployment via git commits).

## Related Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Original inspiration
