---
# dcc-vkeh
version: 1
title: 'Pilot: full roster on two pooled subjects — validate the instrument'
status: todo
type: task
priority: high
created_at: 2026-08-10T17:43:28Z
updated_at: 2026-08-11T08:09:52Z
parent: dcc-ho2w
blocked_by:
    - dcc-5xad
    - dcc-y2e6
    - dcc-fhp1
    - dcc-3cm6
    - dcc-suz4
    - dcc-vvf0
order: 8k
---

Everything run under v2 so far is essentially one tool on one subject: four anthropic cells plus one
`ours-review` cell, all on old subject 2. **There has been no cross-tool comparison under v2**, which
is the benchmark's entire purpose.

Rescoped by the instrument decision ([[dcc-595v]]): the pilot runs **pooled adjudication on two
pooled-corpus subjects** ([[dcc-ixyy]]), not the key-based anchor. Its job is to answer whether the
instrument works *before* the full run spends against all 12 subjects.

## What the pilot must establish

1. **Is the judge stable at the `valid-other` / `nitpick` boundary?** This is the single load-bearing
   subjectivity in the design — v1's own distribution put 58 of 98 clusters in `nitpick` and only 6
   in `false-positive`, so that boundary *is* the metric. Re-judge a sample blind and twice; if the
   two passes disagree materially, pooled adjudication does not yet work.
2. **Do the tools separate?** On precision, nitpick ratio, and unique real findings. If everyone
   scores alike the instrument is not discriminating and the full run is wasted.
3. **Does thread recall separate them?** The miss detector is the axis that catches what pooled
   adjudication structurally cannot. Report it separately from pooled precision — never merged.
4. **Does the judge dismiss what expert humans raised?** Any admitted thread the judge rules
   not-real, when a tool did report it, is a direct calibration failure. This check exists only
   because subjects were drawn from review-disciplined repos.

## Subject choice

Two subjects with dense admitted-thread sets, from different repos and different cells. Suggested:
`PostHog/posthog#52408` (backend/L, 19 admitted of 27) and `dotnet/efcore#34127` (library/M, 11 of
15). Both are well above the thread-thin cells and exercise different languages and application
types. Avoid the two thin cells (`immich#28886` at 2, `sveltejs/kit#15685` at 3) — their thread axis
cannot carry a validation.

## Scope

- Full roster: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`, `superpowers`, plus
  whichever competitors survive tool-definition rot (`pr-review-toolkit` and
  `tag1-comprehensive-review` are absent from `tools.json`)
- 2 subjects x roster x 2 repeats, shim ON
- Score through the pipeline ([[dcc-y2e6]]), not by hand
- Include a null cell ([[dcc-mjj5]]) if ready, so precision has an absolute floor on day one

`superpowers` needs a v2 invocation — it is local-diff-only already, which fits v2 naturally.
`run_cell_v2.sh` currently supports only the three decaf presets and anthropic, and still points at
`v2/repos/<id>`; pooled subjects live in `v2/pooled/<owner>-<repo>-<pr>/repo`.

## Acceptance

- [ ] `run_cell_v2.sh` runs against pooled fixtures, and every roster tool has a working invocation
- [ ] 2 subjects x roster x 2 repeats completed with clean leak audits
- [ ] Judge stability measured by a blind re-judge of a sample, with the disagreement rate reported
- [ ] Tools measurably separate on pooled precision, or a written explanation of why they do not
- [ ] Thread recall reported as its own axis, plus any threads the judge dismissed
