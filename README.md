# decaf's Claude Plugins

Personalized Claude Code plugins with specialized agents, skills, and conventions for development and code review.

Originally forked from [everything-claude-code](https://github.com/affaan-m/everything-claude-code).  You probably want that one rather than this one that has been tailored to my own personal workflow.

## Plugins

This repo provides two plugins that can be installed independently:

| Plugin | Description |
|--------|-------------|
| **`decaf`** | General-purpose agents and skills (memory, analysis, development) |
| **`decaf-review`** | Multi-agent code review and coverage analysis |

## Installation

```bash
# Add as a marketplace
/plugin marketplace add alphaleonis/decaf-claude-config

# Install one or both plugins
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
```

Or install from a local clone:

```bash
cd /path/to/decaf-claude-config
/plugin marketplace add ./
/plugin install decaf-claude-config@decaf
/plugin install decaf-claude-config@decaf-review
```

### Optional: Memory MCP Server

Some skills (`remember`, `recall`, `add-memory`, `pattern-memory`) require the [Memory MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory) for cross-project pattern storage.

```bash
claude mcp add --transport stdio memory -- bun x @modelcontextprotocol/server-memory
```

To configure a persistent storage location:

```bash
claude mcp add --transport stdio memory -- bun x @modelcontextprotocol/server-memory --memory-path ~/.claude/memory.jsonl
```

## What's Inside

```
decaf-claude-config/
├── .claude-plugin/               # Marketplace manifest
├── conventions/                  # Shared convention files (@file references)
├── decaf/                        # Core plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # 6 agents
│   └── skills/                   # 9 skills
├── decaf-review/                 # Review plugin
│   ├── .claude-plugin/plugin.json
│   ├── agents/                   # 8 agents
│   └── skills/                   # 4 skills
├── CLAUDE.md
└── README.md
```

## `decaf` — Core Skills

Skills are invoked as `/decaf:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `decision-critic` | Stress-test decisions through adversarial analysis |
| `incoherence-detector` | Detect doc/code/spec inconsistencies |
| `problem-analysis` | Root cause investigation |
| `powershell-expert` | PowerShell development patterns |
| `remember` | Store a pattern in the knowledge graph |
| `recall` | Search the knowledge graph for stored patterns |
| `add-memory` | Store patterns in knowledge graph (backing for remember) |
| `pattern-memory` | Auto-query/store knowledge graph (not user-invocable) |
| `note` | Capture a follow-up task as a bean |

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
| `handle-cr` | Walk through code review findings interactively |
| `handle-coverage` | Walk through coverage gaps interactively, writing tests |

## `decaf-review` — Review Agents

Agents are referenced via the Task tool as `decaf-review:<agent-name>`.

| Agent | Purpose |
|-------|---------|
| `code-reviewer-broad` | Broad review across 5 categories with confidence scoring |
| `code-reviewer-quick` | Fast generalist: bugs, security, code quality, conventions |
| `code-reviewer-knowledge` | Knowledge preservation, production risks |
| `coverage-reviewer` | Assess coverage gap severity and suggest tests |
| `design-reviewer` | API contracts, boundaries, concurrency, evolution |
| `security-reviewer` | Threat modeling, missing controls, architectural gaps |
| `spec-compliance-reviewer` | Requirement gaps, deviations, scope creep |
| `test-reviewer` | Test anti-patterns, silent failures, false positives |

## Conventions

Shared reference files used by skills and agents via `@file` references:

| Convention | Used by |
|------------|---------|
| `code-review-consolidation.md` | `code-review` skill |
| `coverage-config.md` | `coverage-review` skill |
| `severity.md` | Review agents |
| `security.md` | Security reviewer |
| `code-quality/` | Code review agents |
| `structural.md` | Code review agents |
| `temporal.md` | Code review agents |
| `documentation.md` | Technical writer |
| `intent-markers.md` | Code review agents |

## License

MIT
