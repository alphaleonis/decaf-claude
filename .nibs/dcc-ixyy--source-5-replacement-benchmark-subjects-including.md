---
# dcc-ixyy
version: 1
title: Source 5 replacement benchmark subjects, including a whole TypeScript row
status: todo
type: task
priority: high
created_at: 2026-08-10T18:26:35Z
updated_at: 2026-08-10T18:42:12Z
parent: dcc-ho2w
blocked_by:
    - dcc-f2nf
order: F
---

The ground-truth audit ([[dcc-5xad]]) rejected 5 of 12 subjects. Full evidence and per-subject
reasoning: `competition/benchmark/v2/analysis/GROUND-TRUTH-AUDIT.md`.

## To replace

| # | Subject | Lang/size | Why rejected |
|---|---|---|---|
| 3 | dotnet/runtime#127146 | C# / large | regression issue is a bare CI failure list; total revert, no localization |
| 4 | microsoft/TypeScript#61928 | TS / small | downstream crash never stated in TS's own terms; the one good thread was applied during review |
| 5 | microsoft/vscode#308517 | TS / medium | ground truth invalid — all three findings fixed before merge; merged code does the opposite |
| 6 | microsoft/vscode#320685 | TS / large | reverted for "more than normal regressions"; no named bug at all |
| 11 | tokio-rs/tokio#7757 | Rust / medium | hang never root-caused; indicted ordering bug fixed during review |

**The entire TypeScript row is gone**, so no claim about TypeScript review quality is available until
3 TS subjects are sourced. Until then the corpus is C#x2, Go x3, Rust x2 and the language x size grid
does not hold.

## Screening order (cheapest first)

1. The revert/fix body **names a mechanism**, not a symptom or a CI link (METHODOLOGY-v2 Step 0 —
   this predicted every outcome in the 12-subject audit).
2. The indicted defect is **present in the merged diff** — read the code, never trust the comment.
3. A `must_flag` sentence can be written for **at least two** entries.
4. Merged after the roster's 2026-01 training cutoff, and lightly force-pushed.

Check re-land PRs before rejecting a candidate: subject 8 looked unscorable on its revert body and
was saved by its reattempt PR naming both gaps.

## Acceptance

- [ ] 3 TypeScript subjects sourced (small/medium/large) passing all four screens
- [ ] 1 C#-large and 1 Rust-medium sourced
- [ ] Each new subject taken through METHODOLOGY-v2 section 4 with an answer key committed
- [ ] Fixtures use `thread_comments` (not `human_threads.count`, which counted comments)
