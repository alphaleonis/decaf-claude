# Documentation Conventions

This is the authoritative documentation conventions file. All code-adjacent
documentation (CLAUDE.md, README.md) must follow these principles.

## Core Principles

**Self-contained documentation**: All code-adjacent documentation (CLAUDE.md,
README.md) must be self-contained. Do NOT reference external authoritative
sources (doc/ directories, wikis, external documentation). If knowledge exists
in an authoritative source, it must be summarized locally. Duplication is
acceptable; the maintenance burden is the cost of locality.

**CLAUDE.md = pure index**: CLAUDE.md files are navigation aids only. They
contain WHAT is in the directory and WHEN to read each file. All explanatory
content (architecture, decisions, invariants) belongs in README.md.

**README.md = invisible knowledge**: README.md files capture knowledge NOT
visible from reading source code. If ANY invisible knowledge exists for a
directory, README.md is required.

## CLAUDE.md Format Specification

### Index Format

Use tabular format with What and When columns:

```markdown
## Files

| File        | What                           | When to read                              |
| ----------- | ------------------------------ | ----------------------------------------- |
| `cache.rs`  | LRU cache with O(1) operations | Implementing caching, debugging evictions |
| `errors.rs` | Error types and Result aliases | Adding error variants, handling failures  |

## Subdirectories

| Directory   | What                          | When to read                              |
| ----------- | ----------------------------- | ----------------------------------------- |
| `config/`   | Runtime configuration loading | Adding config options, modifying defaults |
| `handlers/` | HTTP request handlers         | Adding endpoints, modifying request flow  |
```

### Column Guidelines

- **File/Directory**: Use backticks around names: `cache.rs`, `config/`
- **What**: Factual description of contents (nouns, not actions)
- **When to read**: Task-oriented triggers using action verbs (implementing,
  debugging, modifying, adding, understanding)
- At least one column must have content; empty cells use `-`

### Trigger Quality Test

Given task "add a new validation rule", can an LLM scan the "When to read"
column and identify the right file?

### Generated and Vendored Code

CLAUDE.md MUST flag files/directories that should not be manually edited:

| Directory      | What                              | When to read         |
| -------------- | --------------------------------- | -------------------- |
| `proto/gen/`   | Generated from proto/. Run `make` | Never edit directly  |
| `vendor/`      | Vendored deps, upstream: go.mod   | Never edit directly  |
| `third_party/` | Copied from github.com/foo v1.2.3 | Never edit directly  |

The "When to read" column should indicate these are not editable. Include
regeneration commands in the "What" column or in a dedicated Regenerate section.

This prevents LLMs from wasting effort analyzing or "improving" auto-generated
code, and prevents edits that will be overwritten or cause merge conflicts.

See also: conventions/code-quality/baseline.md "Generated and Vendored Code Awareness".

### ROOT vs SUBDIRECTORY CLAUDE.md

**ROOT CLAUDE.md:**

```markdown
# [Project Name]

[One sentence: what this is]

## Files

| File | What | When to read |
| ---- | ---- | ------------ |

## Subdirectories

| Directory | What | When to read |
| --------- | ---- | ------------ |

## Build

[Copy-pasteable command]

## Test

[Copy-pasteable command]

## Development

[Setup instructions, environment requirements, workflow notes]
```

**SUBDIRECTORY CLAUDE.md:**

```markdown
# [directory-name]/

## Files

| File | What | When to read |
| ---- | ---- | ------------ |

## Subdirectories

| Directory | What | When to read |
| --------- | ---- | ------------ |
```

**Critical constraint:** CLAUDE.md files are navigation aids, not explanatory
documents. They contain:

- File/directory index (REQUIRED): tabular format with What/When columns
- One-sentence overview (OPTIONAL): what this directory is
- Operational sections (OPTIONAL): Build, Test, Regenerate, Deploy, or similar
  commands specific to this directory's artifacts

They do NOT contain:

- Architectural explanations (-> README.md)
- Design decisions or rationale (-> README.md)
- Invariants or constraints (-> README.md)
- Multi-paragraph prose (-> README.md)

Operational sections must be copy-pasteable commands with minimal context, not
explanatory prose about why the build works a certain way.

## README.md Specification

### Creation Criteria (Invisible Knowledge Test)

Create README.md when the directory contains ANY invisible knowledge --
knowledge NOT visible from reading the code:

- Planning decisions (from Decision Log during implementation)
- Business context (why the product works this way)
- Architectural rationale (why this structure)
- Trade-offs made (what was sacrificed for what)
- Invariants (rules that must hold but aren't in types)
- Historical context (why not alternatives)
- Performance characteristics (non-obvious efficiency properties)
- Multiple components interact through non-obvious contracts
- The directory's structure encodes domain knowledge
- Failure modes or edge cases aren't apparent from reading individual files
- "Rules" developers must follow that aren't enforced by compiler/linter

**README.md is required if ANY of the above exist.** The trigger is semantic
(presence of invisible knowledge), not structural (file count, complexity).

**DO NOT create README.md when:**

- The directory is purely organizational with no decisions behind its structure
- All knowledge is visible from reading source code
- You'd only be restating what code already shows

### Content Test

For each sentence in README.md, ask: "Could a developer learn this by reading
the source files?"

- If YES: delete the sentence
- If NO: keep it

README.md earns its tokens by providing INVISIBLE knowledge: the reasoning
behind the code, not descriptions of the code.

### README.md Structure

```markdown
# [Component Name]

## Overview

[One paragraph: what problem this solves, high-level approach]

## Architecture

[How sub-components interact; data flow; key abstractions]

## Design Decisions

[Tradeoffs made and why; alternatives considered]

## Invariants

[Rules that must be maintained; constraints not enforced by code]
```
