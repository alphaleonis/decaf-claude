# Open Questions — what a run leaves for a person to decide

An autonomous run makes calls a person may want to reverse and meets questions only a person
can settle. Without a home, those questions surface as one-liners at the end of a long final
report, where they are easy to miss and too short to act on. This convention gives them a
fixed format, written when the question arises, filed as one work item at the end of the run,
and walked by `/decaf-plan:resolve-open-questions`.

**Writer:** `auto-deliver` (VERIFY, RECONCILE, REPLAN record entries; STOP files them).
**Reader:** `resolve-open-questions`.

## What counts

An open question is something only a person can settle, or a call the run made that a person
may reverse. Each has one **kind**:

| Kind | What it is | Typical sources |
|------|------------|-----------------|
| `decision` | A choice the run could not make | a fact only a live system or the operator has; a cost or policy call (a paid CI runner, a privilege); a scope cut, which the loop never makes itself |
| `confirm` | A call the run made and acted on | a deviation from the spec; a behavior change the spec asked the operator to accept; a figure chosen without measurement (a cache size, a timeout); an acceptance criterion met through an exception |
| `manual-check` | Something a person must run or look at | a `[manual]` criterion no execution could settle; a check on another platform or against a live service |

**Not open questions:**
- a decision the spec or the existing code already dictated;
- an acceptance command that named the wrong path when the correct form passed (record it in the reflection's acceptance results);
- out-of-scope work, which is a follow-up item;
- anything already filed as its own work item (link it in the reflection instead).

The bar for `confirm` is "would the operator plausibly choose differently?", not "was a choice
made?". Every run makes hundreds of choices; list the ones that rest on a guess, an unmeasured
number, or a departure from what was asked.

## The entry

Write each entry **when the question arises**, while the evidence is at hand. A question
written up at the end of a run, from memory, is the one-liner this convention exists to
replace. Entries live under a `## Open questions` heading in the phase's
`reflection.md`:

```markdown
## Open questions

### <short title, in plain language>
- **Kind:** decision | confirm | manual-check
- **From:** <work-item id>; <files or symbols involved, if any>
- **What happened:** <what was built or found, and why it is open. Written for someone who
  has not seen the code: what goes wrong, or what stays unknown, under each answer.>
- **Options:**
  - A. <option> — <its effect and cost>
  - B. <option> — <its effect and cost>
- **Recommendation:** <the option and why, grounded in evidence. Name anything not checked.>
```

- **`confirm`**: the options are usually "A. keep it" and "B. reverse it", with what reversing costs.
- **`manual-check`**: replace **Options** and **Recommendation** with **How to check:** (the command or steps) and **Passing looks like:** (the observable result).

## The filed item

At the end of the run the writer gathers every entry not yet filed into **one** work item via
the tracker contract's `create`:

- **Type** `task`, **status `draft`**, **parent** the plan. `draft` keeps it out of `next-ready`, so the next loop never picks it up as buildable work.
- **Title** `Open questions: <plan title> (<plan id>)`.
- **Body**, grouped by kind, decisions first:

```markdown
Open questions left by <skill> on <plan id>, <date>. Walk them with
`/decaf-plan:resolve-open-questions <this item's id>`.

## Open questions

### Decisions
- [ ] **<title>** (<from id>)
  - **What happened:** …
  - **Options:** …
  - **Recommendation:** …

### To confirm
- [ ] …

### Manual checks
- [ ] …
```

Omit a group that has no entries. After `create` succeeds, rewrite each gathered section's
heading to `## Open questions (filed: <item id>)`, so a later run does not file it again. A
section whose heading carries `(filed: …)` is never gathered.

## Recording a resolution

The reader ticks an entry by updating the body in place, appending the outcome to its line:

```markdown
- [x] **<title>** (<from id>) — <outcome>: <one line, with the commit or new item id>
```

`<outcome>` is one of `changed`, `recorded`, `filed`, `accepted`. Where a tracker cannot edit
a body, the reader uses `append-note` with a `## Resolved: <title>` heading instead, and treats
an entry with such a note as ticked.
