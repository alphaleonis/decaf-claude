---
name: improve-codebase-architecture
description: Explore a codebase to find opportunities for architectural improvement, focusing on making the codebase more testable by deepening shallow modules. Use when user wants to improve architecture, find refactoring opportunities, consolidate tightly-coupled modules, or make a codebase more AI-navigable.
---

# Improve Codebase Architecture

Explore a codebase like an AI would, surface architectural friction, discover opportunities for improving testability, and propose module-deepening refactors.

A **deep module** (John Ousterhout, "A Philosophy of Software Design") has a small interface hiding a large implementation. Deep modules are more testable, more AI-navigable, and let you test at the boundary instead of inside.

## Process

### 1. Explore the codebase

Use the Agent tool with subagent_type=Explore to navigate the codebase naturally. Do NOT follow rigid heuristics — explore organically and note where you experience friction:

- Where does understanding one concept require bouncing between many small files?
- Where are modules so shallow that the interface is nearly as complex as the implementation?
- Where have pure functions been extracted just for testability, but the real bugs hide in how they're called?
- Where do tightly-coupled modules create integration risk in the seams between them?
- Which parts of the codebase are untested, or hard to test?

The friction you encounter IS the signal.

Also identify the project language and its idiomatic interface patterns — designs produced later must be expressed in this language.

### 2. Present candidates

Present a numbered list of deepening opportunities to the user. For each candidate, show:

- **Cluster**: Which modules/concepts are involved
- **Why they're coupled**: Shared types, call patterns, co-ownership of a concept
- **Dependency category**: See [REFERENCE.md](REFERENCE.md) for the four categories
- **Test impact**: What existing tests would be replaced by boundary tests

### 3. Save candidates file

Save the full exploration results to a timestamped file. **Never overwrite existing files.**

**Filename**: `.architecture-improvements/CANDIDATES_<YYYY-MM-DD>_<HH-MM-SS>.md` using the current date and time from context. Do NOT shell out to `date`. Create the `.architecture-improvements/` directory first if it doesn't exist.

**File format:**

```markdown
# Architecture Improvement Candidates

**Date**: <YYYY-MM-DD>
**Project language**: <language>
**Idiomatic patterns**: <summary of interface conventions discovered during exploration>

---

## #1 <Cluster name>

**Modules**: `path/to/A`, `path/to/B`, `path/to/C`
**Why coupled**: <explanation of shared types, call patterns, co-ownership>
**Dependency category**: <In-process | Local-substitutable | Remote but owned | True external>
**Test impact**: <what existing tests would be replaced by boundary tests>

**Exploration notes**: <additional context from exploration that would help frame the problem space — e.g., key types, call patterns observed, where the friction was felt>

---

## #2 <Cluster name>
...
```

Include ALL candidates — do not filter by quality. The handler skill lets the user decide which to pursue and which to skip.

### Output Notification

After saving the candidates file, inform the user:

```
✅ Architecture exploration complete: .architecture-improvements/CANDIDATES_<timestamp>.md

Found N deepening opportunities.

Run /decaf-experimental:handle-architecture-improvements to walk through candidates and create RFCs.
```
