---
name: resolve-open-questions
description: Walk the open questions an autonomous run left behind — decisions it could not make, calls it made that you may reverse, checks only a person can run — one at a time, with what happened, the options and a recommendation for each. Use after auto-deliver ends with an open-questions item.
argument-hint: "[open-questions work item id]"
---

# Resolve open questions

You have been invoked as the `resolve-open-questions` skill. The user's arguments are: $ARGUMENTS

An autonomous run (`/decaf-build:auto-deliver`) files what it leaves for a person as one
`draft` work item holding a checklist of open questions. Walk that checklist with the user,
one question at a time, until each has an outcome. The item's body is the state: a ticked
entry is resolved, so a walk interrupted by compaction or a new session resumes from the first
unticked one.

Before anything else, read `${CLAUDE_PLUGIN_ROOT}/conventions/open-questions.md` in full. It
defines the kinds, the entry fields, and how a resolution is recorded.

## The rules

1. **One question per turn.** Present one, end your turn with the question, and wait. Never
   present a batch, and never resolve a question the user has not answered.
2. **Ask in plain text, not a question box.** The explanation is the point, and text before
   a question box can fail to reach the user.
3. **Re-check before presenting.** An entry is a claim from a past run, not a fact about the
   code now. Spend your own effort so the user's answer is cheap.
4. **Write for someone who has not seen the code.** Ids and paths support the explanation;
   they are not the explanation.

## Process

### 1. Find the item

Before the first tracker operation, read `${CLAUDE_PLUGIN_ROOT}/conventions/work-items.md` in
full, then read the one adapter it names for the detected tracker.

With an id, `read` it. Without one, look for open `draft` items whose title starts with
`Open questions:`. Take the only one, or ask which when there are several. None → say so and stop.

### 2. Summarize

Parse the unticked entries under `## Open questions`, in the item's order: decisions, then
calls to confirm, then manual checks. Show the count per kind and one line per entry (its
number and title). If some are already ticked, say how many and that you are resuming. Then
present the first entry in the same turn.

### 3. Present one entry

**Re-check it first.** Open the files and items it cites:
- Does what it says happened still hold? Has a later commit or item already settled it?
- What does the entry leave unsaid that the user needs, such as whether the doc it proposes to edit has a place for the change?

If it is already settled, present that evidence and propose `obsolete` instead of the options.

Then present:

```markdown
**Item <i> of <n>: <title, in plain language>**

**What happened:** <what was built or found, why it is open, and what goes wrong or stays
unknown under each answer. Include what you found in the re-check.>

| Option | Effect | Cost |
|---|---|---|
| A. … | … | … |
| B. … | … | … |

**My recommendation:** <option and why, grounded in evidence. Name what you did not check.>

<A or B?>
```

- **`confirm`**: say what was decided and why, then offer keep or reverse, with what reversing costs.
- **`manual-check`**: give **How to check** and **Passing looks like**, then offer four choices:
  - done and it passed;
  - done and it failed, which files a bug;
  - file it to do later;
  - skip for now.

Where the entry's options are weak, or the re-check turned up a better one, improve them.
The entry is a starting point, not a script.

### 4. Act on the answer

Do what the answer asks, then record it. Each entry ends with one outcome:

| Outcome | When | Do |
|---|---|---|
| `changed` | The answer is a small change: a doc line, a constant, a test | Make it now and run the relevant check |
| `filed` | The answer is real work, or a manual check to do later | `create-followup` under the plan. Status `draft` unless the user's answer fully specifies it, since you inferred the rest |
| `recorded` | The answer keeps or picks something with no change now | Nothing beyond the note below |
| `accepted` | The user keeps what the run did | Nothing beyond the note below |
| `obsolete` | The re-check found it already settled | Nothing beyond the note below |

If a "small change" turns out not to be small, stop and offer `filed` instead.

For every outcome except `obsolete`, `append-note` on the item the entry came from, under
`## Decision: <title>`: the choice, the reason the user gave, and any commit or new item. That
item is where a future reader looks.

Then tick the entry per the convention, with its outcome. If the project's instructions say
to commit tracker files with the change, commit now. Otherwise leave the changes uncommitted
and say so at the end.

**Skip for now** leaves the entry unticked. Move on to the next entry in the same turn: confirm
the outcome in a line or two, then present it.

**"Take your recommendation for the rest."** Go through the remaining entries without
stopping, re-checking each. Stop at any entry where the re-check changed your recommendation,
and at any manual check, since only the user can run it.

### 5. Finish

When no unticked entries remain, `close` the item with a summary: the count per outcome, the
changes and their commits, and the items filed. If any were skipped, leave the item open
instead, and say how many remain and the command to resume.

## There is no `--unattended` mode, deliberately

These questions are what the run could not decide alone. A mode that answers them without
the user would put the same guesses back in the record as decisions.
