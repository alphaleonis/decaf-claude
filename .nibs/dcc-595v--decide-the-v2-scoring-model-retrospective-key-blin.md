---
# dcc-595v
version: 1
title: Decide what the benchmark measures, and on what kind of code
status: todo
type: research
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T18:43:15Z
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

**Feasibility risk to test, not assume:** application and UI repos may not satisfy the Step 0 screen
(fix body names a mechanism). Infra projects have revert discipline, regression issues and re-land
PRs — which is plausibly *why* every survivor is infra. If application subjects cannot meet the
screen, that is evidence the escaped-defect instrument is the binding constraint rather than the
corpus, and pushes toward pooled adjudication. Cheap to test: screen a handful of candidate
application/SPA repos before committing to either answer.

## Also settle (from the audit)

- **Key completeness replaces the ">=2 entries" rule.** The test is whether a key is complete *for its
  diff*, not how many entries it holds. Subject 7 is a 78-line single-file PR whose entire content is
  the defect — one entry is complete; a second would have to be invented.
- **One-entry subjects come out of per-subject precision ranking**, not out of the corpus: a single
  true positive cannot separate signal from noise. Recall pools across subjects fine.

## Acceptance

- [ ] Instrument decided: which of anchor / pooled adjudication / null arm are in, and which one ranks
- [ ] Corpus axis decided, with the language grid explicitly kept or dropped
- [ ] Feasibility spot-check done on application/SPA candidates against the Step 0 screen
- [ ] Verdict vocabulary and severity treatment specified
- [ ] Judge-contamination position stated explicitly
- [ ] Written into METHODOLOGY-v2.md, replacing the key-only framing
- [ ] [[dcc-9ncz]] and [[dcc-ixyy]] re-scoped to match, or closed if the decision obsoletes them
