---
# dcc-e0wj
version: 1
title: 'Research: close the triage/cost gap in ours vs anthropic-code-review (benchmark findings)'
status: in-progress
type: research
priority: high
estimate: l
created_at: 2026-07-28T18:47:46Z
updated_at: 2026-07-29T11:06:08Z
order: zzw
---

# Why

The controlled benchmark (#dcc-z1xw) now has 9 of 12 subjects graded — 90 blind-graded runs,
$1,096 spend. On the headline metrics `ours` loses to the built-in `anthropic-code-review`:

| per run | anthropic | ours |
|---|---|---|
| escaped bug caught | 18/18 | 16/18 |
| substantive share | 49% | 36% |
| severity calibration | **0.88** | **0.62** † |
| cost | $11.82 † | **$21.33** |
| findings emitted | 9.8 | 15.8 |

† **Superseded on two counts.** (1) That 0.62 is max-severity-over-sub-agents, not what the
consolidated report tells a reader — on the artifact a reader sees, ours is **0.77**. (2) Every
anthropic figure in this table came from a column blended with contaminated cells (#dcc-9kkz).
Clean: anthropic **$7.61/run**, calibration **0.92**, 56% substantive share, 18/18 recall. Ours is
unchanged, so the cost ratio is **2.8×**, not 1.8×.

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
`P(substantive | tool said critical/high)` = 0.62 vs anthropic's 0.88.

> **The premise below was wrong and is corrected in "Root cause" — this is *not* a
> consolidation failure. Consolidation measurably *improves* calibration; the over-claiming
> happens in the reviewers, and one persona accounts for most of it.**

~~With 15.8 findings per run and an untrustworthy top-of-list, a reader cannot skim and stop —
they must read everything. This is a consolidation/ranking failure, not a reviewer failure: the
review agents are finding the material, the consolidation step is failing to rank it.~~ The
reader-facing problem is real; the attribution was not.

### Root cause (measured over the 9 graded subjects)

**1. The headline 0.62 does not measure what a reader sees.** `compute_metrics.py::_calibration`
takes the **max severity across every `reported_by` entry**, which includes each sub-agent's own
claim. A reader never sees those — they see the consolidated report. Splitting the two:

| tool | max-over-agents | consolidated report only |
|---|---|---|
| superpowers | 0.65 | 0.65 |
| pr-review-toolkit | 0.47 | 0.50 |
| anthropic | 0.83 | **0.88** |
| tag1 | 0.55 | 0.79 |
| **ours** | 0.65 | **0.77** |

`superpowers` is the control: one agent, so consolidated *is* the max, and the two agree exactly.
The fan-out tools all improve, ours most of all — **consolidation raises calibration from 0.65 to
0.77**, and halves the number of critical/high claims (60 → 30). It is doing the ranking job,
not failing it. The real gap to anthropic is **0.77 vs 0.88**, roughly 40% of what was believed.

**2. The residual gap is entirely a category-boundary problem.** Of ours' 30 consolidated
critical/high clusters, 23 were judged substantive. Split by category:

| category | flagged crit/high | substantive | miss |
|---|---|---|---|
| logic | 10 | 9 | 1 |
| bug | 9 | 8 | 1 |
| perf | 3 | 3 | 0 |
| **doc** | **3** | **0** | **3** |
| design | 2 | 1 | 1 |
| test | 2 | 1 | 1 |
| security | 1 | 1 | 0 |

**Behavioral findings are already well calibrated** — logic + bug = 17/19 = **0.89**, matching
anthropic's overall figure. Non-behavioral ones are not: doc + test + design = 2/7 = **0.29**.
Ours does not have a general ranking problem; it ranks non-behavioral findings as if behavioral.

**3. The mechanism, traced end to end.** `knowledge-reviewer=critical` appears in **4 of the 7**
miscalibrated clusters — in three of them as the *sole* critical against a chorus of low/medium:

- `decaf-quality/agents/knowledge-reviewer.md:41` — "**MUST severity is reserved for RULE 0**
  (knowledge loss)", so every missing-decision-log / undocumented-assumption /
  comprehension-risk finding is emitted as MUST.
- `code-review/SKILL.md:326` rule 1 — "Normalize severities across agents (**MUST → Critical**)".
- `code-review/SKILL.md:328` rule 3 — "Keep the highest severity among duplicates … **a
  specialist's Critical is never outvoted by lower ratings**."

So "this decision should be documented" lands at the same rank as silent data corruption, and
three or four dissenting `low` ratings cannot pull it down. Worked example, subject 1: a finding
that test comments narrate change history was rated `low` by broad, consistency and test — and
shipped as **Critical** on the knowledge-reviewer's MUST alone.

### Quantified fix

| variant | calibration | flagged |
|---|---|---|
| as shipped | 0.77 | 23/30 |
| **cap `doc` category at Medium** | **0.85** | 23/27 |
| demote a lone Critical against 2+ Low dissent | 0.77 | 23/30 |

Capping doc at Medium **loses zero substantive findings** — across all 9 subjects and every tool
there are only 2 substantive doc-category clusters (against 24 valid-minor and 26 trivia), and
neither was among ours' critical/high set. It closes most of the remaining gap to 0.88.

The dissent-based demotion does **nothing** here: `knowledge-reviewer` rates these critical in
*both* repeats, so a "lone critical" test never fires. Rule 3 is not the lever; the MUST→Critical
mapping is.

- [x] Determine why consolidated severity diverges from judged severity — done; and the divergence
      is much smaller than the headline metric implies (0.77, not 0.62)
- [x] Look for a systematic bias — found: non-behavioral categories ranked as behavioral, via
      `knowledge-reviewer`'s MUST → Critical normalization
- [ ] Prototype a stricter severity contract in the consolidation step and re-measure — scoped:
      either cap non-behavioral categories at Medium in rule 1, or stop mapping the
      knowledge-reviewer's RULE 0 MUST onto Critical. Prefer the latter: it fixes the source
      rather than patching the symptom, and leaves a genuinely critical doc finding able to rank
- [ ] → **#dcc-hmp6** — whether `_calibration` should measure the consolidated severity rather
      than max-over-agents. Promoted out of this nib: it rescores every tool and touches
      committed reports cited by three nibs, so it must not land as a side effect of the
      severity-contract prototype above

**Caveat on n.** Ours has 30 consolidated critical/high clusters across 9 subjects; the doc
bucket is 3 of them. The mechanism is traced and certain, but the *size* of the fix rests on a
small count — re-measure rather than trusting 0.85.

## 2. Cost / fan-out efficiency
$21.33/run vs **$7.61** (restated on the repaired data, #dcc-9kkz; the published $11.82 was a
blended column); 14.5 sub-agents vs 11.8, by role 9.4 reviewers + 5.1 validators vs 5 reviewers +
~7 auxiliary. Across all subjects ~77% of sub-agent findings
restate a sibling's. Cost scales with **diff** size, not repo size — see the scaling section below (the earlier
"scaled steeply with repo size" reading compared subject 1 to subject 6, which differ 10× in
diff *and* 3× in repo, and picked the wrong variable). superpowers stayed ~flat at $2.5.

### Where the output actually goes (corrected 2026-07-28)

The token figures this workstream originally quoted were wrong — sub-agent output was
under-counted ~10× by the aggregation bug in #dcc-m8ar (now fixed, all 90 runs backfilled).
Corrected, per run:

| tool | agents | orchestrator out | session out | orch share | out **per agent** | $/run |
|---|---|---|---|---|---|---|
| superpowers | 1.0 | 6,175 | 32,456 | 19% | 26,281 | 2.44 |
| pr-review-toolkit | 5.0 | 21,296 | 126,074 | 17% | 20,956 | 8.56 |
| anthropic | 11.8 | 24,191 | 137,369 | 18% | **9,609** | 7.61 |
| tag1 | 10.4 | 61,303 | 264,463 | 23% | 19,555 | 16.72 |
| **ours** | **14.5** | 84,533 | **367,084** | 23% | 19,486 | 21.33 |

**The orchestrator is 17–24% of output in every tool** — remarkably uniform, and not where the
money is. Session output predicts billed cost at **r = 0.967** (orchestrator output alone:
0.874), so session output is the right cost proxy.

**Ours emits ~2.7× anthropic's total output**, and on the corrected data the split is lopsided:
ours runs only **23% more agents** (14.5 vs 11.8) but each emits **2.0× more** (19.5k vs 9.6k).
By role, ours runs **9.4 reviewers + 5.1 validators** per run against anthropic's **5 reviewers +
~7 auxiliary** (Haiku triage and scorers). Anthropic's per-agent figure is the field's outlier *low* —
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

### Cost scales with diff size, not repo size

The two predictors are near-independent across the 9 graded subjects (r = +0.09), so they can be
compared directly:

| id | lang | diff LOC | repo files | ours $ | agents |
|---|---|---|---|---|---|
| 10 | rust | 33 | **220** | 17.35 | 10.5 |
| 4 | typescript | 37 | **74,229** | 19.21 | 12.0 |
| 7 | go | 53 | 1,234 | 15.82 | 11.5 |
| 1 | csharp | 72 | 5,133 | 14.70 | 15.5 |
| 2 | csharp | 169 | 17,128 | 11.25 | 10.0 |
| 5 | typescript | 276 | 14,505 | 24.02 | 16.5 |
| 3 | csharp | 424 | 57,593 | 27.97 | 14.5 |
| 6 | typescript | 701 | 15,674 | 29.50 | 21.0 |
| 9 | go | 1,560 | 26,968 | 32.10 | 19.0 |

- `r(cost, diff LOC)` = **+0.80** against `r(cost, repo files)` = **+0.31**
- `r(diff LOC, agent count)` = **+0.72** — the mechanism is roster size; gated dispatch responds
  to the changeset, which is the intended behaviour
- Subjects **4 and 10** are the clean contrast: near-identical diffs (37 vs 33 LOC) in repos
  differing **337×** (74,229 vs 220 files), costing $19.21 vs $17.35

**The other tools are the ones that scale with repo size** — superpowers +0.63, tag1 +0.64,
pr-review-toolkit +0.58, against ours' +0.31. This is a point in ours' favour, not against it.
The earlier "scaled steeply with repo size" reading compared subject 1 to subject 6, which differ
10x in diff and 3x in repo, and attributed the growth to the wrong variable — made easy by the
benchmark's size labels being *diff*-size labels.

Residual worth a look: subject 4 is the least diff-proportionate run (37 LOC, 12 agents, $19.21).
It is also the subject with the downstream-only regression (workstream 4), so reviewers may have
legitimately explored beyond the diff. One data point; do not build on it.


- [x] Identify which reviewer personas contribute zero unique clusters across the 9 subjects
      — done, and the framing turned out to be misleading: zero *unique* clusters means
      reliable corroborator, not dead weight. On participation no persona is dead weight;
      `go-reviewer` (50% signal) is the only weak one. See the table above.
- [ ] Test a reduced roster and **re-measure recall** — no clear drop candidate survived the
      corrected analysis; `go-reviewer` (50% signal) is the one to test first. Gate-side work
      is → **#dcc-1xtt**; this item is the measurement
- [ ] → **#dcc-1xtt** — loosen `security-reviewer`'s gate (best ratio in the roster, 5,416
      tok/substantive, yet dispatched in only 3 of 18 runs) and re-gate stack reviewers on
      idiom surface rather than file presence
- [ ] → **#dcc-c2uc** — the validation wave is 17.3% of sub-agent output, the single largest
      line item, and invisible to any finding-yield measure (it refutes, not finds)
- [x] Investigate why cost scales with *repo* size rather than *diff* size — **it does not.**
      For ours, r(cost, diff LOC) = **+0.80** against r(cost, repo files) = **+0.31**, and the
      two predictors are independent in this subject set (r = +0.09), so the comparison is
      clean. The mechanism is roster size: r(diff LOC, agent count) = +0.72 — gated dispatch
      responds to the changeset, which is the intended behaviour. Natural experiment: subjects
      4 and 10 have near-identical diffs (37 vs 33 LOC) in repos differing **337×** (74,229 vs
      220 files) and cost $19.21 vs $17.35 — an 11% spread. Notably the *other* tools do scale
      with repo size (superpowers +0.63, tag1 +0.64, pr-review-toolkit +0.58 against ours
      +0.31), so this is a point in ours favour, not against it. n=9 subjects.
- [ ] → **#dcc-gcob** — ours emits 19.5k output per agent against anthropic's 9.6k (2.0×); disjoint
      briefs are the proposed fix for the 77% restatement rate
- [ ] → **#dcc-lf4a** — shared-context-file pattern as the documented default (small prize;
      the orchestrator already does it on large diffs)
- [ ] → **#dcc-xewu** (deferred) — cheap pre-consolidation confidence filter, anthropic's
      Haiku-scorer shape. Blocked on workstream 3's product decision below
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

- [ ] Evaluate adding a history/blame retrieval step — **scope it to the changed files.**
      Unscoped retrieval would flip ours from diff-scaled to repo-scaled. anthropic runs the most
      history-based agents of any tool and still has the lowest repo sensitivity (partial
      r = 0.572 vs ours 0.403 — and note ours is now the LOWEST in the field, so this is a
      property to protect rather than one to acquire). Measured table and the rule: #dcc-gcob
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
against anthropic's 9.6k — a 2.0× gap. Anthropic's five agents have genuinely disjoint jobs (CLAUDE.md
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

- [x] Root cause identified for the calibration gap, with evidence from the graded data —
      `knowledge-reviewer` MUST → rule 1 Critical → rule 3 un-outvotable; non-behavioral
      categories ranked as behavioral. See workstream 1.
- [ ] At least one change prototyped and re-measured on a subset of benchmark subjects
      (re-run cells, re-grade blind, compare against the committed baseline)
- [ ] Written recommendation: what to change, expected effect on calibration / cost / recall,
      and what was deliberately not changed

# ⚠ Evidence validity — read first

**#dcc-9kkz: 11 of 18 anthropic cells did not run anthropic.** Seven executed `decaf-quality`
(ours) under anthropic's label; four are unattributed. Across the 9 valid cells anthropic
now averages **$7.61/run** across all 18 clean cells, not the published $11.82 — so **ours is ~2.8×
more expensive, not 1.8×**. Anthropic also sweeps recall (18/18) and posts 0.92 calibration and a
56% substantive share, all better than the blended figures.

- **Unaffected** — every ours-only finding here: the per-persona roster analysis, the severity
  calibration root cause, and the diff-vs-repo cost scaling.
- **Needs restatement after re-runs** — every ours-vs-anthropic *cost* comparison in this nib.
  Quality comparisons survive: bug-catch and calibration hold across clean, contaminated and
  unattributed cells alike (7/7, 7/7, 4/4; 0.89 / 0.89 / 0.83).

The direction of the error makes this programme **more** urgent, not less.

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
