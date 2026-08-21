# PostHog/posthog#55149 — per-subject readout

> ## `vintage.status: in-window` — these numbers are PER-SUBJECT ONLY
>
> Merged 2026-05-06, inside `claude-opus-5`'s window on the gating key, and its PR was opened
> 2026-04-17 — **in-window on both keys** (`dcc-60qk`). Nothing here may be pooled into a
> cross-subject figure, averaged with another subject, or quoted as "the benchmark says".
> `vintage.check_pooling()` refuses it, and that refusal is the rule working, not a nuisance.
>
> Since 2026-08-20 the subject is also `role: retired-probe` (`dcc-ryo4`): replaced in the contract L
> cell by PostHog#67924, kept as the **in-window half of a same-repo, same-cell matched vintage
> pair** with its replacement. That pair is what these numbers are now for — a memorization effect
> size, measured against a subject the model may have seen.

Subject: `contract` / L. Checkpoint `9b0f8447`, 18 files, +1253/−38.
Grading: `claude-opus-5`, **two independent blind passes** over the same 108 clusters.
Scored 2026-08-20 after the grading-integrity pass (`analysis/GRADING-INTEGRITY-2026-08-20.md`).

## Coverage — read this before any per-arm number

**4 arms · 7 cells · 108 clusters.** That is a *shallow pool*: the pooled instrument scores against
the union of what the tools said, so a thin arm list means a thin denominator for every
"unique_real" and every judgment of what the field can find. prometheus#18081 and efcore#34127 both
carry **13 arms over 29 cells**; this subject has four of them. An arm that looks unique here may
simply be the only one of four asked.

`ours-audit` contributed a **single** cell. Everything below for that arm is n=1.

## Precision — published as a BAND, not a point

Required by `dcc-sfny`: the `valid-other`/`trivia` boundary that decides precision measured
**kappa 0.598 at n=62 on this subject's two passes**, against a pre-registered floor of 0.60. The
run is `stable_for_rankings` and **not** `stable_for_precision_levels`, so a point estimate would
assert more than the judge supports.

| arm | precision band (p1 / p2) | severity-weighted band | reported clusters |
|---|---|---|---|
| `ours-review` | **0.90 – 0.95** (0.902 / 0.951) | 0.958 – 0.982 | 41 |
| `ours-audit` | **0.80 – 0.80** (0.800 / 0.800) | 0.912 – 0.928 | 50 |
| `ours-bugs` | **0.80 – 0.90** (0.800 / 0.900) | 0.909 – 0.971 | 20 |
| `superpowers` | **0.67 – 0.67** (0.667 / 0.667) | 0.857 – 0.877 | 36 |

Every arm clears the n≥10 reported-cluster publication floor (`PILOT-RESULTS.md`).

**One ranking is not stable across the passes.** `ours-review` is top and `superpowers` is bottom in
both. But `ours-bugs` ties `ours-audit` at 0.800 in pass 1 and beats it 0.900 to 0.800 in pass 2 —
so *"bugs vs audit"* is a coin-flip on this subject and must not be reported as an ordering.

The raw instability behind the band, worth quoting whenever a false-positive count is: the two
passes assigned `false-positive` **7 times versus 2** over the same 108 clusters. The verdict most
likely to be quoted as "this tool was wrong" is the least reproducible one here.

## Thread recall — n = 13, and the denominator is audited

35 admitted threads: **20 human, 15 bot**. The human axis divides by **13**, not 20:

- **7 human threads excluded as unmatchable** (`dcc-hw48`), each carrying two independent readings
  (`dcc-fm8s`) that agreed on all seven:

  | thread | file | why it cannot be raised at the checkpoint |
  |---|---|---|
  | T15 | `rust/feature-flags/src/handler/mod.rs:225` | asks for tests proving a public-request gate DROPS the override fields; that gate does not exist yet — its absence is what `c084` reports |
  | T34 | `posthog/api/feature_flag.py:3606` | critiques an `if not detailed_conditions:` branch and a test; grep finds 0 of either |
  | T53 | `posthog/models/person/point_in_time_properties.py:67` | rewrites a comment that does not exist; line 64 reads something else |
  | T59 | `posthog/api/feature_flag.py:3523` | reviews a regression of a `lower_bound` clamp; there is no clamp at all (0 hits) |
  | T64 | `posthog/api/feature_flag.py:3541` | reviews a CodeQL fix's replacement strings and a test; none of the three exist |
  | T65 | `rust/feature-flags/src/api/types.rs:398` | asks for a test on a `properties_matched` field `ConditionAnalysis` does not have |
  | T69 | `posthog/api/feature_flag.py:3539` | "the clamp is back" — post-checkpoint code, same as T59 |

- **3 duplicate groups**, every one a bot+human pair — `[23,38]`, `[24,44]`, `[27,45]`. Crediting
  either member credits both axes independently (`dcc-qfr5`); this is the subject that produced that
  finding.

| arm | thread recall (reported) | recall (found) | demotion gap |
|---|---|---|---|
| `ours-audit` | 0.846 (11/13) | 0.923 | 0.077 |
| `ours-review` | 0.846 (11/13) | 0.923 | 0.077 |
| `superpowers` | 0.615 (8/13) | 0.615 | **0.000 — structural** |
| `ours-bugs` | 0.385 (5/13) | 0.538 | 0.154 |

Recall is **identical in both grading passes** for every arm. Thread matching is the reproducible
part of this judge; only the substance boundary moves.

**`superpowers`' 0.000 demotion gap is structural, not behavioral.** Its report format has no
demotion section — no "considered but not flagged", no sub-threshold list — so nothing it found can
be recorded as found-and-suppressed. Read it as *not measurable*, never as *this arm suppresses
nothing*. The three decaf arms all show a real gap because their formats can express one.

**What the whole field missed: nothing, and that is the interesting part.** `missed_by_every_tool` is
1 (T16) on the *reported* view and **0 on the found view** — T16 was found and then demoted by every
arm that found it. It is the untested six-branch `is_internal_request` gate in
`authentication.rs`. A threshold problem, not a blind spot.

**Incumbent agreement** (a separate axis, never pooled with the human one): 10 of 12 bot thread
groups were also raised by at least one arm.

## Cost — per cell as well as per arm

`cost_per_real_finding` is repeat-dependent (`dcc-8dtt`): it divides a total by a deduplicated pool,
so an arm that ran twice pays twice for a pool that barely grows. Both forms, with `n_cells`:

| arm | cells | total $ | $/cell | $/real (repeat-dependent) | $/real/cell (invariant) |
|---|---|---|---|---|---|
| `ours-review` | 2 | 101.03 | 50.51 | 2.731 | **1.774** |
| `ours-audit` | **1** | 44.43 | 44.43 | 1.111 | **1.111** |
| `ours-bugs` | 2 | 20.12 | 10.06 | 1.257 | **0.937** |
| `superpowers` | 2 | 12.80 | 6.40 | 0.533 | **0.305** |

This subject is where that bug was found. On the repeat-dependent field `ours-review` reads 2.5×
worse than `ours-audit`; on the invariant one it is 1.6× worse, and per cell 14% worse. Most of the
apparent gap was that one arm ran twice and the other once — a scheduling decision.

Per-cell walls: `ours-audit` 33 min; `ours-review` 41 and 49 min; `ours-bugs` 22 and 21 min;
`superpowers` 13 and 16 min.

## Every finding on this subject is static reasoning

**No arm executed a single probe** (`dcc-9vta`). All seven cells recorded
`languages:[js,go,python]`, `missing_toolchains:[]`, `build_possible:true` — and every one of those
is wrong: Rust detection was root-only, this repo keeps its Cargo.lock under `rust/`, and **cargo is
not installed on this machine**. **13 of the 18 changed files are Rust.**

So the cell prompt told every reviewer a build toolchain was available for the majority language
while none was. Two `ours-bugs` cells independently recorded working around it — one marking all 13
findings `traced` or `read` with 7 below full confidence, the other flagging 8 of 16 as static
traces. One cell reported a backgrounded `cargo check` as "completed (exit code 0)" when its real
output was `cargo: No such file or directory`.

This does not bias the comparison — every arm faced the same environment — but it changes what the
subject measured: **static reasoning, not verified reasoning, across the majority of the diff.**
Detection and the prompt were both fixed on 2026-08-21; these cells predate the fix and cannot be
re-derived without re-running them.

## What this subject may not be used for

- Any pooled or cross-subject figure. In-window on both keys.
- A `bugs` vs `audit` precision ordering. It flips between the two grading passes.
- A precision point estimate. The boundary that decides precision is under its floor here; the band
  above is the publishable form.
- A claim that `superpowers` suppresses nothing. Its 0.000 demotion gap is a format artifact.
- A statement about what the field cannot find. Nothing was missed on the found view.
- A judge-calibration comparison. This subject has **no calibration record** and scores only under
  `--no-calibration`; it was the first subject graded and never had a standing sample drawn
  (`dcc-n4nf`). Any drift between its grading day and another subject's is unmeasured.
