# Benchmark v2 pilot — results and full-run recommendation (nib `dcc-vkeh`)

Ran 2026-08-11 to 2026-08-13. **35 of 35 cells completed, every cell isolation-CLEAN, zero runner
errors.** Roughly $820 all-in: $539 in matrix cells, $99 in probes, $35 wasted on two failed cells,
the rest in scoring.

The pilot's job was to answer whether the instrument works *before* the full run spends against all
12 subjects. It does — with four qualifications that change how the full run must be designed and
what may be published from it.

---

## What ran

| Subject | Shape | Vintage | Cells | Findings | Clusters | Grading passes |
|---|---|---|---|---|---|---|
| `prometheus/prometheus#18081` | library/L | out-of-window | 14 (7 tools × 2) | 371 | 129 | 2 |
| `dotnet/efcore#34127` | library/M | out-of-window | 14 (7 tools × 2) | 261 | 69 | 2 |
| `grafana/grafana#122269` | backend/M, **null arm** | in-window | 7 (7 tools × 1) | 161 | 69 | 2 |

Roster, all seven: `ours-bugs`, `ours-review`, `ours-audit`, `anthropic-code-review`, `superpowers`,
`pr-review-toolkit`, `comprehensive-review`. The last three were wired for this pilot; all three ran
without modification to the tools themselves.

The null arm is `in-window` by design — soak time beats vintage there, and a memorized null subject
deflates the noise floor, which is the safe direction. Its numbers are never pooled with the citable
subjects.

---

## Acceptance items

| # | Item | Status |
|---|---|---|
| 1 | `run_cell_v2.sh` runs against pooled fixtures, every roster tool has a working invocation | **met** — 7/7 tools, probed before spending |
| 2 | 2 subjects × roster × 2 repeats, clean leak audits | **met** — 28 pooled cells, all CLEAN |
| 3 | Judge stability measured by blind re-judge, disagreement rate reported | **met** — five independent measurements |
| 4 | Tools measurably separate on pooled precision | **met** — 0.46 to 1.00, with a hard caveat below |
| 5 | Thread recall as its own axis, plus judge-dismissed threads | **met** — reported separately; zero dismissals anywhere |

---

## Finding 1 — the judge is stable, and it is not the biggest problem

Thresholds were pre-registered in `scoring/judge_stability.py` and committed (`b9de687`) before any
grading pass ran, so the verdict could not be drawn around the result. Every pass 2 ran as a separate
process on a differently-shuffled payload — blind to pass 1 by construction, not by instruction.

| Measurement | exact | real/not-real κ | `valid-other`/`trivia` κ | verdict |
|---|---|---|---|---|
| prometheus r1 | 0.889 | 0.78 | 0.737 | STABLE |
| efcore r1 | 0.929 | 0.871 | 0.779 | STABLE |
| efcore r1+r2 | 0.899 | 0.855 | 0.757 | STABLE |
| prometheus r1+r2 | 0.899 | 0.862 | 0.738 | STABLE |
| null arm | 0.913 | 0.757 | 0.733 | STABLE |

Floors were κ ≥ 0.60 and exact ≥ 0.70. Five for five, comfortably. **The `valid-other`/`trivia`
boundary — the single load-bearing subjectivity in the design — reproduces at κ 0.733 to 0.779.**

**Judge calibration is clean.** `judge_dismissed_reported_threads` is zero on every subject in every
pass: not once did the judge rule "not real" on something a tool raised and an expert human reviewer
had also raised.

---

## Finding 2 — the denominator dominates, not the source of variance

This is the pilot's most consequential result, and it took both subjects at 2 repeats to see.

Isolating each source separately and reading the maximum per-tool delta **reverses between
subjects**:

| Subject | judge (2 passes, same cells) | tool (2nd repeat, same pass) |
|---|---|---|
| efcore | 0.25 | 0.12 |
| prometheus | 0.13 | **0.40** |

Prometheus's 0.40 is entirely `ours-bugs`, whose precision was 1.00 over **three** reported clusters
at r1 and 0.60 over five once r2 was added. That is not a tool changing behavior; it is a figure that
was never a measurement. Pooling all 14 tool-subject pairs and splitting by denominator gives the
real structure:

| reported clusters | mean tool Δ | mean judge Δ |
|---|---|---|
| n < 10 (4 pairs) | 0.100 | 0.163 |
| n ≥ 10 (10 pairs) | 0.056 | 0.085 |

**Both sources roughly halve at n ≥ 10, and the judge is the larger term at both sizes.** So the
direction efcore suggested was right, prometheus's apparent reversal was an artifact, and the effect
that matters most is neither source: it is how many clusters the tool reported.

### What this means for the full run

1. **Do not publish a precision figure over fewer than 10 reported clusters.** Report the raw count
   instead ("reported 3 findings, all real"). Four of fourteen pairs here fall below that line, and
   every unstable figure in the pilot is one of them. This costs nothing.
2. **Two grading passes per subject, always.** Judge Δ is the larger term at both sizes and passes
   consume no cells.
3. **Keep two repeats** — but for a different reason than the design assumed. Not to stabilize
   precision, but because reported *volume* is unstable in a way no amount of re-grading reveals:
   `anthropic-code-review` reported 1 finding then 4 on identical efcore code; `ours-review` went 11
   to 20 on prometheus.

An earlier version of this recommendation favoured grading passes *over* repeats, projecting a
~$1,200 saving on the full run. It rested on one subject and is withdrawn. Both controls are needed.

---

## Finding 3 — the null arm found real defects, so it is not a noise floor

`grafana/grafana#122269` was selected by `NULL-ARM.md` on "no revert, no linked regression issue, no
follow-up fix touching the same lines." The blind grader — **not told it was a null subject**, which
would have made the measurement circular — rated **14 of 69 clusters `valid-other`**, ten of them
confirmed by both passes. Two were found by all seven tools independently:

- the `grafana-cli` accessor applies the new proxy token with **no feature-toggle check**, so the CLI
  uses a different credential than the server
- the docs name the toggle without its registered `grafana.` prefix, so an operator who follows them
  **does not enable the feature**

That selection procedure establishes nobody *reported* a defect, not that there isn't one.

Two consequences:

**Precision does not separate a defect-laden change from a defect-free one.** Ranges: prometheus
0.46–1.00, efcore 0.50–1.00, null 0.38–0.83. The downward shift is real but small against the spread.
**Precision measures whether what a tool said is defensible, not whether it found the bug.** The
thread axis remains the only answer to the second question, and any published precision figure must
say so.

**One false positive in 161 findings across seven tools on the null subject** (three across all 793
findings in the pilot). These tools essentially do not invent defects. Their failure mode is
immateriality — on the null subject, 32 trivia and 22 valid-minor clusters against 14 real ones.

---

## Finding 4 — count reproduces, identity does not

For the thread axis, "the field caught N of M" is reproducible; "these specific ones were missed" is
not. On efcore, pass 1 missed threads {7,8,9} and pass 2 missed {1,2,9} — one in common, same total.

**`threads.missed_index` must never be published from a single grading pass.** Report the count.

---

## Tool results

Reported with every caveat above in force. Precision figures over n < 10 are struck through in
spirit — they are shown only with their n.

| Tool | prom precision (n) | efcore precision (n) | prom recall | efcore recall | $/real (prom) |
|---|---|---|---|---|---|
| `anthropic-code-review` | 1.00 (7) | 1.00 (4) | 0.20 | 0.10 | $3.64 |
| `superpowers` | 0.79 (28) | 0.53 (17) | **0.70** | 0.20 | **$0.42** |
| `comprehensive-review` | 0.74 (23) | 0.89 (18) | **0.70** | 0.50 | $2.79 |
| `ours-bugs` | 0.60 (5) | 1.00 (2) | 0.10 | 0.00 | $6.00 |
| `pr-review-toolkit` | 0.57 (30) | 0.50 (24) | 0.60 | 0.30 | $2.53 |
| `ours-review` | 0.50 (24) | 0.60 (15) | 0.60 | 0.20 | $3.17 |
| `ours-audit` | 0.46 (54) | 0.50 (24) | 0.60 | 0.50 | $2.39 |

**The precision/recall inversion reported at r1 does not survive two repeats.** At single-repeat
strength the two precision-1.00 tools had the worst thread recall on both subjects, which looked like
a real trade-off. At full strength `superpowers` holds precision 0.79, joint-best recall 0.70, three
unique real findings, and the lowest cost per real finding in the roster — four axes at once. The
inversion was an n=1 artifact.

`ours-bugs` and `anthropic-code-review` sit below the n ≥ 10 floor on both subjects. Their precision
figures are not results; what can be said is that they report very little (1–7 clusters) and that
almost all of it is real.

`ours-audit` reports the most by a wide margin (54 clusters on prometheus, 27 per cell) and carries
the most unique real findings (5), at the cost of the lowest precision.

---

## Harness defects found and fixed

Five, all found by *running* the harness rather than reading it, and four of them silent — the run
completes and the artifacts look well-formed.

| Defect | Why nothing caught it | Direction of bias |
|---|---|---|
| `final-output.md` is only `.result`, the last assistant message | File non-empty and plausible | Deletes findings from tools that keep working after reporting (`comprehensive-review` at 5–20%) |
| Tools leave git worktrees outside the checkout | `git status` blind to them, `clean -xfd` can't reach, fs hook guards only `competition/benchmark/` | Cross-cell state (`dcc-2cxq` shape, new channel) |
| Tool-written reports destroyed by the next cell's reset | Each layer well-formed alone | Deletes findings from tools that file reports (`ours-audit`: 73,701 B vs 5,062 chars terminal — 6.4% would have been scored) |
| `/tmp` is tmpfs; a cell exhausted RAM and aborted | Looks identical to a crash or a quiet tool | Lost one cell, $18.68 |
| Resume skipped cells that failed *with partial output* | Emptiness was guarded; partial success was not | Would have silently scored the null arm with six tools instead of seven |

The `.result` truncation and the report destruction push in **opposite** directions on **different**
tools, so they would not have cancelled — they would have scrambled the ranking while every artifact
looked healthy.

---

## The access controls were exercised, not merely installed

`anthropic-code-review` r2 on prometheus logged **22 `gh` DENY against 23 ALLOW** — the only cell to
hit the shim hard. It attempted `gh pr view 18081` (the subject PR itself) twice,
`api .../pulls/10369/reviews`, `api .../issues/10369/comments`, five `pr view --comments`, six
`commits/<sha>/pulls`, and six `pr list --json mergedAt`. Every one refused — including by the field
allowlist and the bare-`pr view` block that `dcc-3cm6` added only after probing found them leaking.

Its r1 on the same subject made zero denied attempts. **A single-repeat design would have recorded
this harness's most important validation as never having happened.**

---

## What may and may not be said from this pilot

**May be said:**

- The instrument discriminates. Tools separate on precision and on thread recall, and the separation
  survives two grading passes for every tool above the n ≥ 10 floor.
- The judge is stable at the boundary the design depends on, five times over, against pre-registered
  thresholds.
- These tools do not invent defects — 3 false positives in 793 findings.
- On a change nobody thought had problems, seven tools found 51 real cluster-memberships.

**May not be said:**

- Any per-tool ranking from a single repeat or a single grading pass.
- Any precision figure over fewer than 10 reported clusters.
- Which specific threads the field missed, from one pass.
- Anything about the five in-window subjects pooled with the citable seven.
- Anything at all from v1.

---

## Recommendation for the full run

**The instrument is fit to run.** Design changes required first:

1. Enforce the n ≥ 10 publication floor in `score_pooled.py` — emit the count, refuse the ratio.
2. Two grading passes per subject as standard; report per-tool figures as median with observed range.
3. Keep two repeats.
4. `threads.missed_index` reported only where passes agree.
5. Re-examine the null arm's selection procedure (`dcc-mjj5`) — "no known defect" did not survive
   contact with seven review tools, and a second null subject chosen the same way likely will not
   either.

[Inference] Cost at pilot rates: ~$210 per subject for 14 cells plus two grading passes. Twelve
subjects ≈ **$2,500**, or ~$1,500 for the citable seven. The pilot cost ~$820 to establish that
number is worth spending.
