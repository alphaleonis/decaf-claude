# Quarantine — cross-cell `.decaf/` contamination (2026-08-06)

Everything in this directory was produced from contaminated runs. **Do not cite any number in
here.** It is kept as evidence and for post-hoc comparison against the clean re-runs.

Tracking nib: `dcc-2cxq`.

## What happened

`repos/<subject_id>` is a single checkout shared by all 16 cells of a subject. `run_cell.sh`'s
`ensure_repo()` returned early whenever the commit was already present, so its
`git checkout -q -f "$merge"` ran only on the first clone. Every later cell inherited the working
tree exactly as the previous cell left it — including the untracked `.decaf/code-reviews/`
directory that the decaf review skills write their reports into.

The decaf skills have a recurring-findings cross-check that reads `.decaf/code-reviews/`. So a
decaf-family cell could read the review reports of every decaf cell that ran before it on that
subject, and use them as corroboration — or as the only source of a finding.

The competitor tools (`anthropic-code-review`, `superpowers`, `pr-review-toolkit`,
`tag1-comprehensive-review`) write no artifacts into the tree: zero `CODE_REVIEW_*.md` files
appear in their bundles. The advantage was therefore asymmetric, inflating decaf-family recall
specifically.

Direct evidence — `9__ours-bugs__r1`, on its High #1 finding:

> **Found by** | orchestrator — surfaced via recurring-findings cross-check (Step 7) and
> independently re-verified against the current `node.go`. **Not surfaced by this wave's
> reviewers (a gap for `bugs`/`models=low`).**

That finding was not produced by the tool's own review. It was recovered from a July `ours`
report left behind in the checkout.

## Blast radius

| Cell group | Prior reports visible | Contaminated |
|---|---|---|
| `*__ours__r1` (9 subjects) | 0 | no — the only clean decaf cells |
| `*__ours__r2` (9 subjects) | 1 (own tool's r1) | yes |
| 18 new-variant cells (`ours-bugs`/`ours-review`/`ours-audit` × subjects 1, 5, 9) | 2–3 | yes |

27 cells total, $389.01 of spend, invalidated and reset to `pending`.

The two contaminations differ in kind. The `ours__r2` cells read only their own tool's earlier
repeat: that does not borrow from a competitor, but it makes r2 non-independent of r1, so
`ours`'s repeat-to-repeat agreement was never a real determinism measurement. The 18 variant
cells read *other tools'* reports — a direct cross-tool recall transfer.

## Contents

- `runs/` — the 27 invalidated run directories, exactly as produced.
- `analysis/subject-NN/` — the nine graded analyses. Every one includes `ours__r2` findings, so
  every per-subject leaderboard in here is affected.
- `analysis/synthesis-report.html`, `analysis/synthesis-data.json` — derived from those nine.

`answer-key.json` and `review.diff` were **not** quarantined. They are derived from the PR and
its human review threads, not from any tool's output, so they stay frozen in
`analysis/subject-NN/` and are reused by the re-grade.

`analysis/cbnf-adjudication.json` was also left in place: it is hand-adjudicated work. Its
entries key off cluster ids that the re-grade will renumber, so it needs re-adjudication against
the new clusters before it can be used again.

## The fix

`run_cell.sh` now resets the checkout before **every** cell, outside the early return:

```bash
reset_repo() {
  git -C "$repo_dir" checkout -q -f "$merge"
  git -C "$repo_dir" clean -qxfd
  # refuse to run if anything survives
}
```

`-x` is required because `.decaf/` is untracked and a plain `clean -fd` respects ignore rules.
If the tree is still dirty after the reset the cell refuses to run, exits 77, and is left
`pending` rather than producing another contaminated result.
