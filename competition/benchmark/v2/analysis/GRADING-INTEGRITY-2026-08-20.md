# Grading integrity pass — 2026-08-20

Four changes to how a verdict is allowed to stand, and what they moved when applied to the six
scored subjects. Nibs `dcc-sfny`, `dcc-on93`, `dcc-fm8s`, and the three open contradictions from
`dcc-tvk8`.

The through-line: **every one of these is a claim that could not be checked.** A precision figure
resting on a boundary held to no floor; a thread match naming an index and nothing else; an exclusion
resting on one reading. None of them were wrong on their face — they were unfalsifiable, and three of
the four turned out to be hiding real errors.

---

## 1. The valid-other/trivia boundary now has a floor (dcc-sfny)

`judge_stability.py` pre-registered two floors, `real_vs_not.kappa >= 0.60` and
`exact_agreement >= 0.70`, and computed a third figure it held to nothing — the one its own docstring
calls "the load-bearing subjectivity in this design".

Measured before the change:

| | prometheus calibration (n=10) | PostHog, two full passes (n=62) |
|---|---|---|
| `valid_other_vs_trivia` kappa | 0.403 | **0.598** |
| `real_vs_not` kappa | 0.732 | 0.907 |
| `exact_agreement` | 0.733 | 0.852 |
| `matches_thread` same index | 3/3 | 24/24 |
| reported | `stable: true` | `stable: true` |

**What changed.** Three pre-registered floors, reported per boundary, and `stable` split into two
claims because the evidence splits two ways:

- `stable_for_rankings` — `real_vs_not` + `exact_agreement`. Which arm beats which survives a judge
  that shifts the whole field one way.
- `stable_for_precision_levels` — the boundary floor as well, at `n >= 50`. A precision *level*
  inherits the reproducibility of the one call that decides it.

`passes: null` on the boundary means **not established**, not failed: its n is a subset count that is
routinely tiny, and n=10 producing 0.403 while n=62 produced 0.598 on the same judge in the same week
is a sample-size artifact, not a worse judge. Overall `stable` requires both claims, and carries a
`stable_reason` saying which one is missing.

Under the new floors both measured runs report `stable: false` with rankings licensed and levels not.
**Consequence for publication: PostHog precision goes out as a band across both passes, not a point.**

**The rubric was sharpened at that one line too.** `scoring/prompts/verdict-rubric.md` is now the
single canonical copy — `foldin-blind-grader.md` and `/bench-analyze` both hand it over verbatim,
where they previously carried two paraphrases that had already drifted. It replaces a paragraph of
prose with a four-question walk (does it assert a defect at all / is the state reachable / is there
anything to do / is the consequence material) and worked examples of every answer taken from
already-graded clusters: `e08` and `ma06` for cleared hypotheses, `gf06` for unreachable, `im02` and
`gf12` for nothing-to-do, `gf02`/`ma26`/`im03` for `valid-other`, `e05`/`gf05`/`im07` for
`valid-minor`.

Also recorded there, because it is the verdict most likely to be quoted as "this tool was wrong" and
the least reproducible one in the set: PostHog's two passes assigned `false-positive` **7 times
versus 2** over the same 108 clusters.

---

## 2. A thread match must quote what it matched (dcc-on93)

`matches_thread: <index>` recorded nothing about why. `score_pooled.py` now refuses a
`matches-thread` verdict without a `matched_thread_quote`, and the quote must actually occur in that
thread's body (whitespace-collapsed, case-folded; ≥12 characters, or the whole body when the body is
shorter — real threads here go down to `Bool?`).

**Backfilling the 58 existing matches found two error classes the pipeline could not see.**

**Four clusters were credited to REJECTED threads** — `e01`, `e13`, `e32` -> efcore T10 and `ma36` ->
mattermost T3. The grader is only ever shown admitted threads, so these indexes cannot name a
legitimate match. The failure was silent in both directions: recall groups only admitted threads, so
the credit bought the tool nothing there, while `precision` still counted the cluster as REAL on the
strength of a match that did not exist. `score_pooled.py` now refuses this too.

`e13`'s index was recoverable — its recorded rationale names ExpressionType.Coalesce, and exactly one
thread says that (T14, a bot thread), where the quote verifies. Corrected. The other three had no
corresponding span anywhere and lost their thread credit.

**One credit onto a matchable thread was loose** — `c048` -> PostHog T32. T32 is about
`build_person_properties_at_time`; `c048` is about a second unbounded scan in
`person_existed_at_timestamp`. The shared span, "has no lower time bound and no row cap", is a real
correspondence of defect class and remedy but not of target. It is the weakest of the 58 and is
recorded here rather than silently kept. It changes no number: T32 is already credited by `c007` and
`c043`.

**Scope discipline on the re-grades.** Where a thread credit was removed, the cluster keeps the
substance class the blind grader gave it (all four were REAL, and became `valid-other`). Re-writing
substance from the auditor's chair is how a lenient judge is made; only the auditable defect — the
thread credit — was corrected, and each carries a `thread_credit_note` saying so.

---

## 3. Every exclusion now carries two readings (dcc-fm8s)

`matchable_at_checkpoint: false` removes a thread from every arm's denominator, and on an axis of
n=3 that is 33%. All 17 exclusions across the six scored subjects were single-pass.

A second reading was run over the exclusions only, blind to the first pass's reasoning, under a rule
stated in advance — **matchable if ANY claim in the thread targets present code** — and with
disagreement resolving toward matchable, also stated in advance. Both readings are recorded on the
thread (`matchability_readings`) and `score_pooled.py` refuses a subject whose exclusions carry only
one.

**Result: 2 of 17 flipped, both the compound-thread shape, and both had cost arms a legitimate hit.**

- **efcore T1.** Its quoted suggestion (`elseResult == null` -> `is null`) has no target — the
  checkpoint condition is `IsNull(elseResult)`. Its closing parenthetical is a separate general
  claim: *"I actually use `is` for any constant/literal check at this point."* That has two targets
  in the code the diff adds, including `func.InstancePropagatesNullability == true` at :633, one line
  below an `is`-pattern doing the same job. Flipped.
- **mattermost T6.** Sentence 1 asks for a request logger, and no logging exists at the checkpoint.
  Sentence 2 is a different claim: *"Let's move this call into the two placed where
  `CommandResponseFromHTTPBody` is called (commandWebhook, DoCommandRequest)."* Every element is
  present — the `o.IsValid()` call sits inside `CommandResponseFromJSON` at :72-74, and
  `CommandResponseFromHTTPBody` has exactly those two callers, at `web/webhook.go:114` and
  `app/command.go:595`. Flipped.

With the previously-found efcore T2, that is **three compound-thread errors** out of the twenty
exclusion verdicts this corpus has ever made. Every one of them silently cost arms a hit.

The fifteen that stand were re-confirmed by enumeration rather than argument: `grep` counts for the
construct each thread discusses (`unquoteIdentifier`: 0 hits; `lower_bound`: 0; `Invalid timestamp`:
0; `not detailed_conditions`: 0; `properties_matched` as a field: 0; `net/url` in a 100-line file:
absent). Prometheus T7 in particular had been flagged as resting on inference; it now rests on the
observation that `261000` occurs exactly twice in the checkpoint test file, both inside a case the
thread is not describing.

---

## 4. The three contradictions are resolved (dcc-tvk8)

`credited_to_unmatchable_thread` is now empty on all six scored subjects.

| contradiction | resolution |
|---|---|
| `ma11` -> mattermost T6 | **thread revised.** Not a loose match — T6's second sentence asks for exactly what ma11 reports. The exclusion was the error. |
| `e15` -> efcore T1 | **thread revised.** Same shape: the norm in T1's closing parenthetical has a target at :633. |
| `c108` -> PostHog T15 | **cluster's thread credit removed.** T15 asks for tests proving a gate DROPS the override fields; that gate does not exist at the checkpoint — its absence is what `c084` reports. The exclusion is correct and the match is not. |

Two of the three "loose grading matches" were annotation errors, not grading errors. The nib
predicted `ma11` would move mattermost's four arms; it did, **upward**.

### What moved

| subject | movement | why |
|---|---|---|
| mattermost | `thread_recall` 0.667 -> **0.750** for all four arms; `hit_by_any_tool` 2 -> 3 | T6 rejoined the denominator (3 -> 4) and the four arms that reported `ma11` regained the hit |
| efcore | `hit_by_any_tool` 6 -> 7; `ours-audit` recall 0.500 -> 0.556; six arms 0.125/0.250/0.375 -> 0.111/0.222/0.333 | T1 rejoined the denominator (8 -> 9); only the arm that reported `e15` gained a hit, so the rest fell on the larger denominator |
| efcore | `incumbent_agreement` 0.000 -> **1.000** on seven arms | `e13`'s corrected index points at T14, a bot thread, so those credits moved onto the incumbent axis where they belong |
| PostHog, prometheus, grafana, immich | no per-tool movement | `c108` lost a credit to a thread already outside the denominator, and its substance class was preserved |

Every movement is explained by a specific correction. None is an unexplained drift.

---

## What this does not fix

- **The boundary still sits under its floor** at the only n where it has been measured properly
  (0.598 at n=62). The floor makes that visible; it does not raise it. Three graders on boundary
  cases only, or a band, remain the open options.
- **Two subjects are mislabeled** `contract` when their checkpoint diff is backend-only (`dcc-acw2`),
  which touches the contract row's whole rationale.
- **Five active subjects were public and under review inside the training window** even though they
  merged outside it (`dcc-60qk`). That question is larger than this pass and larger than the
  replacement round that just finished.
