# Judge calibration history (nib dcc-n4nf)

Agreement of each grading day's verdicts with the **pilot's**, on each subject's standing sample
(`pooled/<subject>/grading/calibration-sample.json`, chosen once, 15 clusters stratified across the
six verdicts). Recorded by `judge_stability.py --calibration` into
`grading/calibration-<date>.json`.

Self-agreement is not calibration. On 2026-08-19 the judge on prometheus agreed with itself 24/24
(κ 1.0) while agreeing with the pilot on 9/15 and 6/15. `judge_stability.py`'s stability mode cannot
see that, because it never looks at the baseline.

| date | subject | vs pilot p1 | vs pilot p2 | direction | note |
|---|---|---|---|---|---|
| 2026-08-17 | prometheus-18081 | 10–11/14 | 9/14 | — | **prose record only** — the underlying verdicts are not on this machine (they ran before the machine move). Taken verbatim from `analysis/BUGS-SP-RESULTS.md`; not recomputable here. |
| 2026-08-17 | dotnet-efcore-34127 | **3/12** | 8/12 | — | same provenance. The pilot judge was the lenient one on inspection: a thread match to a mangled GitHub suggestion nit, and a match to a *rejected bot* thread. |
| 2026-08-18 | five subjects | 53/75 | 51/75 | — | fresh draw that day, so only 3–5 clusters overlap the standing sample; the per-subject files are marked `BACKFILL` and are partial. The 53/75 and 51/75 figures are over that day's own sample. |
| 2026-08-19 | prometheus-18081 | 9/15 | 6/15 | **11 disagreements, all harsher** | fresh draw; backfill against the standing sample is n=3. |
| 2026-08-19 | dotnet-efcore-34127 | 9/15 | 8/15 | (same day, both subjects) | as above, n=5. |

## The reading that matters so far

**2026-08-19's judge was systematically harsher than the pilot.** Eleven disagreements on that day's
calibration sample, **eleven in the harsher direction** — three clusters the pilot called real were
downgraded, none upgraded. Comparative claims from that day survive it (every arm was graded by the
same judge in the same wave), but no absolute trivia or precision count from that day should be
published as though it were stable.

## From here

The standing sample makes days comparable: the same 15 clusters every time, so a difference in the
number is a difference in the judge rather than in the draw. **The backfilled entries above do not
have that property** and should not be read as a trend.
