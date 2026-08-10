---
# dcc-595v
version: 1
title: Decide what the benchmark measures, and on what kind of code
status: completed
type: research
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T19:20:58Z
parent: dcc-ho2w
order: "9"
---

Two questions that cannot be settled separately: **what instrument ranks the tools**, and **what code
it runs on**. Answer both before building or sourcing anything — [[dcc-9ncz]], [[dcc-ixyy]] and
[[dcc-y2e6]] all spend real money executing whatever this decides.

## The arithmetic that forces the question

The ground-truth audit ([[dcc-5xad]]) left 7 subjects carrying **12 scoreable key entries total**
(2,1,1,2,2,1,3). Only subjects 2 and 12 are vintage-safe, and they carry **4 entries between them**.

Five tools x 2 repeats against 12 binary items cannot separate a 50%-recall tool from a 70%-recall
one. That is structural, not imprecision. Completing [[dcc-9ncz]] does not improve it — those 12
entries *are* the finished corpus. [[dcc-ixyy]] would reach n≈22 at full section-4 cost per subject.

Review threads do not rescue density either: 15 threads across five survivors, **12 of them on
subject 12 alone**, with subjects 7 and 10 at zero.

## Question 1 — the instrument

The escaped-defect key measures the rarest thing in the dataset (a defect that survived expert human
review) at the highest cost per observation. It is the only instrument that detects a blind spot
*all* tools share — that is real and worth keeping — but it cannot rank.

Options to decide between, not necessarily exclusive:

- **Escaped-defect key as anchor.** Keep the 7 subjects for shared-blind-spot detection. Stop asking
  it to rank.
- **Pooled adjudication.** Run every tool on one diff, pool and dedupe findings, blind-judge each as
  real / not-real. Yields precision and recall against the union of what tools collectively found.
  Needs **no answer key and no revert**, so it works on any PR — including your own history. v1
  subject 9 produced ~800 findings collapsing to ~98 clusters: roughly 100 gradeable claims from one
  subject versus 2 from its key. Blind spot: cannot see what every tool missed — which is exactly
  what the anchor covers.
- **Null arm.** A clean, well-reviewed, never-reverted PR where approximately every finding is a
  false positive. No key at all. Directly measures the noise that decides day-to-day usability.

Carried over from the original framing of this nib, still to settle:

- Is the key the METRIC or one INPUT to a judged metric? (Recommendation: the latter.)
- Which v1 verdict vocabulary survives, and what replaces `TP-human`?
- Severity weighting — v1's precision was severity-unweighted, so four minor findings outscored one
  revert-forcing defect.
- Does the judge see the key? (v1: yes, blind to tool identity. Keep.)
- **Judge contamination**: the grading model's cutoff is later than most subjects' merge dates, so it
  may know the defect independently. Blind grading hides the TOOL, not the answer. Mitigate or
  disclose — state which.

## Question 2 — what code, and how it is stratified

The surviving corpus is ORM library, web framework, time-series DB, orchestrator x2, CLI tool,
compiler. **Zero application code, zero UI, zero changes crossing a client/server contract.** The only
two application-shaped subjects were vscode x2 and the audit rejected both.

That is an external-validity problem: the day-to-day target is Svelte + ASP.NET Core + EF Core +
GraphQL, and only subject 2 resembles it — as framework internals, not application code.

- **Language is probably the wrong axis.** Defect classes that reviews catch are largely
  language-agnostic. Language *is* a tool-internal variable, because decaf hard-gates
  `dotnet-reviewer` / `typescript-reviewer` / `go-reviewer` / `rust-reviewer` / `cpp-reviewer` on file
  type — but that is a property of the tool config, not of review difficulty, and Rust/C++ cells
  measure capability that will never be used.
- **At 12 entries a 4x3 grid is decorative** — about one entry per cell. Stratification cannot be
  supported at this scale, so choose the axis for **relevance, not balance**.
- Proposed axis: **application/UI · full-stack contract-crossing · backend service · library
  internals**, with size kept as a secondary axis since it genuinely drives cost and roster
  selection, and two or three current survivors retained as the infra anchor.
- Contract-crossing changes are the highest-value review target and the corpus has none: the defect
  lives in the *mismatch* between two files in two languages.

**Operator position (2026-08-10), treat as decided:** language is NOT a stratification axis. Rust and
occasionally C/C++ are in the real workload, but the per-language specialists are expected to
contribute about equally within their language, so language washes out relative to application type.
Two consequences:

- The specialist-parity expectation is untested. If it is worth testing, do it as a narrow head-to-head
  on matched defects — not by stratifying the whole corpus, which is an indirect and expensive way to
  answer it.
- Contract-crossing subjects absorb the part of the language question that matters: a SPA + backend
  change spawns `typescript-reviewer` AND `dotnet-reviewer` together, exercising the multi-specialist
  dispatch path that no single-language subject reaches. A finding there has to span two specialists
  territory to be found at all.

Rust stays represented anyway — subjects 10 and 12 both survived the audit — without reserving a cell
for it.

**Feasibility: TESTED 2026-08-10, hypothesis was WRONG.** Full result:
`v2/analysis/STEP0-FEASIBILITY.md`. 273 merged revert PRs across 9 application and 3 infra repos,
hand-classified against Step 0. Application repos pass at ~4.5%, infra at ~9% — a screening cost
difference, not a barrier, and application repos merge far more PRs so absolute availability is
comparable.

Domain was the wrong predictor: `mattermost` and `PostHog` match or beat kubernetes and prometheus;
the near-zero repos (`outline`, `twentyhq`) are younger, not more application-shaped. The original
reasoning confused project *maturity* with project *domain*.

Consequences:

- The corpus axis is genuinely open — nothing forces a retreat to infra-only subjects, and
  [[dcc-ixyy]] can target application/UI/contract-crossing subjects against the existing screen.
- Six concrete candidates already identified, four of them vintage-safe — including mattermost#30337,
  an APIs-return-nil contract-crossing defect, the exact shape the corpus lacks. Vintage safety is
  *easier* in application repos because they are more active.
- What application repos lack is the k8s/rust habit of a formal **re-land PR** — the source that
  saved subject 8. Expect that candidate class to be rarer.
- **This does not settle the instrument.** The n=12 density problem was never a feasibility argument;
  it is arithmetic that applies identically to application subjects. Better subjects raise relevance,
  not ranking power. Pooled adjudication still stands or falls on its own merits.

## Also settle (from the audit)

- **Key completeness replaces the ">=2 entries" rule.** The test is whether a key is complete *for its
  diff*, not how many entries it holds. Subject 7 is a 78-line single-file PR whose entire content is
  the defect — one entry is complete; a second would have to be invented.
- **One-entry subjects come out of per-subject precision ranking**, not out of the corpus: a single
  true positive cannot separate signal from noise. Recall pools across subjects fine.

## Acceptance
## Acceptance

- [x] Instrument decided — pooled adjudication ranks; retrospective key demoted to a blind-spot
      anchor; null arm added for an absolute noise floor. Written into METHODOLOGY-v2 section 3.
- [x] Corpus axis decided — size (S/M/L) x application type; language explicitly dropped as an axis.
      Own PRs rejected: review quality there is not trusted and the codebases are legacy, so subjects
      come from reputable, review-disciplined repos merged post-cutoff.
- [x] Feasibility spot-check done on application/SPA candidates against the Step 0 screen — `v2/analysis/STEP0-FEASIBILITY.md`; viable at ~4.5% vs infra ~9%
- [x] Verdict vocabulary and severity treatment specified — keep `valid-other` / `nitpick` /
      `false-positive`, drop the key-presupposing `TP-*`, add severity weighting. Detail in [[dcc-y2e6]].
- [x] Judge-contamination position stated explicitly — mitigated, not merely disclosed: code citation
      required per verdict, adversarial re-judging, hand spot-check of the `valid-other`/`nitpick`
      boundary, plus human review threads as a non-scoring calibration check on the judge.
- [x] Written into METHODOLOGY-v2.md, replacing the key-only framing
- [x] [[dcc-9ncz]] and [[dcc-ixyy]] re-scoped to match — ixyy rebuilt around the size x type grid,
      9ncz demoted to anchor-only at normal priority, [[dcc-mjj5]] filed for the null arm, [[dcc-y2e6]]
      reduced to removing the key dependency from the existing pipeline

## Summary

**Completed 2026-08-10** — **Pooled adjudication is the ranking instrument.** The retrospective key becomes an anchor for one
question only — is there a defect class every tool misses — and a null arm supplies an absolute noise
floor. Written into METHODOLOGY-v2 section 3.

The decisive evidence was density plus the verdict distribution. One v1 subject produced 800 findings
collapsing to 98 clusters, graded 1 `TP-primary`, 2 `TP-human`, 31 `valid-other`, 58 `nitpick`, 6
`false-positive`. Key-based scoring consumes 3 of those 98. And only 6 were *wrong* while 58 were
*trivial*: review tools fail by immateriality, not error, which is precisely what a key cannot see.

Pooled adjudication also dissolves three of the four v1 failures — no key means no ground truth to be
wrong, no revert requirement means subjects can postdate the training cutoff, and no fixing PR means
little cross-reference leak. Section 4 drops from 8 steps to 4 for pooled subjects. And v1's pipeline
already IS pooled adjudication minus the key, so [[dcc-y2e6]] shrinks to removing that dependency.

Corpus: size (S/M/L, kept for cost and wall-clock effects and because decaf derives roster size from
executable lines) x application type (application/UI, contract-crossing, backend service, library
internals). Language dropped as an axis. Own PRs rejected — review quality not trusted, codebases
legacy — so subjects come from reputable review-disciplined repos merged post-cutoff. That choice
pays a bonus: human review threads become a non-scoring validity check on the judge.

The grid is affordable only because of this decision: 12 cells was decorative at 1-3 key entries per
subject and is well powered at ~50-100 clusters.

Weaknesses accepted and mitigated rather than assumed away — the judge becomes ground truth and shares
a model family with the tools (code citations, adversarial re-judging, hand spot-checks of the
valid-other/nitpick boundary); volume is rewarded (precision primary, findings-per-cell always
reported); "real" is not binary (severity weighting required).
