# Subject 2 — findings-quality analysis

**dotnet/aspnetcore#67075** (csharp / medium) — a Blazor `DataAnnotationsValidator` fix, reverted
wholesale in #67712. The production change is ~11 lines; the rest of the diff is tests.
Judge: `claude-opus-5[1m]`, blind. 34 clusters graded: **4 TP-primary, 5 valid-minor,
3 false-positive, 22 trivia.**

**This is a re-analysis.** The two `anthropic-code-review` cells were re-run on 2026-07-29 with a
plugin-qualified invocation. The cells previously recorded under that label had executed
`decaf-quality` (ours) at `high` mode — see nib dcc-9kkz — so every anthropic number in the
earlier version of this report was measuring ours. The eight non-anthropic cells are untouched
(bundles byte-identical to 17 Jul) and their extraction was reused verbatim; only the anthropic
findings were re-extracted. All 34 clusters were re-graded blind.

## The escaped bug

The PR replaces a single `GetProperty(FieldName)` with a two-step lookup: `DeclaredOnly` first,
then a `FlattenHierarchy` fallback. It does not work. Two facets: **(a)** `FlattenHierarchy` does
not flatten *instance* members, so when the runtime type does not itself declare the property but
an ancestor is `new`-shadowed, the fallback still throws the `AmbiguousMatchException` the PR
exists to fix; **(b)** `DeclaredOnly`-first silently drops a base class's validation attribute
when a derived `new` shadow omits it — behaviour the added test
`SkipsValidationWhenDerivedShadowHasNoAttributes` enshrines as expected.

**All five tools caught it.** That is unusual for this study and makes the subject a poor
discriminator on recall; the separation here is entirely in noise, cost, and calibration. Facet
(a) was found by everybody. Facet (b) was found by exactly one tool — and thrown away.

## The interesting result: anthropic found facet (b), then discarded it

`c41` — the silent-attribute-drop facet — is the only unique-true cluster in the subject, and it
belongs to anthropic. Its `prior-pr` agent stated it cleanly: the lookup "silently drops
validation attributes depending on which hierarchy level resolves, with no diagnostic," and named
the enshrining test. The blind grader scored it **TP-primary at confidence 93**.

Anthropic's own Haiku confidence scorer then rated that finding **0** — "correct C# member-hiding
semantics" — and the final report lists it only as a *dropped candidate*. The fan-out found a
genuine facet of the escaped bug and the cheap pre-filter deleted it.

This is a direct counterweight to the "filter early, cheaply" intervention proposed in
dcc-e0wj / dcc-xewu. That filter is what produces anthropic's clean output here — **zero false
positives, 1.5 trivia per cell** — and on this subject it also cost a true primary-bug catch. The
credit is real but should be read with that caveat: it counts because the extraction protocol
(METHODOLOGY §3A) records candidates the tool discarded. A reader of anthropic's actual posted
output would not have seen facet (b).

## Noise character

`pr-review-toolkit` is the outlier by a wide margin: **184 raw findings, 27 of 34 clusters
touched, 13.5 trivia per cell** — roughly nine times anthropic's rate — at precision 0.14. It
sprays the whole changeset: fixture naming, declaration order, attribute placement, unbounded
"also test generics/indexers/explicit interface impls" asks. Nothing it uniquely found was true.

`tag1` is the same shape at lower volume (140 findings, 6.0 trivia/cell, precision 0.21).

`ours` sits in the middle — 68 findings, 3.5 trivia/cell, precision 0.23 — but has this subject's
**worst calibration by far, 0.25**. Of the clusters ours ranked critical/high, three of four were
not substantive. Two of its three false positives are direct hits on `known_safe` entries: it
asserted the deliberate static-property exclusion is a defect (`c6`, `c17`) when both new lookups
specify `BindingFlags.Instance` precisely because DataAnnotations validates instance properties.
That is the answer key's designed trap, and ours walked into it twice.

`superpowers` produced the leanest useful output: 30 findings, 4 clusters, 1.0 trivia/cell, and it
caught facet (a) — for **$1.72**.

`anthropic` had **no false positives at all**, the only tool to manage that here.

## Did the fan-out earn its agents?

Not on this subject. Sub-agent distinctness is 0.21–0.29 across all four fan-out tools, meaning
roughly three-quarters of what any agent said restated a sibling. `superpowers` reached the same
primary catch with **one** agent that the others needed 10–11 for.

Ours ran 10 agents and touched 14 clusters; anthropic ran 10.5 and touched 7 — and anthropic's
seven were better chosen, landing the same facet-(a) catch plus the unique facet-(b) one while
emitting half as many findings.

## Cost versus catch

Every tool caught the bug, so cost-per-bug is just cost: superpowers **$1.72**, anthropic
**$5.58**, pr-review-toolkit **$5.64**, ours **$11.25**, tag1 **$12.54**.

Ours is **2.0× anthropic** here while producing twice the findings, more false positives, and a
quarter of the severity calibration. Against superpowers it is 6.5× the cost for the same catch
and 3.5× the trivia. There is no defensible cost story for ours on this subject.

The corrected anthropic figure ($5.58) is close to the study-wide clean-cell average ($7.13) and
less than half what the contaminated cells recorded — which is what the earlier version of this
report was reading as anthropic's cost.

## Caveats

- **All five tools caught the primary bug**, so this subject discriminates on noise and cost only.
  Do not read recall as informative here.
- **Anthropic emits confidence scores, not severities.** Its `severity_calibration` of 1.00 rests
  on very few explicitly severity-tagged clusters and is not comparable in weight to ours' 0.25,
  computed over a fuller severity ladder. Applying a severity-based metric to a tool that does not
  rank by severity is a known limitation — tracked in dcc-hmp6.
- **The eight non-anthropic cells reuse the 17 Jul extraction.** Their bundles are unchanged, but
  they were not re-extracted, so any extraction error there persists.
- **Cluster count moved 36 → 34** and the verdict vocabulary changed (the old run predates the
  valid-minor/trivia split), so the headline counts are not directly comparable to the previous
  version of this file.
- `human_issues` is empty by design — the one live human thread (Youssef1313's) *is* the primary
  bug, so it grades TP-primary rather than TP-human.
