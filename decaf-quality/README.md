# decaf-quality

Code quality for Claude Code: analyze and improve **existing** code without changing its behavior. Three capabilities — **multi-agent code review**, **coverage-gap analysis**, and **refactoring** — each pairing an *analysis* skill with a `resolve-*` skill that walks the results and acts on them. Standalone: declares no dependencies on other plugins.

The code-review engine runs parallel specialized reviewer agents over a diff (local changes, a path, or an ADO/GitHub PR) and consolidates their findings into a single deduplicated report with severity, confidence, and verdict.

## Skills

### Code review
| Skill | Purpose |
|-------|---------|
| `code-review` | Orchestrate review agents (`low` / `mid` / `high` / `max` modes, plus an optional `modeN` roster cap), consolidate findings, write a timestamped report to `.code-reviews/` |
| `resolve-code-review` | Walk through the findings one at a time and decide a resolution for each — fix (optionally TDD), skip, dismiss, or defer to a work item. `auto` mode resolves autonomously after one upfront confirmation. |
| `auto-code-review` | The full loop: review → triage → fix (via subagent) → re-review, iterating until the code stabilizes or the iteration cap is hit |
| `resolve-pr-feedback` | Walk through unresolved PR review threads (ADO or GitHub) and resolve each — fix, reply, decline with evidence, or escalate. Replies are drafted, batch-approved, signed, and posted with matching thread-status changes. |

```
/decaf-quality:code-review                 # mode chosen interactively (default mid), uncommitted changes
/decaf-quality:code-review low             # 2 generalists, fast feedback
/decaf-quality:code-review mid             # gated roster, cost-aware model tiering
/decaf-quality:code-review high            # gated roster, session model end-to-end
/decaf-quality:code-review max             # all applicable agents, session model
/decaf-quality:code-review mid4            # mid mode, roster capped at 4 (floor + 2 best-fit specialists)
/decaf-quality:code-review 42              # review PR #42
/decaf-quality:code-review --spec docs/design.md

/decaf-quality:resolve-code-review         # walk through the latest review's findings
/decaf-quality:resolve-code-review auto high   # autonomously resolve Critical+High

/decaf-quality:auto-code-review            # review-fix-recheck loop until stable
/decaf-quality:auto-code-review max --max-iterations 5

/decaf-quality:resolve-pr-feedback         # current branch's PR, interactive
/decaf-quality:resolve-pr-feedback auto 42 # resolve all feedback on PR 42, drafts approved before posting
```

### Coverage
| Skill | Purpose |
|-------|---------|
| `coverage-review` | Run the project's coverage tools, assess which gaps actually matter, and suggest targeted tests; report to `.code-reviews/`. Reads a `## Coverage` config from the project CLAUDE.md. |
| `resolve-coverage-review` | Walk the gaps one group at a time and write tests — write / skip / dismiss / defer. `auto` mode writes tests autonomously. |

```
/decaf-quality:coverage-review             # diff mode, changed files
/decaf-quality:coverage-review full        # whole project, baseline assessment
/decaf-quality:resolve-coverage-review     # walk the gaps, write tests
/decaf-quality:resolve-coverage-review auto high   # autonomously cover Critical+High gaps
```

### Refactoring
| Skill | Purpose |
|-------|---------|
| `refactor` | Analyze code structure for improvement opportunities and produce a prioritized plan (impact×effort ★ ratings) in `.refactoring-plans/`. Behavior-preserving — no defects, just better structure. |
| `resolve-refactor` | Walk the opportunities one unit at a time and apply them — apply / apply (incremental) / skip / dismiss / defer. `auto` mode applies autonomously. |

```
/decaf-quality:refactor                    # deep mode, changed files
/decaf-quality:refactor full               # whole project (sampled)
/decaf-quality:resolve-refactor            # walk opportunities, apply one at a time
/decaf-quality:resolve-refactor auto       # apply autonomously
```

## Reviewer agents (code-review roster)

| Agent | Focus |
|-------|-------|
| `quick-reviewer` | Fast generalist — line-level bugs, security patterns, quality, conventions |
| `broad-reviewer` | Wide generalist — knowledge, reliability, conformance, structure, architecture |
| `knowledge-reviewer` | Knowledge preservation — undocumented decisions, comprehension risks |
| `consistency-reviewer` | Sibling-consistency — unwritten-convention drift vs. sibling code: naming, canonical helpers, attribute symmetry, leftovers, comment-code mismatch; every finding quotes its convention source |
| `design-reviewer` | System-level design — API contracts, boundaries, concurrency, evolution |
| `security-reviewer` | Architectural security — threat modeling, missing controls |
| `test-reviewer` | Test quality — silent failures, false positives, flaky patterns (test files only) |
| `spec-compliance-reviewer` | Implementation vs. specification — gaps, deviations, scope creep (`--spec`, or a discovered spec) |
| `adversarial-reviewer` | Emergent failure scenarios — assumption violations, composition failures, cascades, abuse cases |
| `performance-reviewer` | Cost at scale — N+1 queries, hot paths, memory growth, pagination, algorithmic complexity |
| `data-migration-reviewer` | EF Core/SQL migration safety — drift, data loss, backfills, deploy window, locking, rollback |
| `dotnet-reviewer` | C#/.NET idiom misuse — async/await, disposal, EF tracking, LINQ, nullability, threading |
| `typescript-reviewer` | TS/JS idiom misuse — floating promises, type escapes, coercion, runtime boundaries, event loop |
| `cpp-reviewer` | C/C++ idiom misuse — lifetimes, ownership, undefined behavior, exception safety, concurrency |
| `go-reviewer` | Go idiom misuse — goroutines, errors, typed nil, channels, context, defer |
| `rust-reviewer` | Rust idiom misuse — panic paths, unsafe invariants, async hazards, lock discipline |
| `prior-feedback-reviewer` | The diff vs. existing PR threads — unaddressed requests, partial fixes, regressions of prior fixes (PR reviews with prior feedback only) |
| `finding-validator` | Adversarial re-verification of one consolidated finding (validation wave; not part of the review roster) |
| `pr-thread-resolver` | Resolves one PR review thread — verify, fix or decline, draft the reply (resolve-pr-feedback only; never posts) |

The stack reviewers and `data-migration-reviewer`/`spec-compliance-reviewer`/`test-reviewer` carry **hard dispatch gates** — they are never spawned, in any mode, when their domain is absent from the changeset.

## Analysis agents (standalone)

Invoked directly by the coverage / refactor skills — **not** code-review orchestrator personas, so they are deliberately absent from the Domain Ownership Matrix and the dispatch roster.

| Agent | Focus | Used by |
|-------|-------|---------|
| `coverage-reviewer` | Which uncovered paths actually matter + targeted test suggestions (severity × confidence, like the reviewers) | `coverage-review` |
| `structural-analyst` | Per-file structural improvement opportunities — naming, composition, complexity, domain modeling, error handling | `refactor` |
| `coherence-analyst` | Cross-file patterns — duplication, validation scattering, interface drift, module boundaries, zombie code | `refactor` |

Shared conventions (severity taxonomy, consolidation rules, security categories, temporal/intent-marker rules, coverage config, refactoring value matrix) live in `conventions/`. To add a reviewer persona, follow [`conventions/persona-authoring.md`](./conventions/persona-authoring.md) — it defines the required agent anatomy, the domain ownership matrix, and the integration checklist.

## How the three capabilities score

- **Code review** and **coverage** share one model: severity (impact, Critical/High/Medium/Low) × five discrete confidence anchors (0/25/50/75/100), with a gate that suppresses sub-75 findings (Critical@50 survives). Code review adds multi-agent consolidation and a validation wave; coverage is single-agent (no consolidation/validation).
- **Refactoring** is different by design — opportunities are scored by **impact × effort star ratings** (★★★/★★) and consolidated via the value matrix in `conventions/refactoring.md`. Refactorings are improvements, not defects, so they carry no severity.

## Code-review engine — design decisions

1. **Keep-highest severity.** When agents disagree on a duplicate finding's severity, the highest always wins, with dissent recorded — a specialist's Critical is never buried under generalists rating the same issue out of their domain.
2. **Agreement promotion.** Agreement between independent reviewers is evidence: it promotes confidence one anchor step (50→75, 75→100). Confidence is never averaged. Agreement between only the two generalists (`quick`+`broad`) does not promote — their scopes deliberately overlap, so it isn't independent corroboration.
3. **Discrete confidence anchors.** Agents rate confidence as one of five behavioral anchors (0/25/50/75/100) with operational definitions. Severity (impact) and confidence (certainty) are orthogonal — a verified-but-minor fact is anchor 100 Low, never anchor 50 (50 means *uncertain*, not *small*). Consolidation suppresses findings below anchor 75, except Critical findings at anchor 50 (critical-but-uncertain must not be silently dropped) and a **deterministic-claim safety net** that re-anchors quotable facts (convention/consistency violations, doc-vs-code contradictions, dead contracts, `!`-laundered nulls) to 100 and routes them to Minor Findings rather than dropping them. Domain bias is tuned per persona by miss-cost: security and data-migration lenient, performance and rust strict; opinion-grade findings cap at anchor 50 everywhere.
4. **Pre-existing separation.** Findings on code the change didn't introduce are marked `pre_existing` by agents and routed to an informational report section — they never affect the verdict or summary counts. The review judges the change, not the codebase.
5. **Minor findings (reported, non-blocking).** Verified Low/Medium findings that don't block the verdict route to a compact **Minor Findings** section — Consistency (quotable-fact nits: convention / doc-vs-code / dead-contract / identifier mismatches, multi-finder allowed), Testing Gaps (single-finder coverage gaps), Residual Risks (single-finder structure/style). They are counted and reported, not buried in an excluded appendix. Defects with a concrete consequence are never demoted, and a false-positive test (tautological, asserts a framework default, can't catch its named regression) is a defect — not a coverage gap.
6. **Skip checks.** Closed/merged PRs are not reviewed; a cheap haiku-subagent judgment skips trivial automated PRs (dependency bumps, release commits); an empty local diff exits early instead of launching agents.
7. **Conditional dispatch on a two-dial mode ladder.** Each agent declares its own dispatch gate (`## Dispatch Gate` section + a `Dispatch —` clause in its description); the changeset determines the roster, the mode sets gate aggressiveness and the model tier (decision 12). The ladder factors roster size and model assignment as independent dials: `low` = floor only, `mid` (default) and `high` = gated roster (differing only in models), `max` = all judgment gates open. When no mode is given, the skill recommends one from the changeset triage (untrusted-input parsing, AI-generated code, or high-risk domain → `high`; small mechanical diff → `low`; otherwise `mid`) and asks interactively — falling back to `mid` without asking when no user is available. `quick`/`std` are accepted as aliases for `low`/`mid`. Hard negative gates (test-reviewer without test files, spec reviewer without a spec, domain-absent stack reviewers) apply in **all** modes, including `max`. The team is announced with per-agent justifications before launch.
8. **Validation wave.** After consolidation (and skipped in `low` mode), surviving primary findings get an independent `finding-validator` subagent prompted to *refute* them — spent where marginal value is highest: every Critical, every single-finder primary, and any finding with dissenting severities. A non-Critical primary already corroborated by 2+ independent finders (≥1 specialist) at anchor 100 is **waived** — independent agreement is itself the verification. Budget-capped at 15. Refuted findings are removed (recorded with the refutation reason); uncertain ones stay but are marked unvalidated. Division of labor: reviewers do plausibility filtering, the wave does proof — paid once, and not re-paid for what agreement already proved.
9. **Spec discovery.** The spec-compliance reviewer runs whenever a spec is available from any source: explicit `--spec` (path or ADO work item ID), a PR-linked work item (Description + Acceptance Criteria), session context, or an unambiguous repo plan document. Provenance is graded — `explicit`/`linked` specs review at full strength; `inferred` specs cap finding severity at Medium so a guessed spec can never block a merge. Ambiguity at any source means no spec: a wrong spec is worse than no spec.
10. **Verify-first fixing.** In `resolve-code-review` and `auto-code-review`, a finding is a claim, not an order: every fix action starts by re-verifying the finding against the current code. Refuted findings are resolved `not-addressing` with evidence; valid findings whose suggested fix would cause harm are `declined` citing the harm; wrong fixes for real issues become `fixed (differently)`. Unverified Criticals (anchor 50) are never auto-fixed — they defer to a human.
11. **Posting etiquette.** Nothing visible to other people on a PR is posted without either an explicit user request (`code-review`) or a batched draft approval (`resolve-pr-feedback`; `--auto-post` opts out). Every agent-authored reply is signed so recipients know they're reading agent output; declines always carry their reasoning; thread-status changes go through the same approval as reply text. The rules live in [`conventions/pr-etiquette.md`](./conventions/pr-etiquette.md).
12. **Dynamic model policy (per-mode tiering).** All agents are `model: inherit`; the orchestrator picks models at dispatch time (Task tool `model` parameter). The volume agents (generalists, consistency, test, performance, data-migration, prior-feedback, stack reviewers, validators) are the down-tier candidates; the judgment agents (knowledge, design, security, spec-compliance, adversarial) always inherit the session model. Per mode: `low` keeps broad on the session model (with two agents, broad is the only deep net) and down-tiers quick; `mid` runs all volume agents and validators on the mid-tier — the cost-aware default, accepting that a deep single-finder volume-agent catch may be lost; `high` down-tiers only quick and consistency (cheap pattern matches and quotable facts) so the deep catches riding broad/performance stay top-tier, validators included; `max` runs everyone on the session model. Tiering never raises cost (a session already at/below mid-tier inherits throughout). The policy names tiers, not model versions, and lives in one place — the skill's Step 2d.

## Output

- **Code review** and **coverage** → `.code-reviews/CODE_REVIEW_<timestamp>.md` / `COVERAGE_REVIEW_<timestamp>.md` in the reviewed repo.
- **Refactoring** → `.refactoring-plans/REFACTOR_PLAN_<timestamp>.md`.

Nothing is posted to a PR unless explicitly requested. Recurring code-review findings across past reviews are tracked by file + category.
