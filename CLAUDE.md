# CLAUDE.md

Personal Claude Code configuration with four plugins: `decaf` (core), `decaf-review` (code review ecosystem), and two memory plugins (install one, not both).

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

### `decaf-memory-doobidoo` — Memory (mcp-memory-service)

Memory skills backed by [mcp-memory-service](https://github.com/doobidoo/mcp-memory-service). SQLite-vec storage with semantic search via local embeddings (MiniLM-L6-v2), knowledge graph with typed relationships, and autonomous consolidation. Requires the MCP server to be configured separately.

**Install one memory plugin, not both.** Both provide the same skills:

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
/plugin install decaf-claude-config@decaf-memory-doobidoo  # or decaf-memory-mcp

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
├── decaf-memory-doobidoo/        # Memory plugin (mcp-memory-service)
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
claude plugin install decaf-memory-doobidoo@decaf-claude-config  # or decaf-memory-mcp
```

Then restart Claude Code to load the updated plugins.

## Versioning

These plugins have **no version field** in their `plugin.json` files. Changes take effect on Claude Code restart (continuous deployment via git commits).

## Related Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Original inspiration
