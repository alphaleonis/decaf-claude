# Subject 4 — microsoft/TypeScript #61928 (typescript/small): findings-quality analysis

**The subject, and why it is the hardest primary in the set.** A tiny (21+/16−, 7-file) change
that makes `createChildren` — the implementation behind the public `Node.getChildren()` API — scan
JSX source files with the JSX language variant, so `</` is emitted as a single `LessThanSlashToken`
instead of `<` + `/`, with matching `SlashToken → LessThanSlashToken` updates across the JSX
closing-element handling. It even fixes a real correctness gap (getChildren previously mis-tokenized
`</`). But changing the token children a public API returns for JSX is a breaking behavioral change
for external consumers: downstream AST walkers (typescript-eslint, eslint-stylistic) crashed with
`RangeError: Maximum call stack size exceeded` on the changed child stream, and it was fully reverted
(#62423, issue #62188). Critically, the crash **does not appear in TypeScript's own test suite** —
only two fourslash baselines needed updating — so a reviewer reading the diff sees a small,
internally-consistent, test-passing change. Catching the escaped bug requires reasoning about
*external consumer* impact, not anything visible in the diff.

**The result inverts subject 1: only one tool caught the escaped bug.** The primary (c1) was found
by **anthropic-code-review alone**, in both reps — and its second TP-primary cluster (c13) was the
observation that the PR's own `test tsserver top300` CI bot reported SIGABRT crashes on real-world
repos, never resolved before merge. The other four tools — **including the two most expensive, ours
($19.21/cell) and tag1 ($18.74/cell)** — **missed the primary in both repeats**. Bug-catch:
anthropic 2/2; ours, pr-review-toolkit, superpowers, tag1 all 0/2. This is the sharpest recall
separation in the benchmark so far, and it runs opposite to cost: the priciest fan-outs missed what
a mid-cost tool caught.

**But anthropic's catch was retrieval-driven — and the same channel cost it precision.** anthropic's
primary framing came from its historical-git-context and prior-pr-feedback agents, which retrieved
the revert PR, the regression issue, and the CI signal from GitHub. That retrieval is a real
capability — none of the diff-only reviewers connected the tokenization change to a downstream crash
— but it is not pure diff-reasoning, and it is double-edged: the same retrieval channel produced
subject 4's most notable false positive. anthropic's c7 cluster asserts that `formatting.ts`'s
`shouldAddDelta` was "left unmigrated" and cites "a maintainer flagged this on the PR." Both halves
are false: formatting uses its **own dedicated JSX-variant scanner** (`formattingScanner.ts`'s
`jsxScanner`), independent of `createChildren`, which already emitted `LessThanSlashToken` for JSX
before this PR — so the diff changes nothing about `shouldAddDelta` — and the PR has exactly two
review comments (Copilot on utilities.ts, DanielRosenwasser on the optional typing), *neither about
formatting*. The "maintainer flagged it" attribution is a hallucination. c13's SIGABRT finding is
similar: the crash signal is genuine, but the tool named fabricated repos (kibana, remotion) that
do not appear in the actual CI report. Retrieval bought the only catch of the escaped bug and, in
the same breath, invented a review comment and mis-cited the evidence.

**The valid-other layer everyone found is genuinely strong.** Even missing the primary, the four
diff-only tools converged on a real, verified secondary set, so signal density stays high:

- **c2 — self-closing dead code (unanimous, 10/10 cells).** The `SlashToken → LessThanSlashToken`
  rename was applied to the completions.ts case still guarded by `parent.kind ===
  JsxSelfClosingElement`; a `LessThanSlashToken` (`</`) can only parent a JsxClosingElement/Fragment,
  never a self-closing element (whose `/` is a plain SlashToken), so the branch is unreachable dead
  code and the self-closing completion-location fix-up silently stopped firing. A textbook
  mechanical-rename bug, caught by every cell.
- **c3 — scanner-variant leak (9 cells).** `createChildren` mutates the shared module-singleton
  scanner to JSX and resets it only on the normal return path (no try/finally), so a `Debug.fail`
  in `addSyntheticNodes` leaks the JSX variant to later non-JSX scans in completions/preProcess.
- **c5 — incomplete-fix asymmetric fallback (9 cells).** The variant comes from
  `sourceFile?.languageVariant ?? Standard` while the text falls back to `node.getSourceFile()`, so
  a variant-less `SourceFileLike` carrying JSX still scans as Standard — re-introducing the very
  mis-tokenization the PR fixes. (Verified real, though held at low confidence: the tools' cited
  examples — textChanges.ts, sourcemaps.ts — turned out to reach a *different* scanner, so the
  concrete trigger they named is wrong even though the asymmetry is real.)
- **c4 — public-API widening (8 cells).** `languageVariant?` was added to SourceFileLike without
  `/** @internal */`, unlike both sibling optional members, so it ships in the public
  typescript.d.ts baseline — a one-shot API-hygiene fix (valid-minor).
- **c6 — braceMatching regression (tag1 unique).** tag1 alone traced that the braceMatching map has
  no `LessThanSlashToken` entry, so go-to-matching-brace on a .tsx closing tag now returns
  `emptyArray` — a concrete internal editor-feature regression from the same token change. tag1's
  fan-out earned this one.

**FP discipline held on the traps; the two FPs were elsewhere.** No tool fell for the four
`known_safe` traps — nobody flagged the deliberately-optional `languageVariant?` as a required-field
bug (it is exactly what the human reviewer requested), nor the `?? Standard` guard as an NPE, nor the
correct closing-token edits, nor claimed the scanner is "never reset." The two graded false positives
are both refuted by deeper code paths the tools didn't check: c7 (formatting, refuted by the separate
formatting scanner) and c14 (a `< /div>` whitespace edge, refuted because a bare LessThanToken never
parents a JsxClosingElement, so the old check didn't match it either). superpowers and tag1 posted
zero FPs; ours carried the c7 formatting FP in both reps (framed as "not migrated," without
anthropic's fabricated attribution); prt had the lone c14 edge FP.

**Subagent economics and overlap.** Distinctness sits at 0.18–0.24 for the fan-outs — high
redundancy, as ever. The four diff-only tools are near-interchangeable here: pairwise Jaccard over
valid clusters is 0.75–1.0 among ours/prt/superpowers/tag1 (they found the *same* secondary set),
while anthropic is the outlier (0.5–0.6) precisely because it alone holds the primary. tag1's fan-out
justified itself with the unique braceMatching catch; ours' fan-out — the most expensive on the
board — produced the same secondary set as the $3 tool plus the c7 FP, and did not reach the primary.

**Cost–quality verdict.** anthropic is the clear winner: the only tool to catch the escaped bug (2/2),
precision 0.88, severity calibration 1.0 (2/2), at $8.06 — with the caveat that the catch is
retrieval-driven and came bundled with a hallucinated FP. superpowers is the value floor: $3.14,
precision 0.55, zero FPs, the whole real secondary layer — but no primary. ours and tag1 are the
cautionary tale of this subject: ~$19/cell, 0/2 on the escaped bug, and (for ours) the highest FP
rate on the board. On a downstream-only bug, spending 6× more on fan-out bought no recall and, in
ours' case, worse precision.

**Caveats.** (1) The escaped bug is downstream-only and invisible to TS's tests, so this subject
measures external-impact reasoning (or retrieval) more than diff-reading; treat anthropic's catch as
substantially a retrieval result, and note that retrieval also produced its c7/c13 fabrications.
(2) human_issues is empty — the sole human thread (DanielRosenwasser's optional-typing request) was
adopted in the merged code — so the grade rests on primary recall + FP discipline + valid-other
yield. (3) c13 was graded TP-primary but is empirical CI-evidence with fabricated repo names and no
tokenization mechanism; it does not change the leaderboard (anthropic already catches via c1) but is
a soft TP — worth a spot-check. (4) c5 is verified-real but the tools' concrete trigger examples are
wrong; it is valid-other at low confidence. (5) The whole primary rests on one tool and one
mechanism family (retrieval) — a single-cell result to weight accordingly in the cross-subject
synthesis, where subject 4 is the strongest evidence that diff-only review misses downstream-only
regressions.
