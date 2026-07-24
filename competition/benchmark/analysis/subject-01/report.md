# Subject 1 — dotnet/efcore #32770 (csharp/small): findings-quality analysis

**The subject.** A ~70-line change to `SqliteDataRecord.GetStream` replacing the single cached
`_rowidOrdinal` with a per-`(database, table)` dictionary so multiple BLOB columns in a JOIN
resolve independently. The escaped defect: the rewrite dropped the old `-1` "searched, not found"
sentinel, so the re-added `Debug.Assert(rowIdForOrdinal != null)` asserts a state that is
legitimately reachable (expression columns, PK not selected, composite-PK / WITHOUT ROWID tables)
and terminates the process in Debug builds — `SELECT 'test'` in `GetFieldValue_of_TextReader_works`
killed the test run (issue #32944) and the PR was reverted the next day (#32945). A piquant wrinkle:
the crashing assert was re-added at a human reviewer's request ("Re-add Assert"), so the human
thread is resolved in the final diff and the assert grades as the primary bug, not a human issue.

**Did the tools catch it?** Yes — all five, in both repeats, at consolidated level, and every one
of them at critical/high. This is a 10/10 sweep on the headline metric, so subject 1 does not
separate the tools on recall; it separates them on everything else. That is consistent with the
bug being "hidden in plain sight": the assert and the null-fallback two lines below it visibly
contradict each other in the diff hunk, no cross-file reasoning required. Several tools went
further than required: anthropic-code-review's historical-git agent and prior-feedback agents cited
the actual revert PR/issue numbers, and pr-review-toolkit empirically verified the crash (exit 134).

**The shared valid core.** Beyond the primary, the same three valid findings recur everywhere:
the not-found result is never cached (c2, valid-other — every `GetStream` on a no-rowid column
re-runs the full scan plus a `pragma_table_info` query, per chunk in chunked reads); the self-join
degenerate case the per-table key structurally cannot fix (c4, valid-other — pre-existing in kind
but squarely inside the PR's stated purpose); and the RowIdInfo over-design complex (c5, TP-human —
dead `TableName`, needless mutability, reduces to a tuple, matching ajcvickers' value-tuple
thread). Four tools found all four valid clusters in at least one repeat; anthropic-code-review
missed only the self-join (its union is {primary, c2, c5}). Inter-tool Jaccard over valid clusters
is 0.75–1.0 and **no tool produced a single unique true finding** — on a diff this small, the
fan-out premium bought zero marginal recall.

**Where the tools actually differ: noise discipline.** The valid set being identical, the spread
is in what else got said. anthropic-code-review is the disciplined outlier: ~3–6 consolidated
findings per cell, 1.5 valid-minor and 0.5 trivia per cell, severity calibration 1.0 (everything
it flagged critical/high was substantive), precision 0.58. Its consolidation gate visibly works —
it even scored the underscore-collision cluster at 50 and told the reader it was below threshold.
superpowers is nearly as clean (0.5 trivia/cell) while still surfacing all four valid clusters —
remarkable for a single-agent run. At the other end, pr-review-toolkit shipped 12 valid-minor and
4 trivia clusters per cell (precision 0.20, severity calibration 0.31 — its "critical" label means
little: it stamped critical on a stale test comment), and tag1-comprehensive-review sat close
behind (8.5 minor, 3.5 trivia, plus the subject's only false positive — a claim that expression
columns share a sentinel `"_"` cache entry, refuted because the not-found path never inserts
anything). ours landed mid-pack on volume (8.5 minor, 1.0 trivia) with zero FPs; its minors were
disproportionately convention-anchored (.editorconfig cites, sibling-idiom comparisons), which is
the valid-minor tier working as designed, but its severity ceiling was noisy — four "critical"
consolidated findings of which only one is the actual bug (calibration 0.6).

**Suggestion tier.** Thirteen clusters graded valid-minor — an unusually rich haul, and almost all
convention-anchored: the `RowIds` field naming (all five tools), `!=` spacing, `rowidkey` casing,
out-var idiom, whitespace churn, Console.WriteLine-instead-of-asserts, the defective test comments,
missing stream-type assertion, untested cache-hit branch, eager allocation. The repo's own
.editorconfig and sibling-test idioms anchor these, so they'd converge under a fix-and-rerun loop.
The trivia tier is dominated by open-ended more-tests lists and pre-existing adjacencies
(unqualified `pragma_table_info`, WITHOUT-ROWID misclassification) — real observations, wrong PR.

**Subagent economics.** The fan-outs were massively redundant here: distinctness 0.14–0.18 across
ours (15.5 agents/cell), anthropic-code-review (11.5), tag1 (10), pr-review-toolkit (5) — i.e.,
~85% of subagent findings restate a sibling's cluster. With zero unique-true findings anywhere,
no agent earned marginal recall on this subject; what the extra agents bought was corroboration
and (for ours/acr) validator confirmation passes. superpowers got the same four valid clusters
from one agent at $1.66/cell.

**Cost–quality verdict.** Every tool caught the bug, so cost-per-bug is just cost: superpowers
$1.66, anthropic-code-review $4.63, pr-review-toolkit $6.86, tag1 $11.68, ours $14.70. On this
subject the Pareto frontier is superpowers (cheapest, clean, full valid recall) and
anthropic-code-review (best precision/calibration, cites the revert); nothing the $11–15 tools
found justified their premium here. ours' distinguishing output was the breadth and specificity of
its convention-anchored suggestion tier and validator-confirmed evidence chains — worth something
in a fix-loop workflow, but not reflected in recall on a subject where recall saturated.

**Caveats.** (1) The subject is easy by construction — visible contradiction, small diff; treat it
as a floor-check, not a discriminator. (2) Human-thread signal is thin: one live style thread (h1),
so TP-human is nearly free for any tool that flags RowIdInfo's design. (3) Several verdicts sit at
confidence 60–70 (c3 valid-minor vs valid-other is genuinely arguable — the collision is real but
needs contrived ATTACH naming; c13/c15/c22/c23 minor-vs-trivia boundaries). (4) Repeat-stability
Jaccard was not computed by the script for this layout. (5) Contamination risk: several tools
(both anthropic-code-review repeats, one pr-review-toolkit and one tag1 subagent) demonstrably
retrieved the revert PR/issue from upstream git/GitHub history — fine as evidence of capability,
but it means "caught the bug" partially reflects retrieval, not pure review reasoning, and it
softens cross-tool comparisons of rationale quality on this subject.
