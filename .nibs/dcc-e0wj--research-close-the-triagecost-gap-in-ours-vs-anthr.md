---
# dcc-e0wj
version: 1
title: 'Research: close the triage/cost gap in ours vs anthropic-code-review (benchmark findings)'
status: in-progress
type: research
priority: high
estimate: l
created_at: 2026-07-28T18:47:46Z
updated_at: 2026-07-28T20:21:29Z
order: zzw
---

# Why

The controlled benchmark (#dcc-z1xw) now has 9 of 12 subjects graded — 90 blind-graded runs,
$1,096 spend. On the headline metrics `ours` loses to the built-in `anthropic-code-review`:

| per run | anthropic | ours |
|---|---|---|
| escaped bug caught | 18/18 | 16/18 |
| substantive share | 49% | 36% |
| severity calibration | **0.88** | **0.62** |
| cost | $11.82 | **$21.33** |
| findings emitted | 9.8 | 15.8 |

But the naive reading ("ours reports more, but not what you want") is **wrong**, and the
correction is what makes this actionable. Ours finds *more* of what you want, at every PR size:

| per run | anthropic | ours |
|---|---|---|
| substantive findings | 4.2 | **5.7** |
| + valid-minor | 2.1 | **4.8** |
| **useful total** | 6.3 | **10.5** |
| noise (trivia + FP) | 2.9 | 5.3 |
| signal:noise ratio | 2.2 | 2.0 |
| false positives | 0.39 | **0.33** |

Ours delivers **+67% useful findings for +80% noise and +80% cost**, at an essentially
identical signal:noise *ratio*. So this is a **triage and cost problem, not a detection
problem** — which is the tractable direction.

Synthesis: `competition/benchmark/analysis/synthesis-report.html` · data:
`synthesis-data.json` · per-subject: `analysis/subject-NN/report.md`.

# Workstreams (ranked by leverage)

## 1. Severity calibration — the single widest gap
`P(substantive | tool said critical/high)` = 0.62 vs anthropic's 0.88. With 15.8 findings per
run and an untrustworthy top-of-list, a reader cannot skim and stop — they must read everything.
This is a **consolidation/ranking failure, not a reviewer failure**: the review agents are
finding the material, the consolidation step is failing to rank it.

- [ ] Determine why consolidated severity diverges from judged severity (compare each subject's
      `analysis.json` `reported_by[].severity` against `judged_severity`)
- [ ] Look for a systematic bias (e.g. doc/comment findings promoted to high; is `critical` used
      for anything that isn't behavioral?)
- [ ] Prototype a stricter severity contract in the consolidation step and re-measure

## 2. Cost / fan-out efficiency
$21.33/run vs $11.82; 14.5 sub-agents vs 10.3. Across all subjects ~77% of sub-agent findings
restate a sibling's. Cost scaled steeply with repo size (~$14.7 efcore-small → ~$29.5
vscode-large) while superpowers stayed ~flat at $2.5.

### Where the output actually goes (corrected 2026-07-28)

The token figures this workstream originally quoted were wrong — sub-agent output was
under-counted ~10× by the aggregation bug in #dcc-m8ar (now fixed, all 90 runs backfilled).
Corrected, per run:

| tool | agents | orchestrator out | session out | orch share | out **per agent** | $/run |
|---|---|---|---|---|---|---|
| superpowers | 1.0 | 6,175 | 32,456 | 19% | 26,281 | 2.44 |
| pr-review-toolkit | 5.0 | 21,296 | 126,074 | 17% | 20,956 | 8.56 |
| anthropic | 10.3 | 45,114 | 186,380 | 24% | **13,671** | 11.82 |
| tag1 | 10.4 | 61,303 | 264,463 | 23% | 19,555 | 16.72 |
| **ours** | **14.5** | 84,533 | **367,084** | 23% | 19,486 | 21.33 |

**The orchestrator is 17–24% of output in every tool** — remarkably uniform, and not where the
money is. Session output predicts billed cost at **r = 0.967** (orchestrator output alone:
0.874), so session output is the right cost proxy.

**Ours emits ~2× anthropic's total output**, and it does so on both dimensions at once: 41%
more agents (14.5 vs 10.3), each emitting 43% more (19.5k vs 13.7k). Anthropic's per-agent
figure is the field's outlier *low* — consistent with its narrow single-purpose briefs and its
explicit "avoid reading extra context beyond the changes" instruction. Note superpowers'
lone agent emits the most of anyone (26.3k), so per-agent verbosity is not inherently bad —
what makes ours expensive is paying it 14.5 times over.

### Within the orchestrator, the cost is reasoning — so there is no prompt-engineering fix

Decomposing the orchestrator transcripts (dedupe by `message.id`, taking the **last** usage
record per id — see #dcc-m8ar; the orchestrator figures were unaffected by that bug and
reconcile to `meta.json` exactly):

| | small — `1__ours__r1`, $14.61, 16 agents | large — `9__ours__r1`, $34.88, 20 agents |
|---|---|---|
| orchestrator output tokens | 89,170 (11 API responses) | 107,402 (26 responses) |
| agent prompts (`tool_use`) | 35.2k — 39% | 23.1k — 22% |
| visible text | 0.2k — <1% | 2.1k — 2% |
| **thinking (residual)** | **53.7k — 60%** | **82.2k — 77%** |

The thinking share *grows* as the job grows. That residual is Steps 5 / 5.5 / 5.6 — severity
normalization, dedup within 3 lines, confidence promotion, re-evaluating every agent's
dismissed-items list, validator selection and verdict processing. It is the one job no
sub-agent can take: the orchestrator is the only component holding all 16–20 reports at once,
and you cannot dedupe findings you cannot see together. Its mechanical share is 22–39% and
shrinking — so trimming prompts cannot move ours' cost. **Roster size can**: within ours,
r = 0.694 between sub-agent count and orchestrator output; small 12.4 agents/$16.77 → large
18.2 agents/$29.86.

### The orchestrator already invented an optimization we never documented

On the small subject it pasted the diff into **all 10 reviewer prompts** (8 of 10
byte-identical, ~63.6k chars ≈ 15.9k tokens) and re-composed the working-tree safety preamble
10 times (9 of 10 *distinct* hashes — it rewrites rather than copies, ~5.4k tokens).

On the large subject it did none of that: it wrote `/tmp/pr130837.diff` plus a
`/tmp/pr130837_context.md` and pointed all 20 agents at the files. **0 of 20 prompts contain a
diff**; prompts averaged 2.2 KB against 6.8 KB on the small subject.

`code-review/SKILL.md:253` says only `<paste git diff or file content here>`. The
shared-context-file pattern is emergent behavior that appears when the diff is big and is
skipped when it is small — exactly backwards from where the saving is free. Worth documenting,
though the corrected numbers above cap the prize: prompts are ~a third of a fifth of session
output.

### Filter *before* consolidating — the structural difference with anthropic

Anthropic scores every issue with a **Haiku** agent and discards below 80 *before* its
orchestrator does any real reasoning. Ours consolidates everything (Step 5) and validates
afterwards (Step 5.6) — so ours pays frontier-model thinking on findings it is about to throw
away. Same insight, opposite order. This is also workstream 1's calibration lever: an early
cheap filter is what makes a short trustworthy list possible.

### Measured: per-persona yield vs. cost (`analysis/scripts/roster_yield.py`)

A cluster is **sole-found** by persona P in a run when P is the only `ours` reviewer that
reported it — i.e. what that run would have lost had P not been dispatched. Validators are
excluded (they re-verify, never originate). Cost is per-persona sub-agent output, trustworthy
only since #dcc-m8ar. Persona attribution was missing from `analysis.json` for subjects 2/3/9/10
and half of 6; it is recovered from each transcript's `attributionAgent` and now cached in
`analysis/subject-NN/agent-personas.json`, so the analysis survives transcript pruning.

| persona | runs | tok/run | share | sole | subst | v-minor | noise | tok/useful |
|---|---|---|---|---|---|---|---|---|
| adversarial-reviewer | 14 | 23,251 | 6.4% | 13 | **12** | 0 | 1 | 27,126 |
| test-reviewer | 16 | 29,600 | 9.3% | 49 | 8 | **21** | 20 | 16,331 |
| broad-reviewer | 18 | 43,515 | **15.4%** | 18 | 5 | 7 | 6 | 65,272 |
| quick-reviewer | 18 | 31,935 | 11.3% | 6 | 4 | 2 | 0 | 95,804 |
| security-reviewer | 3 | 12,637 | 0.7% | 7 | 4 | 1 | 2 | **7,582** |
| spec-compliance-reviewer | 9 | 18,128 | 3.2% | 4 | 3 | 0 | 1 | 54,384 |
| consistency-reviewer | 18 | 22,724 | 8.0% | 36 | 2 | 16 | 18 | 22,724 |
| design-reviewer | 12 | 24,791 | 5.8% | 8 | 2 | 4 | 2 | 49,582 |
| prior-feedback-reviewer | 11 | 10,737 | 2.3% | 5 | 2 | 0 | 3 | 59,054 |
| knowledge-reviewer | 18 | 16,464 | 5.8% | 14 | 1 | 5 | 8 | 49,391 |
| typescript-reviewer | 6 | 36,826 | 4.3% | 10 | 0 | 8 | 2 | 27,620 |
| go-reviewer | 4 | 31,840 | 2.5% | 3 | 0 | 1 | 2 | **127,359** |
| **performance-reviewer** | 12 | 16,135 | 3.8% | 3 | **0** | **0** | 3 | — |
| **dotnet-reviewer** | 6 | 24,105 | 2.8% | 1 | **0** | **0** | 1 | — |
| rust-reviewer | 2 | 10,639 | 0.4% | 0 | 0 | 0 | 0 | — |
| **finding-validator** | 18 | 48,850 | **17.3%** | — | — | — | — | n/a by design |

**The largest line item is the validation wave** — 17.3% of sub-agent output, more than any
reviewer, originating nothing by construction. Its value is refuting false findings, which this
table cannot see. Add the always-on floor (broad 15.4% + quick 11.3%) and **44% of sub-agent
output goes to machinery that runs regardless of the changeset**.

**Zero useful sole clusters:** `performance-reviewer` (12 dispatches, 12 clusters reported, 3
sole — all noise) and `dotnet-reviewer` (6 dispatches, 1 sole, noise). `rust-reviewer` also
scores zero but at n=2 that is no evidence. `go-reviewer` is the worst ratio among personas that
produced anything at all: 127k tokens per useful sole cluster.

**Best value:** `security-reviewer` at 7,582 tok/useful — the best ratio in the roster, and
dispatched only 3 times in 18 runs, so its gate looks too tight. `test-reviewer` has the highest
absolute useful yield (29 sole clusters). `adversarial-reviewer` produces the most *substantive*
sole findings of any persona (12) at a mid-range cost.

### Simulated reduction — free on this evidence, but not yet re-measured

`roster_yield.py --simulate=performance-reviewer,dotnet-reviewer,go-reviewer,rust-reviewer`:

| | kept | lost |
|---|---|---|
| TP-primary | 27 | **0** |
| TP-human | 6 | **0** |
| valid-other | 67 | **0** |
| valid-minor | 87 | 1 |
| trivia | 70 | 6 |
| false-positive | 6 | 0 |

**9.6% of sub-agent output saved (486,887 of 5,085,915 tokens), zero substantive clusters lost,
one suggestion lost, six trivia removed** — signal:noise improves slightly.

Three caveats before acting on it:

1. **It is a simulation over recorded findings, not a re-run.** It assumes surviving agents
   report exactly what they reported.
2. **Removing corroborators can lower confidence anchors.** Consolidation promotes confidence on
   agreement (Step 5 rule 4), so dropping a persona that never *uniquely* finds anything can
   still push a surviving finding below the confidence gate. Sole-found systematically
   undercuts corroboration value — which is precisely why the floor agents look expensive here.
3. **Stack reviewers are hard-gated**, so each sees only its language's subjects: rust n=2,
   go n=4, dotnet n=6. Only `performance-reviewer` (n=12) is on solid ground.


- [x] Identify which reviewer personas contribute zero unique clusters across the 9 subjects
      — done: `performance-reviewer` and `dotnet-reviewer` contribute zero useful sole
      clusters; see the table above and `analysis/scripts/roster_yield.py`
- [ ] Test a reduced roster / conditional dispatch and **re-measure recall** — the simulation
      above says dropping performance/dotnet/go/rust costs 0 substantive clusters for 9.6% of
      sub-agent output, but only a re-run settles the anchor-promotion effect (caveat 2)
- [ ] Re-examine `security-reviewer`'s dispatch gate — best ratio in the roster (7,582
      tok/useful) yet dispatched in only 3 of 18 runs; it looks too tight
- [ ] Weigh the validation wave against its yield — 17.3% of sub-agent output, the single
      largest line item, and invisible to a finding-yield measure (it refutes rather than finds)
- [ ] Investigate why cost scales with *repo* size rather than *diff* size
- [ ] Compare per-agent output against anthropic's 13.7k — are ours' reviewers reading and
      restating more context than their brief needs?
- [ ] Make the shared-context-file pattern the documented default in `code-review/SKILL.md`
      (reviewers all have Bash; write the diff once, pass a path) and re-measure a small subject
- [ ] Prototype a cheap pre-consolidation confidence filter (anthropic's Haiku-scorer shape) and
      measure its effect on orchestrator thinking tokens, recall, and calibration
- [ ] Re-measure ours at a cheap tier (`low`, `mid3`) on the benchmark subjects — never measured;
      the study ran `ours` at `mid` only. Gates the cost case in #dcc-05uw

## 3. Volume dilution
Beyond anthropic's ~10-finding baseline, ours' extra 5.9 findings/run convert at only **25%
marginal precision** (vs 49% baseline) — ~$6.33 per extra substantive finding.

- [ ] Decide the intended product: a short trustworthy list, or exhaustive coverage with tiers?
- [ ] If coverage: make the tiering explicit in the report so trivia is visibly separated
      (the grading rubric's valid-minor/trivia split is a usable model)

## 4. Retrieval gap (one concrete miss)
The only subject ours missed in both repeats (subject 4, typescript/small) was a downstream-only
regression, invisible in the diff — it changed the token stream a public API returns and only
crashed external consumers. anthropic caught it by pulling the revert commit from git history.

- [ ] Evaluate adding a history/blame retrieval step
- [ ] **Trade-off to weigh:** that same retrieval channel produced anthropic's worst false
      positive — a hallucinated claim that "a maintainer flagged this on the PR" when the PR had
      no such comment. Any retrieval must verify claims against merged code before reporting.

# Preserve — behaviours the metrics do not capture

Do not regress these while optimizing:
- Validator sub-agents **correcting their own findings downward** rather than inflating them
  (observed subjects 5 and 7)
- Verifying historical review threads against the **merged** code before re-raising
  (subject 6: correctly identified that 3 of 5 bot threads were already fixed)
- Lowest-but-one false-positive rate of the fan-out tools

# Acceptance

- [ ] Root cause identified for the calibration gap, with evidence from the graded data
- [ ] At least one change prototyped and re-measured on a subset of benchmark subjects
      (re-run cells, re-grade blind, compare against the committed baseline)
- [ ] Written recommendation: what to change, expected effect on calibration / cost / recall,
      and what was deliberately not changed

# Caveats on the evidence

- Recall comparison rests on ~2 hard subjects of 9; treat 18/18 vs 16/18 as suggestive
- `precision` gives no credit for valid-minor by construction — that is where much of ours'
  extra volume lands, and it has real value in a fix-and-rerun loop
- The rubric was authored in-house; grading was blind and tool-blind, but the definition of
  "substantive" may still favour a particular reporting style
- 3 subjects (go/medium, rust/medium, rust/large) are unrun — conclusions may shift

## Related
- #dcc-z1xw — the benchmark that produced this evidence
- #dcc-m8ar — per-sub-agent token capture is unreliable; blocks splitting cost between the
  orchestrator and its sub-agents (workstream 2)
- #dcc-05uw — pluggable review backend (complementary: that nib is about *choosing* a cheaper
  backend per project; this one is about making the deep backend better)
