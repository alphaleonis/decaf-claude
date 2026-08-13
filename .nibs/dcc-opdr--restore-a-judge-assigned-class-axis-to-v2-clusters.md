---
# dcc-opdr
version: 1
title: Restore a judge-assigned class axis to v2 clusters (bug vs improvement)
status: completed
type: task
priority: high
created_at: 2026-08-13T11:29:27Z
updated_at: 2026-08-13T11:40:01Z
parent: dcc-ho2w
order: zk
---

v2's verdict vocabulary grades **how substantial** a finding is — `valid-other` / `valid-minor` /
`trivia` / `false-positive`, which is finer than v1's single `nitpick` bucket. What it does not grade
is **what kind of thing** the finding is.

v1 clusters carried a judge-assigned `category`: docs 21, test 17, design 10, test-coverage 8,
concurrency 5, logic 5, error-handling 4, bug 4, style 4, consistency 3, correctness 2,
behavior-change 2, observability 2, dead-code 2. **v2 clusters have no such field.** `category`
survives only on raw findings, where it is the tool's own unnormalized label
(`null-semantics-correctness`, `missed-optimization`, `naming`) and is never scored.

## Why it matters

A tool that finds wrong-results defects and a tool that suggests better naming currently earn the
same number. Concretely, on `dotnet/efcore#34127` the ten admitted human threads are mostly style
preferences — "I'm personally moving to `is null`", "nit: this can all be one nice switch statement",
"Naming-wise, maybe DetectNullPropagatingNodes?" — with **one** correctness question among them
("AndAlso/OrElse do propagate nulls normally too, no?"). All ten score identically as
`matches-thread`, so a tool that matched only the style nits and a tool that matched only the
correctness bug are indistinguishable on that axis.

The same flattening applies to `valid-other`: it holds both "the optimization deletes a load-bearing
guard and returns wrong rows" and "the soundness contract is never stated in a comment".

## What v1 got wrong, and should not be copied

v1's taxonomy was ad-hoc and unnormalized — `bug`, `logic` and `correctness` are three overlapping
labels for roughly one thing, sitting beside `design` and `style`. Restoring it verbatim would
reintroduce a free-text axis nothing can aggregate. The replacement should be a **closed set**,
graded by the same blind pass that assigns the verdict, and orthogonal to both severity and
substance.

Candidate set, to be settled as part of this work:

- `defect` — the code does something wrong: wrong results, a crash, a leak, a race
- `risk` — not wrong today, but an unenforced invariant or a latent hazard
- `test-gap` — the change is untested or the test does not constrain it
- `docs` — documentation, comments or generated artifacts disagree with the code
- `design` — a structural or API concern; the code works
- `style` — naming, formatting, convention

## Cost

Cheap, and it does not need new cells. All 267 clusters are committed with their summaries and
evidence; one additional grading pass over the existing pools backfills the axis for both pooled
subjects and the null arm. [Inference] ~$25.

## Acceptance

- [ ] Closed set decided and documented in `scoring/README.md`
- [ ] `/bench-analyze` grader emits `finding_class` alongside `verdict`
- [ ] `score_pooled.py` validates it against the closed set and refuses an unknown value, with a test
- [ ] Backfilled onto the pilot's 267 existing clusters
- [ ] `/bench-synthesize` reports the mix per tool — the axis exists to answer "what kind of reviewer
      is this", which precision cannot

## Summary

**Completed 2026-08-13** — Backfilled a judge-assigned finding_class onto all 267 pilot clusters from a closed set
(defect/risk/test-gap/docs/design/style), graded blind to tool identity and blind to the verdict so
class stays orthogonal to substance. score_pooled.py validates against the closed set, refuses a
PARTIAL classification (which would report a class mix over a subset as though it covered the
population), and emits class_distribution; three tests added, all firing.

It immediately changed a conclusion. ours-bugs has the purest defect focus in the roster -- 6 of 7
reported findings are defect-class, against 26-45% for everyone else -- so the preset is not confused
about its purpose. But it found 8 of the 16 real defects and reported only 5: defect recall 31%,
lowest of decaf's three presets, against ours-audit's 81%. ours-audit suppressed 4 real findings and
none was a defect, which localizes the fault to the bugs preset's own threshold rather than the
shared demotion machinery.
