# Arm renames, 2026-08-19

`bugs` is the argument passed to the skill, so `ours-bugs` must be the arm that measures it. On
2026-08-19 it did not: **every scoreable `ours-bugs` cell was the four-seat wave, while its
invocation (`bugs --report`) had meant the single seat since 2026-08-18** (`dcc-pjix`). The id meant
one thing in its data and another in its command.

| before | after | why |
|---|---|---|
| `ours-bugs` (13 cells, all wave) | **`ours-bugs-wave`** | the data is the wave; the name should say so |
| `ours-bugs-sp3` (12 cells, single seat) | **`ours-bugs`** | this is what `bugs` now invokes |

One cell did not move: `mattermost…ours-bugs__r0`, the single-seat probe from `dcc-pjix` (Opus only).
It was already the single seat and keeps the `ours-bugs` id. It is a probe and is never scored.

## What was rewritten, and what deliberately was not

**Rewritten** — run directory names, `extract/*.json` filenames and their `tool` field,
`analysis.json` (`cells[].tool` and `clusters[].reported_by[].tool`), `findings.json`,
`grading/analysis-pass2.json`, `grading/metrics-pass2.json`, `tools.json`, `run_cell_v2.sh`.
`metrics.json` and the fact tables were regenerated from source.

**Not rewritten** — each cell's own `access.log`, `isolation.txt`, `tmp-cleanup.tsv` and the
`pilot-*.tsv` run logs still carry the old paths. Those record what happened at run time; editing
them would falsify the record rather than correct it.

**Not rewritten** — prose in `BUGS-SP-RESULTS.md`, `PROPOSAL-BUGS-SP.md`, `REVIEW-POSTDDUY.md` and
the nibs. Those documents distinguish `ours-bugs` from `ours-bugs-sp3` in arguments that were true
when written, and a find-replace would corrupt statements that are genuinely about the wave. **When
reading anything written before 2026-08-19: `ours-bugs` there means the wave, and `ours-bugs-sp3`
means what is now `ours-bugs`.**

## Verification

The figures moved with the names and did not change: `ours-bugs` now reports pool hit/cell **0.354**
on prometheus+efcore (`ours-bugs-sp3`'s figure) and `ours-bugs-wave` reports **0.438** (the old
`ours-bugs`' figure). `check_artifacts.py` passes on all six subjects, `score_pooled.py` on all five
pooled, the fact tables round-trip, and all four test suites pass — including `test_reversals.py`,
which asserts exact numeric figures.

The model-set guard now also says the right thing about each: it refuses `ours-bugs-wave`, whose
cells genuinely mix pre-dduy Haiku seats with post-dduy Sonnet seats, and does not flag `ours-bugs`,
which is Opus-only throughout.

## Retired in the same change

`ours-bugs-wave`, `ours-bugs-narrow`, `ours-bugs-reachnorm`, `ours-bugs-sp`, `ours-bugs-sp2` are all
flagged `retired` in `tools.json` and refused by `run_cell_v2.sh` (exit 81). Their cells remain
citable; they must not produce new ones. `ours-bugs-narrow` and `ours-bugs-reachnorm` were the
isolated `dcc-tmz2` experiment that established what `bugs` should mean; the question is answered and
neither is a shipping configuration.

**Live arms:** `ours-bugs`, `ours-review`, `ours-audit`, `superpowers`, `anthropic-code-review`,
`pr-review-toolkit`, `comprehensive-review`.
