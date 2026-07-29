---
# dcc-05uw
version: 1
title: Pluggable code-review backend with per-project defaults (cost-tiered review)
status: todo
type: feature
priority: normal
estimate: l
created_at: 2026-07-28T18:48:19Z
updated_at: 2026-07-29T11:03:32Z
order: zzy
---

# Idea

Make the code-review *backend* pluggable, with **persisted per-project defaults** and
**per-invocation override**, so a project (or a single PR) can choose how much review it pays for.

Today every decaf skill that reviews code calls `decaf-quality:code-review` (ours). The benchmark
(#dcc-z1xw) shows that is often the wrong economic choice: `ours` is the most expensive backend in
the field, and for many jobs a cheaper one loses little.

# Evidence from the benchmark (9 subjects / 90 blind-graded runs)

| backend | $/run | escaped bug caught | useful findings/run | trivia share | calibration |
|---|---|---|---|---|---|
| superpowers | **$2.48** | 14/18 | 5.0 | **21%** | 0.63 |
| anthropic-code-review | $7.61 ‡ | **18/18** | 6.3 | 25% | **0.92** ‡ |
| pr-review-toolkit | $8.56 | 12/18 | 11.7 | 42% | 0.51 |
| tag1-comprehensive-review | $16.72 | 15/18 | 11.2 | 37% | 0.61 |
| ours | $21.33 | 16/18 | 10.5 | 31% | 0.62 |

`superpowers` costs **8.6× less than ours** and still caught the escaped bug in 14 of 18 runs,
with the cleanest output in the study (lowest trivia share, lowest false-positive rate, fewest
findings to read). On 6 of 9 subjects it reached the same bug as a 15-agent run using one agent.

That is the core of the case: **for a large fraction of PRs, deep analysis is not required**, and
the current architecture gives no way to say so.

# Motivating use cases

1. **Cheaper repeat reviews in a loop.** `auto-dev` / `auto-tdd` / `auto-code-review` re-review
   after fixes. Using `ours` for every pass is the expensive path — using `superpowers` (or
   `anthropic`) for the second/third pass should save most of the cost at little recall loss.
2. **Per-project economics.** A low-stakes project sets a cheap default once; a high-stakes one
   defaults to the deep roster. No per-invocation ceremony either way.
3. **Per-PR escalation/de-escalation.** A trivial config change does not warrant a $21 review; a
   migration touching auth does. Overridable at the call site.
4. **Best-tool-for-the-axis.** The benchmark suggests `anthropic` is the best "short trustworthy
   list" and `ours` the best "exhaustive coverage" — a project could legitimately prefer either.

# Open questions to investigate

- **Adapter contract.** What is the minimum interface a review backend must satisfy so the
  `resolve-*` skills can consume its output uniformly? Ours emits a structured report under
  `.decaf/`; the others emit prose. Does the adapter normalize, or do downstream skills degrade
  gracefully?
- **Config location & precedence.** `.decaf/config.*` in-project? Project `.claude/settings.json`?
  Precedence chain: invocation arg → project config → user default → built-in default.
- **Granularity.** One default per project, or per-skill (e.g. `auto-dev.review=superpowers`,
  `code-review=ours`)? Per-loop-iteration (first pass deep, later passes cheap)?
- **Which skills are pluggable.** `code-review`, `auto-code-review`, `auto-dev`, `auto-tdd`,
  `batch-dev`, `auto-deliver` all trigger review. Do they all share one setting?
- **Availability & fallback.** Backends are separate plugins/commands that may not be installed.
  How is a missing backend detected, and what is the fallback — error, or degrade to built-in?
- **Escalation policy.** Should a cheap backend finding something critical auto-escalate to a
  deep pass? Attractive, but adds a second invocation's cost and complexity.
- **Do the findings compose?** If pass 1 is `ours` and pass 2 is `superpowers`, can pass 2 see
  what pass 1 already raised, so it re-checks rather than re-derives?

# Sketch (to be validated, not a decision)

```
# .decaf/config.toml   (per project, committed)
[review]
default = "ours"              # backend for a full review
loop    = "superpowers"       # backend for re-review passes inside auto-* loops

# override at the call site
/decaf-quality:code-review --backend anthropic
/decaf-build:auto-dev --review-backend superpowers
```

# Acceptance

- [ ] Decision recorded on the adapter contract (normalize vs. degrade) with rationale
- [ ] Config location, precedence chain, and granularity chosen and documented
- [ ] Prototype: at least two backends selectable for `code-review`, with a per-project default
      that a per-invocation flag overrides
- [ ] `auto-dev` (or `auto-code-review`) able to use a different backend for its re-review pass
- [ ] Measured: cost delta and any recall delta of a cheap-loop configuration vs all-ours,
      ideally reusing benchmark subjects so the comparison is grounded

# Notes

- Benchmark evidence: `competition/benchmark/analysis/synthesis-report.html`, data in
  `synthesis-data.json`. Related: #dcc-z1xw (the benchmark), #dcc-e0wj (improving ours itself —
  complementary, not a substitute; this nib is about *choosing* a backend, that one about
  making the deep backend better).
- Three benchmark subjects are still unrun, so the per-backend numbers above may shift slightly.

# Evidence update (2026-07-28) — read before refining

Findings from reading the competitors' actual source and decomposing the benchmark
transcripts. Several correct premises stated above; the scope decision is still open.

**The field narrows to three.** tag1 and pr-review-toolkit are out — they lose on nearly
every axis except cost. Remaining: `ours`, `anthropic`, `superpowers`. That also means this
does not need a general plugin contract; three hard-coded adapters will do.

**The two gaps are complementary, and each maps cleanly.** Neither external backend supplies
both axes `auto-code-review`'s triage table needs (severity × anchor × validated-flag):

| | severity | confidence | verdict | fix text | scope accepted |
|---|---|---|---|---|---|
| ours | 4 tiers + Minor | anchor 100/75/50 | APPROVED / NEEDS_CHANGES | yes | local, GitHub PR, ADO PR |
| superpowers | Critical / Important / Minor, each defined | **none** | "Ready to merge? Yes/No/With fixes" | yes, required | local git range |
| anthropic | **none** — flat numbered list | 0–100 rubric, filtered | implicit | **no** — one-line desc + permalink | GitHub PR only |

- **superpowers → confidence.** One uncorroborated reviewer with no verification step *is*
  anchor 75 by ours' own definition. Severity maps directly (Critical→Critical,
  Important→High, Minor→the Minor bucket). Caveat: its severity calibration measured 0.63,
  barely above ours' 0.62 — the labels transfer, but deserve no more trust than ours.
- **anthropic → severity.** Its confidence rubric uses discrete anchors 0/25/50/75/100 and
  step 6 discards everything under 80 — so on that ladder **only findings scored exactly 100
  are ever emitted**: "definitely a real issue, that will happen frequently in practice."
  Mapping all of them to `(High, anchor 100)` restates the rubric rather than guessing it;
  measured calibration 0.88 corroborates. What is genuinely lost is remediation text.

**Anthropic is three different products; only one is dispatchable.** `/review` is a harness
builtin (GitHub PR). `claude ultrareview` / `/code-review ultra` is a cloud-hosted multi-agent
review (`launchRemoteReview`, cost-gated, user-triggered — not invocable by a skill). The
**plugin** `code-review@claude-plugins-official` is what the benchmark measured, and its
`allowed-tools` is entirely `gh pr *` / `gh issue *` — **PR-only, GitHub-only**. So:

- local / uncommitted (every auto-* loop, bare `/code-review`): **ours or superpowers only**
- GitHub PR: all three · Azure DevOps PR: ours only

[Unverified] Whether a local, in-session, non-cloud `/code-review` also exists was not
settled — `/review`'s help text and the `ReportFindings` tool hint at one, but no
registration was located. Even if it exists, a harness builtin is likely not Skill-tool
dispatchable, which is the bar for a decaf backend.

**Motivating use case 1 collides with an existing decision.** `auto-code-review:75` already
refuses `low` for re-review passes: *"`mid` runs the validation wave, and an autonomous fixer
must not consume unvalidated findings."* superpowers is strictly less validated than `low`.
The loop also already down-tiers (`mid3`–`mid6`, Step 5.4) — what is actually missing is the
ability to **persist** that choice per project.

**The cost premise needs restating.** Ours' expense is not depth or Opus reviewers — it is
consolidation *reasoning*, 60% (small subject) to 77% (large) of orchestrator output, growing
with roster size. See #dcc-e0wj workstream 2. Swapping in superpowers buys cheapness by not
doing the consolidation at all: a different product, not a cheaper one. Anthropic reaches
better calibration for half the cost using **5 Sonnet agents and Haiku scorers — no Opus
sub-agents at all** — by filtering cheaply *before* the orchestrator reasons.

**Config location is settled by precedent.** `coverage-review` already reads its config from a
`## Coverage` section in the project's CLAUDE.md (`conventions/coverage-config.md`). `.decaf/`
is documented as generated-artifact scratch (`conventions/artifacts.md`), so committed config
does not belong there. A `## Code Review` section is the house pattern.

**The adapter contract has an in-repo template.** `conventions/work-items.md` solves exactly
this shape already — named ops, per-backend mapping tables, detection order, and the governing
rule *"the contract is designed to the weakest backend."*

**Availability detection is solved.** `claude plugin list` returns plugin names plus
enabled/disabled status.

**Acceptance criterion 5 belongs to #dcc-e0wj.** Its workstream 2 owns re-measuring a reduced
roster, and now explicitly owns measuring ours at `low`/`mid3` — never measured, since the
study ran `ours` at `mid` only. That measurement gates how much of the cost case here survives.

## Open decisions (unresolved — for the refine interview)

- Scope: persisted config + 3-way switch · config only (tiers) · switch only
- Whether anthropic is in scope now, given PR-only reach and no remediation text
- Whether superpowers may drive the autonomous fix loop, or human-facing review only
