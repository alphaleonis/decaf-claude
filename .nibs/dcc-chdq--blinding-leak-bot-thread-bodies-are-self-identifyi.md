---
# dcc-chdq
version: 1
title: 'Blinding leak: bot thread bodies are self-identifying even with origin stripped'
status: completed
type: bug
priority: normal
created_at: 2026-08-18T17:44:27Z
updated_at: 2026-08-19T16:15:14Z
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

- [x] Measurement done 2026-08-19: human 18/28 (0.64) vs bot 5/8 (0.62) matched by >=1 cluster; bot threads whose bodies visibly read as machine-written matched MORE (2/2 vs 3/6), the opposite of the concern, and those two are also the longest bodies so length confounds it. No gross effect. n=8 bot threads cannot detect a small one, and `matches_thread` conflates judge behaviour with tool coverage.
- [x] METHODOLOGY-v2 section 3 states it: blinding is sound for metadata, unproven for style; revisit if a subject with a large bot population enters the corpus.
- [x] Normalization DECLINED on the measurement. Normalizing bodies (stripping emoji rubrics and tool signatures) would alter the evidence the judge grades against, to correct a bias no measurement can currently see. Revisit only if a bot-heavy subject enters the corpus — grafana-117615 already has 5 bot threads to 2 human and is the one to watch.

## Summary

**Completed 2026-08-19** — Measured rather than assumed. Stripping `origin` blinds the judge to metadata but not to style — a
CodeRabbit body announces itself with an emoji rubric — and that cannot be fixed by removing fields,
since a thread cannot be graded without its body.

No gross effect: threads matched by >=1 cluster run 18/28 (0.64) human vs 5/8 (0.62) bot. The
controlled split runs the wrong way for the concern (visibly-machine-written bot threads matched 2/2
vs 3/6 for the rest), and those two are the longest bodies, so length confounds it.

Declined normalization: it would alter the evidence the judge grades against, to correct a bias no
measurement can see. Recorded in METHODOLOGY-v2 section 3 as sound-for-metadata,
unproven-for-style, with the trigger to revisit (a bot-heavy subject; grafana-117615 is already
5 bot to 2 human).

Two limits stated rather than buried: n=8 bot threads corpus-wide cannot detect a small bias, and
`matches_thread` conflates judge behaviour with tool coverage — a thread no tool addressed cannot
match however the judge reads it.
