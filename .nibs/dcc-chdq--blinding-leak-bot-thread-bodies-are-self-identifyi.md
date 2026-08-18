---
# dcc-chdq
version: 1
title: 'Blinding leak: bot thread bodies are self-identifying even with origin stripped'
status: todo
type: bug
priority: normal
created_at: 2026-08-18T17:44:27Z
updated_at: 2026-08-18T17:45:06Z
parent: dcc-ho2w
order: zy
---

Blind grading strips `author` and `origin` from every thread handed to the judge, so a thread
cannot be graded differently for being bot-authored (`thread_recall` is human-only;
`incumbent_agreement` is the separate bot axis). Verified structurally on 2026-08-18: the grading
payload carries exactly `{index, path, line, body}` and `{cluster_id, summary, location}`.

But the **body** is often self-identifying. mattermost-36824 has an admitted thread opening:

    🎯 Functional Correctness | 🟠 Major | ⚡ Quick win
    🧩 Analysis chain
    🌐 Web query:

That is unmistakably an automated reviewer. A judge cannot grade a thread without seeing its body,
so the blinding cannot be completed by removing more fields.

**Why it matters:** if the judge infers authorship it may apply a different bar to bot threads,
which would move clusters between the human and incumbent axes — the two axes METHODOLOGY-v2 says
must never be pooled.

**Not yet evidence of harm.** No measurement has been made of whether verdicts actually differ by
inferred origin. That is the first thing to do.

## What to do

- Measure first: on a subject with both origins, compare `matches-thread` rates against
  bot-bodied vs human-bodied threads, controlling for how many tools raised each.
- If a difference shows up, consider normalizing bodies (strip emoji rubric headers and
  tool-signature blocks) before grading, and record that the body was normalized.
- Record the limitation in `METHODOLOGY-v2` §3 either way — currently it reads as though
  stripping `origin` makes the judge blind to origin, which is only true of the metadata.

## Acceptance

- [ ] Measurement done and written up
- [ ] METHODOLOGY-v2 states the limitation
- [ ] Normalization implemented, or explicitly declined with the measurement as the reason
