---
# dcc-c92m
version: 1
title: 'Extract found-vs-reported: read sub-threshold and considered-but-not-flagged sections'
status: completed
type: task
priority: high
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T20:11:33Z
parent: dcc-ho2w
blocked_by:
    - dcc-y2e6
order: "6"
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
## Acceptance

- [x] Demoted sections extracted for both tool families — real markers harvested from actual cell
      output, not guessed: anthropic writes `Sub-threshold observations (verified real, but scored
      below the reporting bar — not posted)`, `Notes on things checked and cleared (not findings)`
      and `Minor/cosmetic (below reporting bar)`; decaf writes `### 🔵 Minor (N)`, `Considered But
      Not Flagged` and `**Not a defect** (all agents agree)`. Recorded in `/bench-analyze-v2` as
      examples rather than an allowlist, since tools reword their own headers.
- [x] Verdicts distinguish reported from found — `disposition: reported|demoted` per finding.
      `thread_recall` / `thread_recall_found` / `demotion_gap`, and the same split on
      `anchor_recall`. Precision counts reported only, since a demoted finding costs no attention.
      Guarded and tested (`demotion_gap`, `bad_disposition`, `disposition_defaults_to_reported`).
- [x] **Subject 2's anthropic cell scores as a CATCH under found, MISS under reported** — verified on
      the real archived cell: `anchor_recall 0.0` against `anchor_recall_found 1.0`.

## Summary

**Completed 2026-08-10** — Implemented as a `disposition` field (`reported` | `demoted`) carried per finding, with every
recall-style metric computed twice and neither allowed to stand alone: `thread_recall` versus
`thread_recall_found`, the same split on `anchor_recall`, and `demotion_gap` published as a tool
property in its own right. Precision-style metrics count reported findings only, because a demoted
finding costs the reader no attention.

The acceptance case is verified on the real archived cell rather than a mock: the anthropic run that
headlined "Verdict: No blocking issues found" scores **anchor_recall 0.0 / anchor_recall_found 1.0**,
because its sub-threshold section describes key entry e1 exactly — "Verified empirically… a
pre-existing limitation, not a regression. Per the rubric, pre-existing issues score 0."

Section markers were harvested from actual tool output rather than guessed, and recorded as examples
rather than an allowlist, since tools reword their own headers — the extraction rule is to judge by
whether the reader would have been shown the finding.

Three new self-tests (18 total, all passing). `disposition_defaults_to_reported` exists so an
analysis written before this field keeps scoring as it did.

Worth carrying into [[dcc-vkeh]]: a large demotion gap is not a defect to fix in the harness, it is a
finding about the tool. The remedy for a tool that finds everything and reports nothing is a
threshold change, not a better model — and that distinction is invisible to any headline-only metric.
