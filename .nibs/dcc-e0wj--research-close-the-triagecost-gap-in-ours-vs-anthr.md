---
# dcc-e0wj
version: 1
title: 'Research: close the triage/cost gap in ours vs anthropic-code-review (benchmark findings)'
status: in-progress
type: research
priority: high
estimate: l
created_at: 2026-07-28T18:47:46Z
updated_at: 2026-07-28T20:38:14Z
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
$21.33/run vs $11.82; 14.5 sub-agents vs 10.3 (by role: 9.4 reviewers + 5.1 validators vs 5
reviewers + ~5 auxiliary). Across all subjects ~77% of sub-agent findings
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

**Ours emits ~2× anthropic's total output**, on both dimensions at once. Splitting the agent
counts by role: ours runs **9.4 reviewers + 5.1 validators** per run, anthropic **5 reviewers +
~5 auxiliary** (Haiku triage and scorers). So ours runs roughly **twice the reviewers**, each
emitting 43% more (19.5k vs 13.7k). Anthropic's per-agent figure is the field's outlier *low* —
consistent with its narrow single-purpose briefs and its explicit "avoid reading extra context
beyond the changes" instruction. Note superpowers' lone agent emits the most of anyone (26.3k),
so per-agent verbosity is not inherently bad — what makes ours expensive is paying it ~9 times
over, plus a validation wave on top.

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

### Measured: per-persona value vs. cost (`analysis/scripts/roster_yield.py`)

Counts every cluster a persona reported, **corroborated or not**, against the judge's verdict.
Validators are excluded (they re-verify, never originate). Cost is per-persona sub-agent output,
trustworthy only since #dcc-m8ar. Persona attribution was missing from `analysis.json` for
subjects 2/3/9/10 and half of 6; recovered from each transcript's `attributionAgent` and cached
in `analysis/subject-NN/agent-personas.json` so it survives transcript pruning.

| persona | runs | share | **subst** | v-minor | noise | signal | soleU | tok/subst |
|---|---|---|---|---|---|---|---|---|
| broad-reviewer | 18 | 15.4% | **45** | 20 | 11 | 86% | 12 | 17,406 |
| adversarial-reviewer | 14 | 6.4% | **40** | 2 | 5 | 89% | 12 | **8,138** |
| quick-reviewer | 18 | 11.3% | 29 | 9 | 4 | 90% | 6 | 19,822 |
| design-reviewer | 12 | 5.8% | 24 | 8 | 8 | 80% | 6 | 12,395 |
| knowledge-reviewer | 18 | 5.8% | 18 | 15 | 14 | 70% | 6 | 16,464 |
| test-reviewer | 16 | 9.3% | 14 | **27** | 22 | 65% | 29 | 33,828 |
| spec-compliance-reviewer | 9 | 3.2% | 10 | 3 | 1 | **93%** | 3 | 16,315 |
| prior-feedback-reviewer | 11 | 2.3% | 10 | 2 | 5 | 71% | 2 | 11,811 |
| consistency-reviewer | 18 | 8.0% | 9 | **28** | 20 | 65% | 18 | 45,449 |
| typescript-reviewer | 6 | 4.3% | 9 | 9 | 3 | 86% | 8 | 24,551 |
| performance-reviewer | 12 | 3.8% | 9 | 0 | 3 | 75% | 0 | 21,513 |
| dotnet-reviewer | 6 | 2.8% | 7 | 2 | 2 | 82% | 0 | 20,661 |
| security-reviewer | 3 | 0.7% | 7 | 1 | 3 | 73% | 5 | **5,416** |
| go-reviewer | 4 | 2.5% | 6 | 1 | **7** | **50%** | 1 | 21,226 |
| rust-reviewer | 2 | 0.4% | 1 | 0 | 0 | — | 0 | n=2 |
| finding-validator | 18 | **17.3%** | — | — | — | — | — | n/a by design |

### Correction: "sole-found" was the wrong primary metric

An earlier pass ranked personas by clusters *no sibling also found* and concluded
`performance-reviewer` and `dotnet-reviewer` were droppable. **That conclusion is withdrawn.**

Of the 10 perf-category clusters in the graded set, `ours` found 9, and `performance-reviewer`
was among the finders on **7 of them** — including subject 6's **TP-primary** (an escaped bug)
and three `valid-other`. Its sole-found score is zero only because `broad`, `adversarial`,
and `design` reached the same findings. On participation it sits mid-roster at 75% signal and
21.5k tokens per substantive cluster.

Sole-finding penalises exactly the agents that agree on real bugs, and agreement is not waste:
consolidation *promotes confidence on agreement* (Step 5 rule 4), which is what carries a
finding over the confidence gate and up the ranking. Low soleU with high subst reads as
**reliable corroborator**, not redundant.

### What the corrected table actually supports

- **No persona is dead weight.** Every one participates in substantive clusters.
- **`go-reviewer` is the only genuinely weak signal**: 50% — over half its reports are trivia or
  false positives, worst in the roster by 20 points. n=4 runs, so suggestive, not settled.
- **`rust-reviewer` remains unevaluable** at n=2.
- **`adversarial-reviewer` is the standout**: 40 substantive clusters at 8,138 tok each, second
  only to `security-reviewer`, which has the best ratio in the roster (5,416) on just 3 of 18
  dispatches — its gate looks too tight.
- **`consistency-reviewer` and `test-reviewer` are suggestion engines**, not bug finders: 28 and
  27 valid-minor against 9 and 14 substantive, and the two worst tok/substantive figures
  (45,449 and 33,828). Whether that is money well spent is workstream 3's product question, not
  a defect.
- **The validation wave is still the largest single line item** — 17.3% of sub-agent output,
  more than any reviewer, originating nothing by design. With the always-on floor (broad 15.4%
  + quick 11.3%) that is 44% of sub-agent output spent regardless of the changeset.

`roster_yield.py --simulate=a,b,c` models what dropping a set would have cost, but note it only
counts clusters lost *entirely* — it cannot model the anchor-promotion loss above, so it
systematically flatters any reduction. Treat its output as an upper bound on the saving and a
lower bound on the damage.


- [x] Identify which reviewer personas contribute zero unique clusters across the 9 subjects
      — done, and the framing turned out to be misleading: zero *unique* clusters means
      reliable corroborator, not dead weight. On participation no persona is dead weight;
      `go-reviewer` (50% signal) is the only weak one. See the table above.
- [ ] Test a reduced roster / conditional dispatch and **re-measure recall** — no clear drop
      candidate survived the corrected analysis; `go-reviewer` is the one to test first
- [ ] Re-examine `security-reviewer`'s dispatch gate — best ratio in the roster (5,416
      tok/substantive) yet dispatched in only 3 of 18 runs; it looks too tight
- [ ] Weigh the validation wave against its yield — 17.3% of sub-agent output, the single
      largest line item, and invisible to any finding-yield measure (it refutes, not finds)
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

# Candidate interventions (ranked by measured share × confidence)

Levers that do **not** require removing personas — the corrected roster analysis in workstream 2
found no dead weight. Each names its measured basis, so a failed prototype can be traced to a
wrong premise rather than a wrong implementation.

**First, a correction that reshapes several of these.** The "14.5 sub-agents" figure quoted
throughout this nib is **9.4 reviewers + 5.1 validators** per run. Two consequences:

- The reviewer comparison with anthropic is **9.4 vs 5**, not 14.5 vs 10.3 — both those totals
  include auxiliary agents. Ours runs roughly twice the reviewers, not 41% more.
- **A roster cap of 8 is near-useless.** Step 2b.5 excludes validators from the cap, and the
  review wave already averages 9.4 (range 8–12), so `mid8` drops ~1.4 reviewers and is a literal
  no-op on 6 of 18 runs. The meaningful range is `mid5`–`mid6`.

## 1. A third model tier, aimed at the validation wave

**Basis:** validators are 17.3% of sub-agent output (~13% of session output) and are classified
as *volume* agents in Step 2d, so in `mid` they already run mid-tier. Anthropic does the same job
— score a claim against a fixed 0–100 rubric — with **Haiku**, and posts the study's best
calibration (0.88).

**Change:** add a cheap tier to Step 2d's role split and put the validation wave on it.

**Risk:** low. Coverage unchanged; the task is rubric application, not open-ended reasoning.
Watch for validators losing the ability to *correct findings downward*, a behaviour the Preserve
section says not to regress.

**Measure:** re-run a subset, compare confirmed/refuted/uncertain distribution against the
committed baseline. Cheapest high-share lever here.

## 2. Score before consolidating (the structural difference)

**Basis:** orchestrator thinking is 60% (small subject) to 77% (large) of orchestrator output,
and the orchestrator is 23% of session output. Ours consolidates *everything* (Step 5), then
validates (5.6), then suppresses via the confidence gate — paying frontier-model thinking on
findings it is about to discard. Anthropic scores with Haiku and discards below 80 **before** its
orchestrator does any real reasoning.

**Change:** move a cheap scoring pass ahead of consolidation. The prize is not only the thinking
saved but that the pass could **absorb** the validation wave rather than adding to it — one cheap
pass over raw findings instead of an expensive pass over consolidated ones.

**Risk:** high — it changes the skill's spine, and a hard pre-filter is a commitment to the
"short trustworthy list" product. **Blocked on workstream 3's product decision.**

**Note:** this is also workstream 1's calibration lever; an early cheap filter is what makes a
trustworthy top-of-list possible. The two workstreams converge here.

## 3. Disjoint briefs — attack the 77% restatement

**Basis:** ~77% of sub-agent findings restate a sibling's, and ours emits ~19.5k output per agent
against anthropic's 13.7k. Anthropic's five agents have genuinely disjoint jobs (CLAUDE.md
compliance, shallow bug scan, git history, prior PR comments, code comments). Ours has `broad`,
`quick`, `knowledge`, `consistency` and `adversarial` sweeping overlapping general ground.

**Change:** narrow briefs so agents cannot restate each other.

**Risk:** medium-high, and the failure mode is now well understood — redundancy is *also* what
produces corroboration, and corroboration drives confidence promotion (Step 5 rule 4). Pushed too
far this reproduces the `performance-reviewer` error at roster scale: agents that look redundant
are carrying the anchors.

## 4. Tune gates rather than remove agents

**Basis:** two findings pointing opposite ways.

- **Loosen `security-reviewer`** — best ratio in the roster (5,416 tok/substantive) yet dispatched
  in only 3 of 18 runs. Its gate is starving the cheapest good findings available. This *adds*
  spend and should improve yield per dollar.
- **Tighten `go-reviewer`** — 50% signal, worst in the roster by 20 points. Stack reviewers
  hard-gate on *file presence*; gating on *idiom surface* (goroutines, channels, defer, unsafe)
  would fire them only when their brief applies. Generalizes to all five stack reviewers.

**Risk:** low, and independently testable per gate.

## 5. Price the Considered-But-Not-Flagged channel

**Basis:** every reviewer emits a dismissed-items section and Step 5.5 has the orchestrator reason
over all of them to promote wrongly-dismissed findings. That costs output in every agent plus
orchestrator thinking, and has never been priced against what it recovers.

**Measure this before changing it** — count findings promoted by Step 5.5 across the 18 archived
runs and what the judge made of them. Pure analysis over committed data, no re-runs. If the
promotion rate is near zero the channel is removable; if it recovers substantive findings it
stays and this is closed.

## 6. Shared-context-file pattern (already logged in workstream 2)

Small and free, but the corrected numbers cap the prize: agent prompts are ~a third of the
orchestrator's output, and the orchestrator is 23% of the session. Worth doing for consistency,
not for the saving.

## On what "measuring" costs

**Simulation is free; measurement is not.** `roster_yield.py --simulate` reuses recorded findings
at zero API cost, but it only counts clusters lost *entirely* — it cannot model the
anchor-promotion loss, so it flatters every reduction. Use it to screen, never to decide.

A real measurement means re-running cells: [Estimate] ~$18/run for a reduced roster against the
$21.33 baseline, so ~$320 for the full 9-subject × 2-repeat sweep, ~$160 for a single-repeat
sweep that gives up stochasticity control — plus blind re-grading on top. Budget accordingly and
prefer interventions that can share one re-run.

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
