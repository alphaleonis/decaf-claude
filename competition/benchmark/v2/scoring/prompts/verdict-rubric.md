# The verdict rubric — canonical text (nibs dcc-sfny, dcc-on93)

**This file IS the rubric.** `foldin-blind-grader.md` and `/bench-analyze` both hand it to the blind
grader verbatim; neither restates it. It lived in two places until 2026-08-20 and the two copies had
already drifted apart in wording.

## The verdict object

```json
{"cluster_id":"", "verdict":"matches-thread|matches-key|valid-other|valid-minor|trivia|false-positive",
 "matches_thread": null, "matched_thread_quote": null,
 "judged_severity":"critical|high|medium|low|nit|info",
 "code_citation":"file:line-range", "confidence": 0.0, "rationale":""}
```

- **`code_citation` is REQUIRED for every real verdict** (`matches-*`, `valid-other`) — point at the
  code that makes the claim true. The judge shares a model family with the reviewers, so a verdict
  that cannot point at code is not evidence. Verify against the actual code, not the summary's
  wording.
- **`matches-thread` requires BOTH `matches_thread` and `matched_thread_quote`.** The index says
  which thread; the quote — a span copied out of that thread's body — says what in it the cluster
  corresponds to. A grader that cannot quote the overlapping text has not matched it, and the
  scorer refuses the verdict (`score_pooled.py`) rather than crediting it.
- **`matches-key` requires `matches_key`.** Anchor subjects only.
- Judge SUBSTANCE, not wording: a cluster raising the same defect a human thread raised, in
  different words, matches it. But "same defect", not "same line" — see the failure mode below.
- Never reward volume; judge each cluster on its own merits, blind to how many the tool produced.
- `judged_severity` is YOUR assessment of impact if real (`info` for trivia/false-positive).

### The loose-match failure mode this quote exists to catch

Three real cases, all credited before the quote was required, all same-file-or-same-line
coincidences rather than the same claim:

| credited | the cluster said | the thread asked for |
|---|---|---|
| `e15` -> T1 | `== true` used where an `is { }` pattern is the convention | `is null` instead of `== null` — on a line with no `== null` |
| `ma11` -> T6 | validation belongs in the shared bidirectional decoder | use a context-carrying logger instead of the global one |
| `c108` -> T15 | the Rust test edits set the new fields to inert values | no integration test covers overrides being dropped |

Each would have failed the quote test: there is no span of those threads the cluster corresponds to.
If the only quote you can produce is the thread's file path, its opening pleasantry, or a token that
merely happens to appear in both, the verdict is not `matches-thread` — it is `valid-other` (the
cluster raised something real that no thread raised) or `valid-minor`.

## `trivia` vs `valid-other` — the load-bearing call

This one boundary decides `precision`: `valid-other` counts as real, `trivia` counts as noise, and
`valid-minor` is excluded from both. It is also the least reproducible verdict the judge makes —
measured at kappa 0.598 over n=62 on 2026-08-20, against a pre-registered floor of 0.60, while the
coarse real/not-real collapse was 0.907 and thread matching reproduced 24 of 24. Everything else
about the judge is stable. **This is the call to slow down on.**

Work the four questions in order. The FIRST one that answers stops the walk.

**1. Does the claim assert that something is WRONG?**
A cluster that investigates a hypothesis and clears it — "considered whether X breaks, it does not"
— asserts no defect, however careful the analysis. → **`trivia`**, always, and note it as cleared.

> `e08` "Whether the HashSet relies on structural rather than reference equality" — *cleared and
> correct: set and probe both go through SqlExpression's structural Equals.* → `trivia`
> `ma06` "A typed-nil `*AppError` could escape at the `CommandResponseFromJSON` call site" —
> *cleared: the pointer is nil-tested as a concrete type before being returned.* → `trivia`

**2. Is the state it describes REACHABLE at this checkpoint?**
True in the abstract but unreachable given the callers that exist → **`trivia`**.

> `gf06` "the `refId.label || refId.value || ''` fallback can hand an empty identifier to
> `quoteIdentifierIfNecessary`" — *technically true, but `ExpressionQueryEditor` always sets both
> from `q.refId`, so a refId with neither is unreachable in practice.* → `trivia`

**3. Is there something to DO about it?**
Reachable and true, but no change follows — a fact about history, a consequence already sealed, a
harmless characterization → **`trivia`**.

> `im02` "users who ran the deleted migration already had -1 ratings irreversibly converted" —
> *true, and nothing in this change can undo it.* → `trivia`
> `gf12` "the third test asserts quoting at `metaSqlExpr.ts:29` that predates the diff, so it is
> characterization" — *true and harmless; adding it is not actionable.* → `trivia`

**4. Is the CONSEQUENCE material?**
Wrong results, a crash, data loss, a security or contract break, a path that silently disagrees with
another path → **`valid-other`**. Cosmetic, documentation, a coverage asymmetry, or an edge case a
reader would reasonably decline → **`valid-minor`**.

> `gf02` "`cleanTableName` strips quotes and parens but not backticks and truncates at the first
> space" — *the now-default `` FROM `gdp per capita` `` yields target `` `gdp `` and `Graph.link`
> throws.* → `valid-other`
> `ma26` "`IsValid`'s nil-skip lets `{"extra_responses":[null]}` through" — *the nil element reaches
> `HandleCommandResponsePost`, which dereferences it.* → `valid-other`
> `im03` "metadata extraction still clamps with `validateRange(Rating, 1, 5)` while
> `handleSidecarWrite` writes -1" — *two paths in the same feature disagree.* → `valid-other`
>
> `e05` "the new TODO carries no issue reference, unlike the `#16050` markers nearby" — *accurate;
> documentation nit.* → `valid-minor`
> `gf05` "`quoteIdentifierIfNecessary` does not double embedded backticks" — *correct, and an
> extreme edge case in a pre-existing helper.* → `valid-minor`
> `im07` "the web UI passes -1 through `rating || null` so a rejected asset renders as unrated" —
> *real display effect, small.* → `valid-minor`

**`false-positive` is for claims that are WRONG** — the code does not do what the cluster says. It is
not the bucket for "right but unimportant"; that is questions 1-3. Reach for it only after checking
the code, and note that it is the least reproducible verdict in the set (two passes over the same 108
clusters assigned it 7 times versus 2), so it deserves the same care as the boundary above.

When genuinely uncertain, say so in `confidence` rather than splitting the difference. A `trivia`
at 0.5 confidence and a `valid-other` at 0.5 confidence carry information the metric can use; a
`valid-minor` chosen to avoid the decision does not.
