---
name: commit
description: Stage, commit, and optionally push changes. Checks project conventions for commit message format and topic branch requirements.
argument-hint: "[push] [topic]"
---

# /commit

You have been invoked as the `/commit` skill. The user's arguments are: $ARGUMENTS

## Parse arguments

Check `$ARGUMENTS` for these keywords (order-independent, combinable):

- **`push`** — after committing, push to the remote
- **`topic`** — create a topic branch before committing

## Step 1: Understand the changes

Run in parallel:

```bash
git status
```

```bash
git diff --stat && git diff
```

```bash
git diff --cached --stat && git diff --cached
```

```bash
git branch --show-current
```

```bash
git log --oneline -5
```

If there are no staged or unstaged changes and no untracked files (working tree clean), tell the user there is nothing to commit and stop.

## Step 2: Check branch situation

Determine the current branch. A branch is a "main branch" if it is named `main` or `master`.

### Read project CLAUDE.md

Read the CLAUDE.md in the project root (the git working directory, NOT this plugin's CLAUDE.md). If it exists, look for:

1. **Commit message conventions** — instructions about commit message format, prefixes (conventional commits, etc.), or style. Store for Step 4.
2. **Topic branch requirements** — phrases like "always use topic branches", "never commit directly to main", "use feature branches", or similar.

### Decide on topic branch

| Situation | Action |
|-----------|--------|
| `topic` argument present | Create a topic branch |
| Already on a non-main branch | Commit normally (no branch change) |
| Project CLAUDE.md requires topic branches AND on main | Ask user if a topic branch should be created |
| Ambiguous about branches AND on main | Ask user |
| No topic branch instructions AND on main | Commit directly without asking |

### Create topic branch (when needed)

Auto-generate a short branch name from the changes (e.g., `fix-validation-error`, `add-user-export`). Keep it under 40 characters, lowercase, hyphenated. Do not ask the user for the name.

```bash
git checkout -b <branch-name>
```

## Step 3: Stage files

Stage all changed and untracked files by name. Do NOT use `git add -A` or `git add .`.

**Skip these files** (never stage them):

- `.env`, `.env.*`
- Files with `credential`, `secret`, or `key` in their name (e.g., `credentials.json`, `secrets.yaml`)
- `*.pem`, `*.key`, `*.p12`, `*.pfx`

If files were skipped, tell the user which ones and why.

## Step 4: Commit

Generate a concise commit message:

- If the project CLAUDE.md specifies a commit message format: follow it
- Otherwise: one-line summary focused on the "why", not the "what". Lowercase start, no trailing period. Under 72 characters. Add a body after a blank line only if the change warrants explanation.

Do NOT add a `Co-Authored-By` line. Do NOT use `--amend`.

```bash
git commit -m "$(cat <<'EOF'
<message>
EOF
)"
```

## Step 5: Push (if requested)

If `push` was in the arguments:

```bash
# If the branch has no upstream yet
git push -u origin <branch-name>

# If upstream is already set
git push
```

## Step 6: Confirm

Report what was done:

```
Committed: <short hash> <first line of message>
Branch: <branch name>
```

If push was performed, add: `Pushed to origin/<branch>`
