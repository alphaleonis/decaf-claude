---
name: write-comments
description: The rules for writing code comments and doc comments in any language, plus the project's glossary and local rules. Use before writing or editing source code, so new comments follow the rules from the start, or with a target to rewrite the comments already there.
argument-hint: "[file, directory, or 'diff' to rewrite existing comments]"
allowed-tools: Bash(cat:*), Bash(echo:*)
---

# Write comments

You have been invoked as the `write-comments` skill. The user's arguments are: $ARGUMENTS

**Without arguments**, load the rules below and follow them in every comment you write or edit for
the rest of this task. Don't reply with a summary of the rules. Continue the task you were doing.

**With a target** (a file, a directory, or `diff` for the uncommitted changes), rewrite the comments
in the target to the rules. Change only comments and doc comments, never code. Where a comment
names a mechanism, check the claim against the code before you keep it. Report the files changed
and any comment you deleted outright, so the user can restore it.

## The rules

@../../conventions/comments.md

## This project's overlay

The project's `.decaf/conventions/comments.md` follows. Where it contradicts the rules above, it
wins.

!`cat "${CLAUDE_PROJECT_DIR}/.decaf/conventions/comments.md" 2>/dev/null || echo "This project has no overlay."`
