---
name: note
description: >
  Capture a follow-up idea or task as a nib without interrupting current work.
  Requires a nibs-based task tracking system in the project.
argument-hint: "[parent:<id>] <description>"
allowed-tools: Bash, Read, Grep
---

# /note — Capture a follow-up task

You have been invoked as the `/note` skill. The user's arguments are: $ARGUMENTS

The user wants to quickly capture a thought, idea, or follow-up task without interrupting their current work. Keep the interaction minimal.

## Prerequisites

Verify nibs is available:

```bash
nibs version 2>/dev/null
```

If nibs is not installed or no `.nibs.yml` exists in the project, tell the user:

**No nibs configuration found in this project. `/note` requires a nibs-based task tracking system.**

Then stop.

## Parse arguments

Check if the arguments start with an explicit parent reference:

- `parent:<id>` — explicit parent nib ID (e.g., `parent:proj-a1b2`)

Strip any parent reference from the remaining text — the rest is the note description.

## Find the parent nib

### If an explicit parent was given

Verify it exists:

```bash
nibs show <id> --json --no-mentions
```

If it doesn't exist, tell the user and stop.

### If no explicit parent was given

Determine the best parent from context:

1. **Check for in-progress nibs** — these represent active work streams:

```bash
nibs list --json -s in-progress
```

2. **Select the parent using your judgment**:
   - If exactly one in-progress nib exists, use it
   - If multiple in-progress nibs exist, pick the one most relevant to the note's topic based on conversation context
   - If no in-progress nibs exist, check for `todo` features or epics that match the note's topic
   - If no suitable parent can be determined, create the nib without a parent

## Create the nib

Formulate a concise, descriptive title from the user's note text. Then create the nib:

**With parent:**

```bash
nibs create "<title>" -t task -s todo --parent <parent-id> -d "<description>"
```

**Without parent:**

```bash
nibs create "<title>" -t task -s todo -d "<description>"
```

The description should include:
- The idea or follow-up described by the user, expanded slightly if terse
- A `## Context` section noting what was being discussed (branch, active work, topic from conversation) to preserve the "why" behind the note

## Confirm

Keep the confirmation brief — the user does not want to be interrupted:

**With parent:** `Note <nib-id>: <title> (under <parent-id>)`

**Without parent:** `Note <nib-id>: <title>`
