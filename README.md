# decaf's Claude Plugin

A personalized Claude Code plugin with specialized agents, skills, and conventions for code review, coverage analysis, and structured decision-making.

Originally forked from [everything-claude-code](https://github.com/affaan-m/everything-claude-code).  You probably want that one rather than this one that has been tailored to my own personal workflow.

## Installation

```bash
# Add as a marketplace
/plugin marketplace add alphaleonis/decaf-claude-config

# Install the plugin
/plugin install decaf-claude-config@decaf
```

Or install from a local clone:

```bash
cd /path/to/decaf-claude-config
/plugin marketplace add ./
/plugin install decaf-claude-config@decaf
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
├── .claude-plugin/        # Plugin and marketplace manifests
├── agents/                # 13 specialized subagents
├── skills/                # 12 interactive skills and workflows
├── conventions/           # Shared convention files (@file references)
└── CLAUDE.md              # Plugin instructions and skill/agent index
```

## Skills

Skills are invoked as `/decaf:<skill-name>`.

| Skill | Description |
|-------|-------------|
| `code-review` | Parallel multi-agent code review with consolidation |
| `coverage-review` | Run code coverage analysis and review gaps for severity |
| `handle-cr` | Walk through code review findings interactively |
| `handle-coverage` | Walk through coverage gaps interactively, writing tests |
| `decision-critic` | Stress-test decisions through adversarial analysis |
| `incoherence-detector` | Detect doc/code/spec inconsistencies |
| `problem-analysis` | Root cause investigation |
| `powershell-expert` | PowerShell development patterns |
| `remember` | Store a pattern in the knowledge graph |
| `recall` | Search the knowledge graph for stored patterns |
| `add-memory` | Store patterns in knowledge graph (backing for remember) |
| `pattern-memory` | Auto-query/store knowledge graph (not user-invocable) |

## Agents

Agents are used internally by skills or can be referenced via the Task tool as `decaf:<agent-name>`.

| Agent | Purpose |
|-------|---------|
| `architect` | Feature architecture design |
| `code-reviewer-broad` | Broad review across 5 categories with confidence scoring |
| `code-reviewer-quick` | Fast generalist: bugs, security, code quality, conventions |
| `code-reviewer-knowledge` | Knowledge preservation, production risks |
| `coverage-reviewer` | Assess coverage gap severity and suggest tests |
| `csharp-developer` | C# implementation with enterprise patterns |
| `debugger` | Systematic debugging with evidence gathering |
| `design-reviewer` | API contracts, boundaries, concurrency, evolution |
| `planner` | Implementation planning |
| `security-reviewer` | Threat modeling, missing controls, architectural gaps |
| `spec-compliance-reviewer` | Requirement gaps, deviations, scope creep |
| `technical-writer` | LLM-optimized documentation |
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
