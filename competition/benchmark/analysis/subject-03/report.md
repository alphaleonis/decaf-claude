# Subject 3 — findings-quality analysis

**dotnet/runtime#127146** (csharp / large) — "Handle canonical types in casting logic," a 13-file
NativeAOT/type-system PR whose escaped bug was that the new optimistic canonical-wildcard semantics
were wired into the **shared** `CanCastTo` primitive: correct for the intended ILC dataflow
constraint checking, but unsound for consumers that treat `CanCastTo` as a **definite** answer.
`CorInfoImpl.compareTypesForCast` passes positives through as `TypeCompareState.Must`, crossgen2
folded `isinst I<object>` to unconditionally true, and `JIT/opt/Casts/shared_Casts` produced wrong
runtime output. Reverted in #127301. Judge: `claude-opus-5[1m]`, blind. 34 clusters graded:
**3 TP-primary, 1 TP-human, 3 valid-other, 9 valid-minor, 2 false-positive, 16 trivia.**

**This is a re-analysis.** The two `anthropic-code-review` cells were re-run on 2026-07-29 with a
plugin-qualified invocation. The cells previously recorded under that label had executed
`decaf-quality` (ours) at `high` mode — see nib dcc-9kkz — so every anthropic number in the earlier
version of this report was measuring ours. The eight non-anthropic cells are unchanged and their
extraction was reused verbatim; only the anthropic findings were re-extracted, and all 34 clusters
were re-graded blind.

## Everyone caught it, three different ways

**All five tools caught the primary bug**, which makes this the second consecutive subject that
discriminates on noise and cost rather than recall.

What is more interesting is that the answer key's `must_flag` rule admits several facets and the
tools split across them. `c1` states the sharp version — canon answers reaching definite
compile-time decisions via `compareTypesForCast`, naming the actual miscompile. `c3` states the
blast-radius version — every other `CanCastTo` consumer inherits the optimistic semantics
unaudited. `c5` states it as a coverage claim — the broadened surface is exercised by no test
outside constraint checking. All three were graded TP-primary; a reviewer landing any one of them
has done the job.

`c2` is the subject's only **TP-human** hit: the csproj gives the runtime type loader the *real*
`CastingHelper.Canon.cs` rather than the `NonCanon` stub, silently changing its cast semantics.
That was jkotas's question on the PR thread, deferred by the author with "probably not right now" —
and it is exactly the class of leak that then materialized elsewhere.

No tool produced a unique-true cluster this time; every valid finding was corroborated.

## Three real defects nobody framed as the primary bug

Three clusters graded `valid-other`, all in the constraints helper and all diff-verifiable:

- `c17` — the `NotNullableValueTypeConstraint` arm of `IsSpecialTypeMeetingConstraint` is **dead
  code**. Only `__UniversalCanon` satisfies the Universal check, and it is flagged
  `TypeFlags.ValueType`, so the caller's `(!IsValueType || IsNullable)` guard is already false.
- `c25` — several new test assertions are **vacuous**: `__Canon` is `TypeFlags.Class`, so
  `!IsGCPointer` short-circuits the reference-type chain before the new code runs. The tests pass
  for reasons unrelated to what their comments credit.
- `c21` — the pre-existing value-type prefilter fires before any canon awareness, so a structural
  pair like `MyStruct<string>` vs `MyStruct<__Canon>` returns false before `IsCanonEquivalent` can
  run.

These are the findings a reader would actually want beyond the headline, and they came from the
fan-out tools rather than the lean ones.

## Noise character

`pr-review-toolkit` again produced the most output by a distance — **314 raw findings**, 27 of 34
clusters, **10.0 trivia per cell** — at precision 0.25. `tag1` is close behind on noise (166
findings, 8.0 trivia/cell) and is the only tool to touch 29 clusters.

`ours` sits mid-field on noise (147 findings, 5.5 trivia/cell, precision 0.27) and — worth noting
after subject 2 — recorded **zero false positives** here, avoiding all three `known_safe` traps.
Its calibration recovered to 0.60 from subject 2's 0.25.

`anthropic` was the tightest of the fan-out tools: 35 findings, 11 clusters, 2.5 trivia/cell,
precision 0.35, no false positives.

`superpowers` had the best precision in the subject at **0.50** on 50 findings, with 1.5
trivia/cell and no false positives.

Both false positives in the subject (`c8`, `c32`) are of the same shape: asserting a defect in a
code path that cannot be reached — function pointers as generic instantiation arguments, and a
missing partial pairing for a file the csproj does not compile.

## Did the fan-out earn its agents?

Less than on subject 2, and by a wider margin. Sub-agent distinctness is 0.24–0.36, so two-thirds
to three-quarters of what any agent said restated a sibling. `superpowers` reached the same
TP-primary catch with **one** agent that ours reached with 14.5.

Ours ran the largest roster in the subject (14.5 agents) and touched 18 clusters; `tag1` touched
29 with 10 agents, and `pr-review-toolkit` touched 27 with 5. On clusters-touched-per-agent ours
is the least efficient fan-out here.

## Cost versus catch

Every tool caught the bug, so cost-per-bug is cost: superpowers **$3.13**, anthropic **$9.66**,
pr-review-toolkit **$14.79**, tag1 **$24.36**, ours **$27.97**.

Ours is the most expensive cell in the subject — **2.9× anthropic** and **8.9× superpowers** — for
the same primary catch, three shared `valid-other` findings, and mid-field noise. This is the
study's largest csharp diff (424 lines across 13 files), so it is where a deep roster should pay
off most; it did not pay off here.

The corrected anthropic figure ($9.66) is roughly a third of what the contaminated cell recorded
($32.25), which was ours at `high` on this same subject — the single most expensive run in the
whole benchmark, sitting in the anthropic column.

## Caveats

- **All five tools caught the primary bug**, so recall is uninformative here. Two consecutive
  subjects now behave this way.
- **The `must_flag` rule is deliberately broad** — three distinct clusters qualified. A stricter
  rule requiring the `compareTypesForCast` mechanism specifically would have separated the field.
- **Anthropic emits confidence scores, not severities**, so its `severity_calibration` of 1.00
  rests on few severity-tagged clusters and is not weight-comparable to ours' 0.60. Same
  limitation as subject 2; tracked in dcc-hmp6.
- **The eight non-anthropic cells reuse the 17/22 Jul extraction.** Bundles are unchanged, but any
  extraction error there persists.
- **Cluster count moved 33 → 34** with a changed verdict vocabulary (the old run predates the
  valid-minor/trivia split), so headline counts are not comparable to the previous version.
- Nine clusters were graded at confidence ≤ 62; those and every TP-primary/TP-human verdict want a
  human eyeball.
