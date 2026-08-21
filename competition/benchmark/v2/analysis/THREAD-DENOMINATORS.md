# The thread axis, corpus-wide — annotated 2026-08-21 (nib dcc-tvk8)

Every **active** subject now carries a `matchable_at_checkpoint` verdict on every admitted thread, so
`thread_axis_publishable` is true across the grid and no cell can quietly score against an inflated
denominator. 126 threads were read for this pass, on top of the 71 already annotated.

## Annotated before the cells ran, which is the point

Seven of the twelve were annotated **before a single cell has run on them**. That is the strongest
form of this blind available: matchability is a judgment about what a reviewer at the checkpoint
could raise, and it is decided here with **no tool output in existence** to be influenced by. The
alternative order has already gone wrong once — an annotator on grafana#117615 disclosed reading a
note saying no tool had matched the two threads it was judging (`dcc-hsy8`).

Do the annotation first. It costs the same and it cannot be contaminated.

## The active grid

| cell | subject | admitted | human | excluded | human denominator |
|---|---|---|---|---|---|
| contract S | immich#28886 | 2 | 2 | 0 | **2** |
| contract M | mattermost#36824 | 6 | 4 | 1 | **4** |
| contract L | PostHog#67924 | 65 | 62 | 0 | **62** |
| app-ui S | grafana#117615 | 7 | 2 | 2 | **0** |
| app-ui M | immich#29965 | 19 | 19 | 0 | **19** |
| app-ui L | element-web#32964 | 5 | 1 | 0 | **1** |
| backend S | mattermost#37874 | 6 | 6 | 0 | **6** |
| backend M | grafana#125982 | 20 | 20 | 2 | **18** |
| backend L | jellyfin#17044 | 8 | 8 | 0 | **8** |
| library S | sveltejs/kit#15685 | 3 | 1 | 0 | **1** |
| library M | efcore#34127 | 11 | 10 | 1 | **9** |
| library L | prometheus#18081 | 10 | 10 | 1 | **9** |

**139 matchable human threads across the active corpus.** For scale: the census that started this
work counted **30** across the seven then-citable subjects, concentrated in two cells with four at
≤2. The replacement round plus this annotation is where the miss detector actually got built.

Four cells remain at or under the `THIN_HUMAN_AXIS_MAX` of 2 — app-ui S (0), app-ui L (1), library S
(1), contract S (2). Their recall is quantized and reportable per subject only, never poolable
(`dcc-scc3` owns the decision to replace or keep them). grafana#117615 sits at **zero**: both of its
human threads are unmatchable, so it reports `thread_recall: null` with `human_axis_empty: true`,
which is not the same as every arm scoring 0.

## Only two exclusions in 126 threads, and they are the same thread twice

grafana#125982 T18 and T20 both review a comment reading *"A specific object was named but its
parent folder is unknown. Without a folder the only thing that can authorize the request is a
wildcard folder grant"* — T18 asks whether it has a use case, T20 says it is no longer true and
quotes it as the before-side of a suggested change. Enumerating every comment block inside
`checkPermissionDualCheck` (service.go:975-1040) finds six, none of them this one, and the phrase
returns **0 hits repo-wide**. The checkpoint handles an empty `ParentFolder` differently — it
returns true outright at :993-995 — so neither the comment nor the behavior it describes exists.

The other 124 were matchable, several via the compound-thread rule where a thread's quoted
suggestion had drifted but its substance had not:

- **element-web T2** names an ESLint disable comment to remove; there is none. Its primary claim, the
  unused `behaviour` binding at test:18, is present.
- **jellyfin T5** says `ApplyTo` never clears `dto.PlaybackPositionTicks`; it does assign it. But
  `dto.PlayedPercentage` is set only under `UserData.PlaybackPositionTicks > 0`, so a Played
  alternate at position 0 leaves the primary's percentage standing beside `Played = true` — the
  defect described, on the surviving half.
- **PostHog T36** weighs a `<team_focus>` fence, `</team_focus>` stripping and a 2000-char cap that
  do not exist at the checkpoint. The injection surface it is about is not merely present but
  **wider**: `focus_prompt` is interpolated raw into the prompt's first line with no mitigation at
  all.
- **PostHog T59** pairs `perform_create` with a `perform_destroy` that does not exist. The
  `perform_create` half is present and does lack the analytics call.

## One caveat on the two exclusions

`dcc-fm8s` requires two independent readings on every exclusion, and both readings of grafana
T18/T20 were **authored in the same session by the same agent**. The second is a genuine
re-derivation — enumerate every comment in the function, then widen the grep from one file to the
repo — but it is a second *method*, not a second *reader*, and it is recorded as such in
`matchability_readings[].independence`. Get a real second opinion on those two before grafana#125982
is scored. Nothing else in the corpus depends on them.

## Deliberately not annotated

The five non-active fixtures — PostHog#52408, PostHog#59630, grafana#124181, immich#24627,
jellyfin#12834 — carry a `matchability_deferred` block instead of verdicts. None holds a cell, so no
recall divides by them, and `score_pooled.py` already refuses an unannotated subject rather than
assuming everything is matchable. Annotate before the memorization probe runs: it compares recall
across a matched vintage pair, and both halves need the same denominator discipline.
