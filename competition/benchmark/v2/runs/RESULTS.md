# Benchmark v2 — first end-to-end cells (subject 2, 2026-08-10)

Checkpoint `3aa499ae7d23` (base `a2a5480e4b59`), 2026-07-07 · opus-4-8 · effort high.
Key: `v2/analysis/subject-02/answer-key.json` — one entry, e1, validated against the revert PR body.

| Run | e1 | Cost | Wall | gh accesses |
|---|---|---|---|---|
| `ours-review` | **caught, reported** | $4.16 | 471s | 0 |
| `anthropic-code-review` (local-authoritative prompt) | **caught, reported** as "the primary defect" | $1.27 | 203s | 0 |
| `anthropic-code-review` (v1-faithful "fetch the PR with gh") | **found, then SUPPRESSED** below the reporting bar | $2.10 | 273s | 1 (allowed) |

## The scoring problem this exposed

The third run found e1's component (a) and empirically verified it, then scored it **0** and demoted it
to "sub-threshold observations", producing a headline verdict of *"No blocking issues found."* Its
reasoning: the original code also threw for intermediate-base hiding, so this is "a pre-existing
limitation, not a regression. Per the rubric, pre-existing issues score 0."

Score the reported findings → **miss**. Score everything the tool wrote → **catch**. Same tool, same
subject, same model; the difference is a rubric rule about pre-existing issues plus a confidence bar.

The rubric reasoning is defensible for component (a) alone and wrong for the defect as a whole,
because component (b) — silently dropping validation attributes where the original threw loudly — is
new behavior, not pre-existing. Neither tool articulated (b) in any run.

**Implication for the benchmark:** a headline-only extraction understates recall, exactly as the
subject-9 report predicted for severity-filtered harnesses. Extraction must take sub-threshold and
"considered but not flagged" sections, and the metric should report reported-vs-found separately.

## Leaks found and closed (all by testing, none by writing the doc)

| Vector | Evidence | Fix |
|---|---|---|
| `gh pr diff <subject>` | returns the merged state — future information at any earlier checkpoint | denied; the agent has the correct diff locally |
| `gh pr view --comments`, `--json reviews` | post-checkpoint discussion on a pre-checkpoint PR | denied |
| `gh pr list --search` | returned `#67712 "Revert \"Fixed AmbiguousMatchException...\""` — the answer in a title | `created:<=CHECKPOINT` injected into the search; prior PR #67455 still visible |
| bare `gh pr view` | printed `state: MERGED` and `reviewers: ilonatommy (Approved)` — both post-checkpoint | denied; requires `--json` with safe fields |

The last one is the most consequential: the run that saw `state: MERGED` and an approval is the run
whose verdict collapsed to "no blocking issues". [Inference] Being told a change shipped and was
approved plausibly raises the bar a finding must clear. Not proven — one run each, and the prompt
also differed — but it is the first evidence that leaked context can SUPPRESS findings rather than
only inflate them, which is the opposite of the failure mode v2 was built to stop.

## Caveats

- One subject, one checkpoint, three cells. Validates the pipeline, not the tools.
- No dotnet SDK in the container: the first two runs are static analysis. The third claims empirical
  verification by sub-agents — unverified by me.
- The shim's DENY path has still never been triggered by a real reviewer; only ALLOW has.
