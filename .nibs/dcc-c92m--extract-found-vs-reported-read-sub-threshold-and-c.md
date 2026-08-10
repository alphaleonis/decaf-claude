---
# dcc-c92m
version: 1
title: 'Extract found-vs-reported: read sub-threshold and considered-but-not-flagged sections'
status: todo
type: task
priority: high
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T17:43:41Z
parent: dcc-ho2w
order: "Y"
---

A tool can FIND a defect and then suppress it below its own reporting bar. Measured, not theorised:
`anthropic-code-review` on subject 2 found e1, verified it empirically, scored it 0 as "a
pre-existing limitation, not a regression", and headlined **"No blocking issues found."**

Score the headline -> miss. Score everything it wrote -> catch. Same tool, same model, same subject.

Both tool families do this. decaf writes a "Considered But Not Flagged" section; anthropic writes
"Observations below the reporting threshold". v1's extraction read consolidated reports and would
have scored that cell a miss.

## What this needs

- Extraction must parse demoted sections, not just the headline findings
- Each finding carries whether it was REPORTED or FOUND-BUT-DEMOTED
- Metrics report both, separately — recall-as-reported and recall-as-found
- The gap between them is itself a tool property worth publishing: a tool that finds everything and
  reports nothing is not equivalent to one that finds nothing

Related: the same effect was flagged in the subject-9 report as severity filters depressing measured
recall, and in `shared/model-migration.md` for Opus 4.7+ generally.

## Acceptance

- [ ] Demoted sections extracted for both tool families
- [ ] Verdicts distinguish reported from found
- [ ] Subject 2's anthropic cell scores as a CATCH under found, MISS under reported
