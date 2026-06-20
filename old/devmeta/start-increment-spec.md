---
description: Start a new increment (global) — create directory, overview, interactive scope
argument-hint: [increment-title]
---

## Project Context

Read `.devmeta/devmeta.md` from the project root if it exists. It provides
project-specific test commands, environment checks, and additional rules.

If no `.devmeta/devmeta.md` exists:
- Testing: look for `package.json` test scripts
- Environment: skip checks
- Additional rules: none

---

## Context

- Today's date: !`date +%Y-%m-%d`
- Increment title argument: $ARGUMENTS

## Your Task

Create a new increment directory with a properly structured `_overview.md` and begin defining scope interactively.

### Step 1: Determine Increment Number and Suffix

Read `.devmeta/current-increment.md`. Parse the active increment line (`**Active:** Increment <num>[-<suffix>] — ...`) and extract the **leading integer**, ignoring any `-<suffix>` part. Add 1 to get the new increment number — call it `<NN>` for the rest of this command.

Generate a 3-letter random suffix `<XXX>` from `[a-z]` (e.g. `abc`, `xkl`, `qmt`). The suffix exists so parallel branches/worktrees that both pick the same `<NN>` land in different directories and don't merge-conflict on the increment subtree.

Check that `.devmeta/increments/increment-<NN>-<XXX>/` does not already exist; if it does, regenerate the suffix and retry (up to 5 attempts — collisions are practically impossible).

**Throughout this command, `<NN>` is the new increment integer and `<XXX>` is its 3-letter suffix.** The full increment identifier (used in directory names and the title) is `<NN>-<XXX>` (e.g. `76-abc`). Iteration numbers within this increment use `<NN>` only — `<NN>.1`, `<NN>.2`, `<NN>.1R` — never the suffix.

### Step 2: Create Increment Directory

```bash
mkdir -p .devmeta/increments/increment-<NN>-<XXX>/iterations
mkdir -p .devmeta/increments/increment-<NN>-<XXX>/ia-cycles
```

### Step 3: Create `_overview.md` from Template

Write `.devmeta/increments/increment-<NN>-<XXX>/_overview.md` using this template:

```markdown
# Increment <NN>-<XXX> — <Title>

**Status:** NOT STARTED
**Depends on:** Increment <previous-id> (<previous increment title>)
**Goal:** <1-2 sentence goal — what the user can do after this increment that they couldn't before>

---

## What This Increment Produces

### On screen
- <User-visible feature 1>
- <User-visible feature 2>

### Under the hood
- <Technical deliverable 1>
- <Technical deliverable 2>

### Testing delivered
- <Test coverage expectations>

---

## What This Increment Does NOT Include

| Deferred | Why | Which Increment |
|----------|-----|-----------------|
| <Feature> | <Reason> | <Future increment> |

---

## Iteration Map

| # | Title | What Gets Built |
|:--:|-------|-----------------|
| <NN>.1 | <title> | <deliverables> |
| <NN>.2 | <title> | <deliverables> |

---

## Detailed Iterations

### Iteration <NN>.1 — <Title>

**Deliverables:**
- <deliverable 1>
- <deliverable 2>

**Verify on screen:**
- <acceptance criteria>

### Iteration <NN>.2 — <Title>

**Deliverables:**
- <deliverable 1>

**Verify on screen:**
- <acceptance criteria>

---

## Exit Criteria

- [ ] <Criterion 1>
- [ ] <Criterion 2>
- [ ] All tests pass
- [ ] Living docs updated

---

## Blocked Items

- <Item>: <What's needed and when>

---

## Previous Increments

<List of completed increments with links to their _overview.md>
```

If `$ARGUMENTS` provides an increment title, use it. Otherwise, leave `<Title>` as a placeholder for the interactive dialogue to fill in.

### Step 4: Update `.devmeta/current-increment.md`

Update `.devmeta/current-increment.md` to point to the new increment:
- Set the new increment as active with status NOT STARTED, using the **suffixed identifier** in the line: `**Active:** Increment <NN>-<XXX> — <Title>: ...`
- Keep the previous increment reference with its final status (its identifier stays whatever it was — historic ones may have no suffix)

### Step 5: Interactive Scope Definition

Begin an interactive dialogue to flesh out the overview. Ask about:

1. **Goal:** What should the user be able to do after this increment?
2. **On-screen deliverables:** What will visually change?
3. **Under-the-hood deliverables:** What technical work is needed?
4. **Exclusions:** What is explicitly out of scope?
5. **Iterations:** How should the work be split? (Aim for 2-5 iterations, each 1-3 days of agent work)
6. **Dependencies:** What must exist before this increment can start?
7. **Blocked items:** Anything that needs human action (API keys, accounts, etc.)?
8. **Exit criteria:** How do we know the increment is done?

Update the `_overview.md` with each answer.

### Step 6: Finalize

1. Review the completed `_overview.md` with the user
2. Ensure all template sections are filled in
3. Verify iteration map is reasonable (not too many iterations, not too few)
4. Confirm exit criteria are testable

Report:
```markdown
## Increment <NN>-<XXX> Created

**Directory:** `.devmeta/increments/increment-<NN>-<XXX>/`
**Overview:** `.devmeta/increments/increment-<NN>-<XXX>/_overview.md`
**Iterations:** <N> planned
**Status:** Ready for `/devmeta:plan-iteration <NN>.1`
```
