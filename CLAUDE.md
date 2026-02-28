# CLAUDE.md

Personal Claude Code configuration plugin with some useful Agents and Skills for coding.

## Quick Reference

**Plugin name**: `decaf`
**Skills**: Invoked as `/decaf:skill-name` (appear in intellisense)

### Available Skills

| Skill | Invocation | Purpose |
|-------|------------|---------|
| `code-review` | Both | Parallel multi-agent code review with consolidation |
| `coverage-review` | Both | Run code coverage analysis and review gaps for severity |
| `handle-cr` | Both | Walk through code review findings interactively |
| `handle-coverage` | Both | Walk through coverage gaps interactively, writing tests |
| `remember` | Both | Store a pattern in the knowledge graph (delegates to add-memory) |
| `recall` | Both | Search the knowledge graph for stored patterns |
| `add-memory` | Both | Store patterns in knowledge graph (backing for /remember) |
| `decision-critic` | Both | Stress-test decisions through adversarial analysis |
| `incoherence-detector` | Both | Detect doc/code/spec inconsistencies |
| `note` | Both | Capture a follow-up task as a bean without interrupting current work |
| `pattern-memory` | Claude only | Auto-query/store knowledge graph |
| `powershell-expert` | Both | PowerShell development patterns |
| `problem-analysis` | Both | Root cause investigation |

### Available Agents

| Agent | Purpose |
|-------|---------|
| `architect` | Feature architecture design |
| `code-reviewer-broad` | Broad review across 5 categories with confidence scoring |
| `code-reviewer-quick` | Fast generalist: bugs, security, code quality, project conventions (sonnet) |
| `code-reviewer-knowledge` | Knowledge preservation, production risks, RULE 0/1/2 hierarchy |
| `coverage-reviewer` | Assess coverage gap severity and suggest targeted test improvements |
| `csharp-developer` | C# implementation with idiomatic patterns |
| `go-developer` | Go implementation with idiomatic patterns |
| `debugger` | Systematic debugging with evidence gathering |
| `design-reviewer` | System-level design: API contracts, boundaries, concurrency, evolution |
| `planner` | Implementation planning |
| `security-reviewer` | System-level security: threat modeling, missing controls, architectural gaps |
| `spec-compliance-reviewer` | Spec compliance: requirement gaps, deviations, partial implementations, scope creep |
| `technical-writer` | LLM-optimized documentation |
| `test-reviewer` | Test anti-patterns, silent failures, false positives |

## Installation

### As a Local Marketplace

```bash
# 1. From the plugin directory, register as a marketplace
/plugin marketplace add ./

# 2. Install the plugin
/plugin install decaf-claude-config@decaf

# 3. Restart Claude Code to load the plugin
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
│   ├── plugin.json        # Plugin manifest (name: decaf)
│   └── marketplace.json   # Marketplace metadata
├── agents/                # Specialized subagents (14)
├── skills/                # Skills and workflows (13)
└── conventions/           # Shared convention files (@file references)
```

## Versioning

This plugin has **no version field** in `plugin.json`. Changes take effect on Claude Code restart (continuous deployment via git commits).

## Related Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills)
- [Claude Code Plugins Documentation](https://code.claude.com/docs/en/plugins)
- [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — Original inspiration
