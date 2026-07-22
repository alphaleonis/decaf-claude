# Subject 3 — findings-quality analysis

**dotnet/runtime#127146** (csharp / large) — "Handle canonical types in casting logic," a 13-file
NativeAOT/type-system PR by a principal engineer whose escaped bug was that the new optimistic
canonical-wildcard semantics were wired into the **shared** `CanCastTo` primitive: correct for the
intended ILC dataflow constraint checking, but unsound for consumers that treat `CanCastTo` as a
**definite** answer — `CorInfoImpl.compareTypesForCast` passes positives through as
`TypeCompareState.Must` (its own comment table says the canonical case must be **May**), so the
JIT/crossgen2 folded away required runtime casts and `JIT/opt/Casts/shared_Casts` produced wrong
results on every R2R-CG2 platform. Reverted wholesale in #127301. Judge: `claude-opus-4-8`, blind.
**791 raw findings → 33 clusters: 3 TP-primary, 1 TP-human, 9 valid-other, 1 false-positive, 19
nitpick.**

## Did they catch the bug? Yes — all of them, decisively

Bug-catch is **100% for all five tools in both repeats.** I expected very low recall (deep
JIT/AOT canonical-generics domain; the author is a domain principal and the .NET architect reviewed
it) — but the violated contract was *documented in the consumer itself*: `compareTypesForCast`'s
comment table spells out that canonical cases must return May. Every tool that traced the widened
`CanCastTo` to its callers found the contradiction, most naming the exact miscompile scenario
(`IFoo<__Canon> → IFoo<string>` folding to constant true) and several noting the READYTORUN sanitizer
only fixes MustNot, not the new wrong Must. The catch was graded at confidence 98 — the cleanest
primary catch of the benchmark so far. Two related clusters also graded TP-primary: the
**unaudited blast radius** (devirtualization, dispatch-map building, covariant returns, ~10 downstream
projects consuming ILCompiler.TypeSystem) and the **zero test coverage of the broadened `CanCastTo`**
outside constraint checking (its true-arms are dark — deleting the hook leaves the suite green).

Notably, `anthropic-code-review`'s second run — an anomalous cheap run ($3.41, ~11 min, **no subagent
fan-out at all**) — still opened its report with a precise articulation of the primary. On this
subject the catch did not require fan-out; it required reading the consumers of the changed primitive.

## The human thread was caught too

The one substantive human thread (jkotas: *"Do we actually need the real CastingHelper.Canon.cs in the
runtime type loader?"* — answered with "we can fix the bug if this ever becomes a bug") maps to
cluster c2: **System.Private.TypeLoader ships the real Canon flavor, silently changing runtime GVM
dispatch casting semantics, untested.** Nine of ten cells raised it — every tool, in at least one
repeat (only `anthropic` r1 missed it). Strong human-issue recall across the board.

## Precision is the highest of any subject so far — because there was real signal to find

This diff genuinely contained many defects beyond the primary (9 valid-other: the un-normalized
`MakeGenericMethodSite` twin, the value-type prefilter shadowing canonical struct shapes, vacuous
test assertions, the weak smoke-test proxy, dead constraint arm, undocumented Canon/NonCanon
selection contract, untested branches, shallow variance coverage, a missing InstantiationContext
test). Precision: **`superpowers` 57%, `ours` 54%, `tag1` 51%, `anthropic` 49%, `pr-review-toolkit`
44%** — roughly double the ratios seen on subjects 2/9. Valid findings per run: **`tag1` and
`pr-review-toolkit` 10.5 (most), `ours` 7.0, `anthropic` 5.5, `superpowers` 3.5.** `tag1` also has
the sole **unique valid catch** (the missing non-null `InstantiationContext` test) — and the sole
**false positive**: its claim that TypeLoader.csproj is missing the matching
`TypeSystemConstraintsHelpers` pair is refuted by the diff (that project never compiles the file), an
error its own second run's verifier caught but its first run shipped. No tool fell into either
planted trap (the valid semicolon-body C# types that the Copilot bot itself got wrong, and the
intentional NonCanon stubs).

## Cost vs. catch — the cheap end wins again when everyone catches the bug

With universal recall, cost-per-bug is just cost-per-run: **`superpowers` $3.13, `pr-review-toolkit`
$14.79, `anthropic` $17.83†, `tag1` $24.36, `ours` $27.97.** `superpowers` again delivered the
essential result — primary + human issue + 3.5 valid findings at 57% precision — for a ninth of
`ours`' price. The thorough tools bought more valid secondaries (tag1/pr-review 10.5/run) but with
9–13.5 nitpicks/run of noise. `ours` sits mid-pack on yield at the highest price on this subject.
†`anthropic`'s mean is skewed by the anomalous no-fan-out r2 ($3.41 vs $32.25 for r1) — which still
caught the primary, an accidental natural experiment suggesting the fan-out wasn't what found this bug.

## Caveats

- **The primary was unusually discoverable for its domain**: the violated invariant is written in a
  comment table inside the consumer. The 100% catch says the tools read consumers of changed shared
  code well; it does not say they would find an undocumented equivalent.
- **`anthropic` r2's missing fan-out** makes its per-repeat comparison partly apples-to-oranges
  (12 raw findings vs r1's 102); flagged in the run data.
- **Judge-uncertain clusters**: `c7` (UniversalCanon↔Canon cross-form, conf 50), `c8` (function-pointer
  fall-through, 45), `c17` (dead constraint arm, 55), `c27` (smoke-test proxy, 55).
- Single judge (`claude-opus-4-8`).

## Human spot-check queue (bias control)

- **TP-primary:** `c1` (conf 98 — solid), **`c3` (85)** and **`c5` (80)** — confirm that the
  blast-radius and dark-branches clusters deserve primary credit rather than valid-other.
- **TP-human `c2` (95)** — confirm the TypeLoader/jkotas mapping.
- **The false positive `c32` (85)** — tag1's missing-pair claim; the diff refutes it (TypeLoader never
  compiles TypeSystemConstraintsHelpers.cs).
- **Low-confidence:** `c7` (50), `c8` (45), `c17` (55), `c27` (55).

*Outputs are committed-local under `analysis/subject-03/`. Nothing was posted anywhere; analysis is
read-only over `runs/`.*

## Addendum — suggestion-tier regrade (valid-minor vs trivia)

The 19 nitpick clusters were blind-regraded under the suggestion-tier rubric: **5 valid-minor, 14
trivia**. Surviving suggestions are the objectively-anchored ones: the unused `using` the bot flagged
and the cleanup half-missed, the 8-vs-6-space `<Link>` indentation against the file's own convention,
the factually wrong test comments, the missing doc on `IsSpecialTypeMeetingConstraint`, and the
`IsCanonEquivalent` doc/code contradiction. Suggestion yield: `pr-review-toolkit` 4.5/run (highest),
`tag1` 4.0, `ours` 3.5, `anthropic` 2.0, `superpowers` 1.5. Severity calibration: everyone 100%
except `tag1` 67% (its confidently-labeled `c32` was the subject's false positive). Low-confidence:
`c28` (→ trivia, 55).
