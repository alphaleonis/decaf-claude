---
# dcc-ui5d
version: 1
title: Refine walks open questions one at a time, with lettered options, recommended first
status: completed
type: task
created_at: 2026-11-23T21:34:41Z
updated_at: 2026-11-23T21:35:14Z
order: zzzzzzzzzk
---

`refine` ends each open question in one proposal to confirm ("Same here?"), so the user composes any alternative themselves, and it shows every question at once, so later answers are given against a draft an earlier answer may have changed. `resolve-open-questions` and the open-questions convention list options without saying where the recommended one goes.

- [x] `refine` walks its open questions one per turn, `Q<i> of <n>`: after each answer it updates the draft and re-checks the rest, dropping any the answer made moot
- [x] `refine` ends each question with two to four lettered options, the recommended one first and marked `(recommended)`, then `Or tell me something else.`; plain text, not a question box
- [x] `resolve-open-questions` puts the recommended option first as A, marked `(recommended)`; manual-check choices are lettered too
- [x] The open-questions convention requires the recommended option to be A
- [x] README's refine and resolve-open-questions sections match

## Acceptance
- [run] `scripts/check-skill-references.sh` — expect: exit 0
- [manual] a real `refine` run presents one lettered question per turn — needs a live interview

## Summary

**Completed 2026-11-23** — refine walks its open questions one per turn with lettered options, the recommended one first; resolve-open-questions and the open-questions convention put the recommended option first as A. The [manual] check (a live refine run) is not yet exercised.
