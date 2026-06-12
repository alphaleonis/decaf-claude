---
name: code-review
description: Run parallel code review agents and consolidate findings into a unified report
argument-hint: "[low|mid|high|max][N] [--spec <path>] [PR#] [path] [instructions]"
---

# Code Review

This command orchestrates code review agents and consolidates their findings into a unified, deduplicated report.

## Argument Parsing

Parse `$ARGUMENTS` to determine:
1. **Mode**: `low`, `mid`, `high`, or `max`. The legacy keywords `quick` and `std` are accepted as aliases for `low` and `mid`. When no mode keyword is given, the mode is selected in Step 2a.5 — interactively when possible, otherwise defaulting to `mid`.
   - **Roster cap (optional)**: an integer suffixed directly to the mode keyword — `mid4`, `high6`, `max8` (alias forms `std4` etc.) — caps the **review-wave roster** at that many agents. It applies to `mid`, `high`, and `max`; on `low` it is ignored (the floor is already exactly two agents). The cap **counts the two floor agents** (so `mid4` = floor + the 2 best-fitting specialists) but **not** the Step 5.6 validators, and it does **not** change the mode's model tiering or validation policy. Applied in Step 2b.5.
2. **Spec**: `--spec <path | work-item-ID>` — a specification/plan document, or an ADO work item ID whose Description and Acceptance Criteria serve as the spec. When omitted, spec discovery (Step 1.5) may find one automatically.
3. **PR number**: A pull request number (e.g., `123`, `PR#123`, `#123`) — review that PR instead of local changes
4. **Scope**: Specific file/directory path, or all uncommitted changes (ignored when PR number is provided)
5. **Instructions**: Any additional review instructions

The mode ladder factors two independent dials — **roster size** (which agents run) and **model assignment** (which tier each agent runs on). Roster grows across the bottom half of the ladder; models upgrade across the top half. A trailing integer (`mid4`, `high6`) is a third, manual dial: it **caps roster size** directly — keeping the floor plus the best-fitting specialists up to that count — without touching model assignment or validation (see Step 2b.5):

| Mode | Roster | Models | Use Case |
|------|--------|--------|----------|
| `low` | quick + broad (2) | broad on the session model, quick mid-tier; validation skipped | Fast feedback from two generalists |
| `mid` (default) | floor + gate-matched specialists (typically 4-9) | judgment agents on the session model; volume agents + validators mid-tier | Cost-aware default — corroborated findings at the lowest specialist cost |
| `high` | floor + gate-matched specialists (same roster as `mid`) | session model end-to-end, except quick and consistency (mid-tier) | Strict quality — keeps the deep single-finder catches that ride the volume agents |
| `max` | All agents except hard-gate exclusions | all on the session model | Maximum coverage and fidelity |

## Execution Steps

### Step 1: Gather Context

Determine what code to review:

#### PR mode (when a PR number is provided)

Detect the hosting platform from context (git remotes, available MCP tools, or prior conversation):

- **Azure DevOps**: Use `mcp__azure-devops__repo_get_pull_request_by_id` to fetch the PR metadata (title, description, author, source branch, **target branch**), then retrieve the diff. List changed files and their diffs via the Azure DevOps MCP tools.
- **GitHub**: Use `gh pr view <number> --json title,body,author,baseRefName,headRefName` for metadata, then `gh pr diff <number>` for the diff.

**Skip checks — run on the PR metadata before gathering the full diff:**

1. **Closed/merged**: If the PR state is closed, merged, abandoned, or completed, stop immediately and tell the user: `PR #N is <state>; not reviewing.`
2. **Trivial/automated PR**: Launch a single lightweight subagent (model: haiku) with only the PR title, description, and changed-file list, asking: *"Is this an automated or trivial PR that does not warrant a code review? Consider: dependency lock-file or manifest-only bumps, automated release commits, chore version increments with no substantive code changes. When in doubt, answer no."* If it answers yes, stop and tell the user why — they can override by re-running with explicit instructions (any user-provided instructions in `$ARGUMENTS` count as an override; skip this check then).

**Target branch awareness**: The PR's target (base) branch determines the true scope of the review. A PR targeting a feature branch may contain only a few incremental changes, even if the source branch is far ahead of `main`/`develop`. Always identify the target branch and ensure the diff reflects only the changes between source and target — not the cumulative distance from the default branch.

Include the PR title, description, author, source branch, and **target branch** in the context passed to agents so they can evaluate intent and scope correctly.

**IMPORTANT**: Do NOT post comments, reviews, or status updates to the PR. The review output is a local file only. If the user explicitly asks to post comments to the PR, then and only then may you do so — under the posting rules in `@../../conventions/pr-etiquette.md` (agent-authored comments are signed).

**Prior feedback**: fetch the PR's review threads (ADO: `repo_list_pull_request_threads` + comments; GitHub: `gh api` review threads). Filter to human, non-system threads. If any exist, record `hasPriorFeedback = true` and keep the filtered threads — the `prior-feedback-reviewer` receives them in its prompt (it does not fetch them itself).

#### Local mode (default — no PR number)

- If a specific path is provided: Review that file or directory
- Otherwise: Get uncommitted changes via `git diff HEAD` and `git diff --cached`

For file/directory scope, use:
```bash
git diff HEAD -- <path>
```

If no uncommitted changes exist and no path specified, check the last commit:
```bash
git diff HEAD~1..HEAD
```

If that also yields nothing to review (or the diff is whitespace/generated-files only), stop and tell the user there is nothing to review — do not launch agents.

### Step 1.5: Spec Discovery

Determine whether a specification is available for compliance checking, and how trustworthy the association is. Check sources in priority order and **stop at the first hit**:

1. **Explicit `--spec`** — a path (read the document) or an ADO work item ID (fetch via the ADO MCP; the spec is the work item's `System.Description` plus `Microsoft.VSTS.Common.AcceptanceCriteria`, and for Bugs the repro steps). Source: `explicit`.
2. **PR-linked work items** (PR mode only) — fetch the work items linked to the PR (ADO: work item refs on the PR via the ADO MCP; GitHub: closing references like `Fixes #N` in the PR body). If exactly one linked User Story/Bug/Feature has a substantive Description or Acceptance Criteria, use it. Source: `linked`. If several are linked, use them all only when they are siblings of one parent (one feature's tasks); otherwise treat as ambiguous and skip.
3. **Session context** — when this conversation produced or worked from a spec (a PRD, plan document, or work item discussed while implementing the change), use that. Source: `inferred` — unless the user explicitly pointed at it earlier in the session, which makes it `explicit`.
4. **Repository documents** — extract 2-3 keywords from the branch name and recent commit subjects; glob plan/spec locations (`docs/plans/`, `docs/specs/`, `docs/prd/`, top-level `*.prd.md` or similar). Exactly one match → use it, source: `inferred`. Zero or multiple matches → no spec.

**Guardrails:**
- **A wrong spec is worse than no spec.** Never guess between candidates; ambiguity at any source means that source contributes nothing.
- **Confidence follows the source.** `explicit` and `linked` specs are reviewed at full strength. For `inferred` specs, the spec-compliance reviewer caps finding severity at **Medium** — a guessed spec must never flip the verdict to NEEDS_CHANGES.
- Record the outcome either way: spec source and identity go in the report header (`**Spec**: work item #95202 (linked)` / `none found`), so a silent miss is visible.

### Step 2: Select Agents (Conditional Dispatch)

Selection is **conditional dispatch**: the changeset determines the roster; the mode only sets how aggressively gates are applied. Every agent declares its own dispatch gate (a `Dispatch —` clause in its description, with the full rule in its `## Dispatch Gate` section).

#### Step 2a: Classify the changeset

From the diffstat plus a skim of the diff (do not deep-read files for triage), determine:

1. **Change types present**: executable code (and which languages), test code, prose/docs, config, generated files/lockfiles
2. **Executable lines changed** — exclude generated files and lockfiles from the count
3. **Character of the change**: mechanical (formatting, renames, typos) vs. substantive; security-adjacent surface touched; API/contract/boundary/concurrency surface touched; untrusted-input parsing/evaluation present; substantially AI-generated (stated by the user, PR authored by a bot/agent, or known from session context)

#### Step 2a.5: Select the mode (when none was given)

Skip this step entirely when the user gave an explicit mode (including via alias) — an explicit mode is never second-guessed.

First compute the **recommendation** from the Step 2a classification:

- **`high`** — the change parses or evaluates untrusted input, is substantially AI-generated, or touches a high-risk domain (auth, payments/financial, data mutations, external API integration) with ≥50 executable lines. These are the changesets where the deep single-finder catches justify the model premium.
- **`low`** — small (<50 executable lines), mechanical or low-risk, no specialist surface.
- **`mid`** — everything else.

Then:

- **Interactive invocation** (the user invoked this skill directly in a conversation): ask via `AskUserQuestion` — one question, the four modes as options, the recommended one first and marked `(Recommended)`, each option's description naming its roster size and model policy in one line. Use the answer.
- **Non-interactive invocation** (running inside another skill or subagent, or no user is available to answer): use `mid` without asking — the caller overrides by passing a mode explicitly. Record how the mode was chosen either way (`asked`, `explicit`, or `default (non-interactive)`) for the report's Agent Selection Rationale.

#### Step 2b: Evaluate dispatch gates per mode

| Mode | Rule |
|------|------|
| `low` | Floor only: `quick-reviewer` + `broad-reviewer` |
| `mid` (default) / `high` | Floor + every agent whose dispatch gate matches the changeset |
| `max` | Floor + all agents **except** those excluded by a hard negative gate |

Current roster gates (authoritative text lives in each agent's `## Dispatch Gate` section — keep this table in sync when adding agents):

| Agent | Gate |
|-------|------|
| `decaf-exp:quick-reviewer` | Always — review floor |
| `decaf-exp:broad-reviewer` | Always — review floor |
| `decaf-exp:knowledge-reviewer` | Any substantive change; skip only purely mechanical diffs |
| `decaf-exp:consistency-reviewer` | Any substantive change; skip purely mechanical diffs and changes with no sibling code to compare against |
| `decaf-exp:design-reviewer` | Public API/contract, data model, module boundary, or concurrency surface changes |
| `decaf-exp:security-reviewer` | Security-adjacent surface (auth, crypto, user input, network, file I/O, serialization, secrets/config, privileges) — judged from diff content; lean toward spawning when unsure |
| `decaf-exp:test-reviewer` | **Hard gate**: test files present in changeset |
| `decaf-exp:spec-compliance-reviewer` | **Hard gate**: a spec is available — provided via `--spec` or discovered in Step 1.5 |
| `decaf-exp:adversarial-reviewer` | ≥50 changed executable lines, OR high-risk domain (auth, payments, data mutations, external APIs) at any size |
| `decaf-exp:performance-reviewer` | DB/ORM queries, loops with I/O or allocation, async/concurrent code, data pipelines, or caching logic in the diff |
| `decaf-exp:data-migration-reviewer` | **Hard gate**: migration artifacts in the diff (EF `Migrations/*.cs`, ModelSnapshot, `.sql` DDL/backfill scripts) |
| `decaf-exp:dotnet-reviewer` | **Hard gate**: C# files in changeset |
| `decaf-exp:typescript-reviewer` | **Hard gate**: TypeScript/JavaScript files in changeset |
| `decaf-exp:cpp-reviewer` | **Hard gate**: C/C++ files in changeset |
| `decaf-exp:go-reviewer` | **Hard gate**: Go files in changeset |
| `decaf-exp:rust-reviewer` | **Hard gate**: Rust files in changeset |
| `decaf-exp:prior-feedback-reviewer` | **Hard gate**: reviewing a PR AND prior human review threads exist |

**Hard negative gates apply in ALL modes, including `max`.** An agent whose domain is absent from the changeset is never spawned — there is no point running the test-reviewer with no tests in the diff, or (once stack-specific agents exist) a C# persona on a Rust project. `max` opens the judgment gates, not the hard ones.

**User override:** explicit user instructions beat gates — "include security" spawns the security-reviewer regardless of triage; "skip knowledge" excludes it.

#### Step 2b.5: Apply the roster cap (only when a `mode<N>` cap was given)

Skip this step when no cap was parsed. In `low` mode a cap is always a no-op (the roster is already the two-agent floor) — note it if one was given and move on.

The cap bounds the **review-wave roster** — the agents launched in Step 3 — at `N`. Validators (Step 5.6) are not counted, and the mode's model tiering (Step 2d) and validation policy are unchanged: a `mid4` roster is a 4-agent roster reviewed and validated under `mid` rules. Resolve the cap against the roster Step 2b produced:

1. **The floor is never dropped.** `quick-reviewer` and `broad-reviewer` always run; they consume two of the `N` slots.
2. **Explicitly-requested agents are pinned.** Any agent the user named ("include security") is kept ahead of the ranking and consumes a slot. If the floor plus pins already exceed `N`, the pins win — record `roster cap N exceeded by explicitly-requested agents (kept K)` and dispatch those K; skip the ranking.
3. **`N` ≥ the matched roster size `M`** → the cap drops nothing; record `roster cap N ≥ matched roster M — no agents dropped` and proceed unchanged.
4. **`N` ≤ 2** → clamp to the floor only; record `roster cap N below floor size — clamped to the 2-agent floor`. (This is still a `mid`/`high`/`max` run — its tiering and validation wave follow the mode, unlike `low`.)
5. **Otherwise** → keep the floor (and any pins), fill the remaining `N − kept` slots with the highest-ranked gate-matched specialists, and **drop the rest** — recording each dropped agent under the roster-cap exclusion wording (Step 2c).

**Rank the gate-matched specialists by fit to *this* changeset (use the Step 2a classification); keep the top slots:**

1. **Categorical coverage the generalists cannot substitute — rank highest.** Dropping one leaves an entire dimension unreviewed, not merely thinner: the **stack reviewer** for the dominant changed language (`dotnet` / `typescript` / `cpp` / `go` / `rust`); `data-migration-reviewer` when migration artifacts are present; `prior-feedback-reviewer` when re-reviewing a PR with prior threads (addressing them is the point of the re-review); `spec-compliance-reviewer` for an `explicit` or `linked` spec.
2. **The changeset's primary risk dimension — rank next**, mapped from the Step 2a character: security-adjacent / untrusted-input → `security-reviewer` (then `adversarial-reviewer`); API / contract / boundary / concurrency → `design-reviewer`; test files dominate the diff → `test-reviewer`; DB / loops / async / caching → `performance-reviewer`. Order these by how central the dimension is to the diff — the dominant risk takes the first specialist slot.
3. **`knowledge-reviewer` and `consistency-reviewer` — rank last.** They are precision-safe and broaden coverage, but their lanes overlap `broad` the most, so they are the first specialists to shed when slots are scarce.

**Hard-gate agents are not exempt from the cap.** A tight enough cap can drop the stack reviewer on a C#-heavy diff or the test-reviewer on a test-bearing diff — a real coverage trade, not a gate decision. Rank such agents by rule 1/2 so they survive unless the cap is severe, and always name the trade in the announcement. If the cap forces dropping a hard-gate agent whose domain dominates the diff, surface it prominently — the user most likely wants a higher `N`.

#### Step 2c: Announce the review team

Before launching, state the team with a one-line justification per gated decision — both inclusions and exclusions:

```
Review team:
- quick-reviewer (always)
- broad-reviewer (always)
- knowledge-reviewer — new retry logic embeds behavioral decisions
- security-reviewer — diff adds an HTTP endpoint handling user input
- design-reviewer: skipped — changes confined to private method internals
- test-reviewer: skipped — no test files in changeset (hard gate)
```

**Exclusion reasons name the actual cause.** There are four distinct cases — do not conflate them:

| Case | Wording |
|------|---------|
| Judgment gate didn't match | `skipped — changes confined to private method internals` |
| Hard gate failed | `skipped — no test files in changeset (hard gate)` |
| `low` mode floor-only rule | `not evaluated — low mode runs the floor only` |
| Roster cap dropped it (Step 2b.5) | `dropped — roster cap (mid4): ranked below the 2 specialists kept` |

In `low` mode the specialists' gates are never evaluated; describing such an exclusion as a gate decision ("hard gate not applied") misstates why the agent is absent — its gate may well have matched. Likewise, an agent dropped by the roster cap had its gate **match** — it lost a slot to higher-ranked agents — so its exclusion wording must say "dropped — roster cap", never "skipped". When the cap drops a hard-gate agent whose domain is present (e.g. the stack reviewer on a C# diff), state that the coverage was traded for the cap.

This is the audit trail for the gating: when the roster turns out wrong, the stated reason shows which gate to fix. Include the same list in the report's Agent Selection Rationale section.

#### Step 2d: Model dispatch policy

Agents declare `model: inherit` and stay model-agnostic; the orchestrator decides models at dispatch time via the Task tool's `model` parameter. Two tiers, named by **role**, not model version (update the example model names here when the landscape changes; never hard-pin models in agent frontmatter):

- **Judgment agents** — `knowledge-reviewer`, `design-reviewer`, `security-reviewer`, `spec-compliance-reviewer`, `adversarial-reviewer` — carry the deep, cross-cutting reasoning.
- **Volume agents** — `quick-reviewer`, `broad-reviewer`, `consistency-reviewer`, `test-reviewer`, `performance-reviewer`, `data-migration-reviewer`, `prior-feedback-reviewer`, the stack reviewers (`dotnet`, `typescript`, `cpp`, `go`, `rust`), and the Step 5.6 `finding-validator`s — do pattern-matching, sibling comparison, idiom checks, and per-finding verification.

Apply the split by mode (mid-tier = the platform's mid-tier model, `sonnet`):

- **`low`:** `broad-reviewer` inherits the session model; `quick-reviewer` runs mid-tier. With a two-agent roster, broad is the only deep net — down-tiering it would leave `low` with no deep finder at all.
- **`mid` (cost-aware — the default):** judgment agents inherit the session model; volume agents and validators run mid-tier. The pattern-match and consistency findings the volume agents surface are well within the mid-tier's reach, while deep behavioral, design, and security findings stay on the top-tier judgment agents. The trade this mode accepts: a deep cross-file catch that only a volume agent (especially `broad`) would make may be lost to the down-tier.
- **`high` (strict quality):** every agent inherits the session model **except** `quick-reviewer` and `consistency-reviewer` (mid-tier — their lanes are cheap pattern matches and quotable facts). Validators inherit the session model. This keeps the deep single-finder catches that ride `broad` and `performance` on the top tier.
- **`max` (maximum fidelity):** no down-tiering — **every** agent inherits the session model, so a top-tier session reviews end-to-end on the top model.
- **Never tier *up*:** if the session model is already at or below the mid-tier (e.g., a `sonnet` or `haiku` session), down-tiered agents inherit the session model instead of being forced onto `sonnet`. Tiering only ever lowers cost, never raises it.
- **Fallback:** if the harness's Task tool exposes no `model` parameter, dispatch without overrides — a working review on the session model beats a broken dispatch.

Tiering is independent of any roster cap (Step 2b.5): the cap decides *which* agents run; tiering decides *which model* each runs on. A `mid4` roster still applies `mid` tiering to its four agents.

Note any tiering applied (which agents ran on which tier) in the team announcement and the report header.

### Step 3: Launch Review Agents in Parallel

Based on selection, launch agents using the **Task tool with parallel calls in a single message**.

**CRITICAL**: All agents for the selected mode MUST be launched in a single message with multiple Task tool calls. This ensures true parallel execution.

#### Agent Prompts

Each agent receives the same base context but with agent-specific focus:

**Base Context Template:**
```
Review the following code changes for issues. Focus on your area of expertise.
Follow your own output format instructions.

## Changes to Review
<paste git diff or file content here>

## Additional Instructions
<any user-provided instructions from $ARGUMENTS>
```

**Agent-Specific Focus:**
- `decaf-exp:quick-reviewer`: Fast generalist — bugs, logic errors, null safety, security patterns, code quality, convention violations
- `decaf-exp:broad-reviewer`: Comprehensive analysis — confidence scoring, knowledge preservation, production reliability, structural quality, architecture
- `decaf-exp:knowledge-reviewer`: Knowledge preservation (RULE 0), undocumented decisions, implicit assumptions, comprehension risks
- `decaf-exp:consistency-reviewer`: Sibling-consistency — unwritten-convention drift vs. sibling code (naming, canonical helpers, attribute symmetry, leftovers, comment-code mismatch, duplicated literals); every finding quotes its convention source
- `decaf-exp:design-reviewer`: System-level design — API contracts, data models, boundary violations, concurrency design, evolution readiness
- `decaf-exp:security-reviewer`: System-level security — threat modeling, missing controls (crypto, audit, config, dependencies, privileges)
- `decaf-exp:test-reviewer`: Test quality — anti-patterns, silent failures, false positives, flaky patterns (test files only)
- `decaf-exp:spec-compliance-reviewer`: Spec compliance — requirement gaps, deviations, partial implementations, scope creep (provide spec document in prompt)
- `decaf-exp:adversarial-reviewer`: Emergent failure scenarios — assumption violations, composition failures, cascade chains, abuse cases (states its depth tier)
- `decaf-exp:performance-reviewer`: Cost at scale — N+1 queries, hot-path work, memory growth, missing pagination, algorithmic complexity
- `decaf-exp:data-migration-reviewer`: Migration safety — schema drift, data loss, backfills, deploy-window breakage, locking, rollback
- `decaf-exp:dotnet-reviewer`: C#/.NET idiom misuse — async/await, disposal, EF change tracking, LINQ, nullability, threading
- `decaf-exp:typescript-reviewer`: TS/JS idiom misuse — floating promises, type escape hatches, coercion, runtime boundaries, event loop, mutation
- `decaf-exp:cpp-reviewer`: C/C++ idiom misuse — lifetimes, ownership, undefined behavior, exception safety, concurrency
- `decaf-exp:go-reviewer`: Go idiom misuse — goroutines, error discipline, typed nil, channels, context, defer, slice aliasing
- `decaf-exp:rust-reviewer`: Rust idiom misuse — panic paths, unsafe invariants, async hazards, lock discipline, error context
- `decaf-exp:prior-feedback-reviewer`: Diff vs. existing PR feedback — unaddressed requests, partial fixes, regressions of prior fixes (append the fetched threads to its prompt)

**For spec-compliance-reviewer**, append the spec content and its provenance to the prompt:
```
## Specification

**Source**: <explicit | linked | inferred> — <path, work item #N, or how it was discovered>

<contents of the spec document, or the work item's Description + Acceptance Criteria>
```

For `inferred` sources, the reviewer caps finding severity at Medium (its own rules cover this — but always pass the Source line so it can).

### Step 4: Collect Results

Wait for all agents to complete. Each agent returns findings in JSON format.

### Step 5: Consolidate Findings

Apply the consolidation rules:

@../../conventions/code-review-consolidation.md

1. **Normalize severities** across agents (MUST → Critical, SHOULD → High, etc.)
2. **Deduplicate** findings with same file + line (within 3 lines) + similar category
3. **Keep the highest severity** among duplicates, noting dissent — a specialist's Critical is never outvoted by lower ratings
4. **Promote confidence on agreement** (one anchor step when 2+ agents flagged the same finding; agreement between only quick+broad does not promote) — never average
5. **Merge descriptions** from multiple finders
6. **Apply the confidence gate**: suppress findings below anchor 75, except Critical findings at anchor 50; **and except the deterministic-claim safety net** — re-anchor quotable-fact findings (convention/consistency violations, doc-vs-code contradictions, dead contracts, identifier/comment mismatches, `!`/cast-laundered nulls) to 100 so they are kept, not suppressed. Record suppressed counts under Considered But Not Flagged
7. **Separate pre-existing findings** (all finders marked `pre_existing`) into the Pre-existing Issues section — informational, excluded from verdict and Summary counts
8. **Route minor findings** to the **Minor Findings** section: Consistency (quotable-fact Low/Medium, multi-finder allowed), Testing Gaps (single test-reviewer coverage gap), Residual Risks (single generalist structure/style). Reported and counted (Summary Minor row), not verdict-driving. A false-positive test (tautological / asserts a default / can't catch its named regression) is a defect — Medium+ stays primary, Low → Consistency

### Step 5.5: Review "Considered But Not Flagged" Items

**IMPORTANT**: Agents may inconsistently dismiss legitimate issues. For each agent's "Considered But Not Flagged" section:

1. **Collect all dismissed items** from all agents
2. **Cross-reference against flagged findings**: If Agent A dismissed something that Agent B flagged, include it as a finding
3. **Re-evaluate dismissed items**: For items no agent flagged, critically ask:
   - "Is the agent's reasoning for dismissal sound?"
   - "Does this match patterns that SHOULD be flagged (silent failures, knowledge loss, null safety)?"
   - "Would a user be confused or harmed by this issue?"
4. **Promote to findings** any dismissed items that:
   - Were dismissed with weak reasoning ("this is probably fine", "acceptable")
   - Match Critical/High severity criteria from any agent's guidelines
   - Involve knowledge preservation, silent failures, or null safety

This step compensates for LLM stochasticity where agents may "reason themselves out of" flagging legitimate issues.

### Step 5.6: Validation Wave

Independent re-verification of the primary findings that most need it — the counterweight to reviewers being instructed to err toward reporting. Spent selectively (see selection below): single-finder and contested findings get a validator; findings independent agreement already proved are waived. Runs **after** Step 5.5, so findings promoted from dismissed items are validated too.

**Skip this step** in `low` mode (speed is the point — record `Validation: skipped (low mode)` in the report header) and when zero primary findings survived.

1. **Select findings — validate where marginal value is highest, not blanket.** From the surviving primary findings, validate:
   - **every Critical** — high stakes; always worth an independent check, even when corroborated;
   - **every single-finder primary** — no corroboration yet; this is where the unique Highs live and where a lone reviewer is most likely wrong;
   - **any finding carrying dissenting severities** among its finders — the disagreement is the signal to resolve.

   **Waive** (corroboration is the verification) any non-Critical primary already found by **2+ independent finders including at least one specialist, all at anchor 100** — mark it `corroborated ×N — validation waived` in the report rather than spending a validator to re-confirm what independent agreement already established. Pre-existing and minor-bucket findings are never validated.
2. **Budget cap — 15 validators.** If more than 15 findings qualify, validate the highest-severity 15 (Critical first, then High, Medium, Low; ties broken by anchor descending), dropping only from the Medium/Low tail. **Never leave a Critical unvalidated** — if Criticals alone exceed 15, raise the cap to include all of them. Record the unvalidated and waived counts.
3. **Dispatch one `decaf-exp:finding-validator` per finding, in parallel** (single message, multiple Task calls). Each validator receives: the full finding (number, title, severity, anchor, file:line, category, issue, fix, finder agents, pre_existing), the diff hunk(s) for the cited file with surrounding context, and relevant PR metadata/instructions. Model follows Step 2d (validators are volume agents — mid-tier `sonnet` in `mid`, the session model in `high`/`max`).
4. **Process verdicts:**
   - `confirmed` — keep the finding; apply any corrections the validator supplied (line, file, pre_existing reattribution — a reattributed finding moves to Pre-existing Issues)
   - `refuted` — remove from findings; record under Considered But Not Flagged as `refuted by validator: <reason>`
   - `uncertain` — keep, but mark the finding `unvalidated` in the report
   - validator failed or timed out — keep the finding, mark it `validation failed (kept)`
5. **Record stats** for the report header: confirmed / refuted / uncertain counts, plus over-budget unvalidated count if any.

The wave only confirms, corrects, or removes — verdicts never raise severity or anchor, and validators never add new findings.

### Step 5.7: Compute Agent Summary Statistics

After consolidation and validation, compute per-agent statistics for the Agent Summary table (refuted findings excluded):

1. **Issues Found**: For each agent, count how many consolidated findings list that agent in the "Found by" field. A shared finding (found by multiple agents) counts toward each agent that found it.
2. **Unique Issues**: For each agent, count findings where that agent is the **only** finder — i.e., no other agent reported the same issue (after deduplication).
3. **Total**: Sum of all consolidated findings (each finding counted once regardless of how many agents found it).

### Step 6: Generate Report

Create a timestamped review file in `.code-reviews/` at the repo root. **Never overwrite existing reviews.**

```bash
# Ensure directory exists
mkdir -p .code-reviews

# Creates: .code-reviews/CODE_REVIEW_2025-01-24_14-30-45.md
FILENAME=".code-reviews/CODE_REVIEW_$(date '+%Y-%m-%d_%H-%M-%S').md"
```

**Generate diffstat** from `git diff --stat` output for the reviewed changes. Summarize as file count and total insertions/deletions for the `**Scope**` line in the report header.

**Number all findings** in the report for easy reference.

```markdown
# Code Review

**Mode**: <mode> (<explicit | asked | default (non-interactive)>)[ · roster cap N — M gate-matched agents dropped] | **Reviewers**: <agent list> | **Date**: <YYYY-MM-DD>
**Source**: <PR #N — title (platform) [source → target]> | <local changes> | <last commit>
**Scope**: N files changed, +X/-Y lines
**Spec**: <path or work item #N (explicit | linked | inferred)> | <none found>
**Validation**: <N confirmed, M refuted, K uncertain[, W waived (corroborated)][, J unvalidated (over budget)]> | <skipped (low mode)>

## Agent Selection Rationale

<The review-team list from Step 2c: each gated agent with its one-line inclusion
or exclusion reason. Note how the mode was chosen (explicit / asked with the
recommendation / default non-interactive) and any model tiering Step 2d applied
(which agents ran on which tier). If a roster cap (Step 2b.5) was in effect, state
the cap value, the specialists kept, and each gate-matched agent dropped to the
cap — including any hard-gate coverage traded away.>

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟠 High | X |
| 🟡 Medium | X |
| 🟢 Low | X |
| 🔵 Minor | X |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts the reported-but-non-blocking findings (Consistency / Testing Gaps / Residual Risks). Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES (if any Critical/High among primary findings) | ✅ APPROVED (otherwise)

---

## Findings

### #1 🔴 Critical: <issue title>

| | |
|---|---|
| **File** | `<path>:<line>` |
| **Category** | <category> |
| **Confidence** | <anchor: 100, 75, or 50 (Critical only)> |
| **Found by** | <agent1> (<severity1>), <agent2> (<severity2 or "not flagged">) |

**Issue:** <description>

**Fix:** <suggested fix>
```language
// code snippet if applicable
```

---

### #2 🟠 High: <issue title>
...

### #3 🟡 Medium: <issue title>
...

### #4 🟢 Low: <issue title>
...

---

## Pre-existing Issues

[Findings every finder marked pre-existing — issues in code this change did not
introduce. Informational only; excluded from the verdict and Summary counts.
Same per-finding format as Findings, numbered P1, P2, ... Omit this section
entirely if empty.]

### P1 🟠 High: <issue title>
...

---

## Minor Findings

[Verified, non-verdict-blocking one-liners — reported and counted (Summary
Minor row), never sent to the validation wave. Omit any sub-bucket that is
empty; omit the whole section only if all three are empty.]

### Consistency

[Quotable-fact findings: convention/sibling-consistency violations, doc-vs-code
contradictions, dead or self-contradicting contracts, identifier/comment
mismatches, and Low-severity false-positive tests. Multi-finder items allowed.]

- `path/to/file.cs:42` — <title> (knowledge-reviewer)

### Testing Gaps

[Single-finder Medium/Low *coverage* gaps where the test itself is not broken.]

- `path/to/file.cs:42` — <title> (test-reviewer)

### Residual Risks

[Single-finder Medium/Low structure/style observations with no nameable consequence.]

- `path/to/file.cs:42` — <title> (broad-reviewer)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| <agent1> | X | Y |
| <agent2> | X | Y |
| ... | ... | ... |
| **Total** | **X** | |

Notes:
- **Issues Found**: Total findings attributed to this agent (including shared findings)
- **Unique Issues**: Findings reported ONLY by this agent and no other

---

## Specialist Notes

<Include per-agent appendices that provide context beyond individual findings.
Only include sections that agents actually produced.>

### Requirement Coverage Matrix (spec-compliance-reviewer)
[If spec-compliance-reviewer was used, include its coverage matrix here]

### Threat Model Notes (security-reviewer)
[If security-reviewer was used, include its threat model notes here]

### Considered But Not Flagged (all agents)
[Consolidated list of items agents examined but did not flag, with reasoning.
Group by agent for clarity. Include findings suppressed by the confidence
gate, with their anchor (e.g., "2 findings suppressed at anchor 50").]
```

### Severity Icons (ALWAYS include in finding headers)

- 🔴 Critical - Must fix before merge
- 🟠 High - Should fix before merge
- 🟡 Medium - Consider fixing
- 🟢 Low - Minor improvement

**Always use literal Unicode emoji characters (🔴🟠🟡🟢), never `:shortcode:` syntax like `:yellow_circle:`.**

### Finding Numbering

- Number findings sequentially: #1, #2, #3, etc.
- Order by severity first (Critical → High → Medium → Low), then by file path
- Include the number in the heading: `### #1 🔴 Critical: Issue title`

### Verdict Logic

- **NEEDS_CHANGES**: Any Critical or High severity findings among **primary** findings
- **APPROVED**: Only Medium/Low primary findings, only Minor findings, or no findings
- Pre-existing issues and Minor findings (Consistency / Testing Gaps / Residual Risks) never change the verdict

### Output Notification

After creating the review file, inform the user:
```
✅ Review complete: .code-reviews/CODE_REVIEW_2025-01-24_14-30-45.md
```

### Step 7: Review History (Recurring Findings)

After writing the report, scan `.code-reviews/CODE_REVIEW_*.md` for previous reviews. If previous reviews exist, check if any findings in the current review match findings from previous reviews (same file path + same category). If recurring findings are found, append a section to the report:

```markdown
## Recurring Findings

| File | Category | Occurrences | First Seen |
|------|----------|-------------|------------|
| `path/to/file.cs` | null-safety | 3 | 2025-12-01 |
```

Keep this lightweight — match on file path + category only. Skip this step if no previous reviews exist.

## Example Usage

```
/decaf-exp:code-review                              # mode chosen interactively (default mid), uncommitted changes
/decaf-exp:code-review low                          # Low mode (2 agents) - fast feedback
/decaf-exp:code-review mid                          # Mid mode - gated roster, cost-aware tiering
/decaf-exp:code-review mid4                         # Mid mode, roster capped at 4 (floor + 2 best-fit specialists)
/decaf-exp:code-review high                         # High mode - gated roster, session model end-to-end
/decaf-exp:code-review high6 src/                   # High mode on a directory, roster capped at 6
/decaf-exp:code-review max                          # Max mode - all applicable agents, session model
/decaf-exp:code-review --spec docs/design.md        # spec compliance check, mode chosen interactively
/decaf-exp:code-review high --spec docs/design.md   # High mode with spec compliance
/decaf-exp:code-review mid src/Tools/MyTool.cs      # Mid mode, specific file
/decaf-exp:code-review max src/                     # Max mode, directory
/decaf-exp:code-review mid focus on null safety     # Mid mode with custom instructions
/decaf-exp:code-review 42                           # review PR #42, mode chosen interactively
/decaf-exp:code-review max #42                      # Max mode, review PR #42
/decaf-exp:code-review low PR#123                   # Low mode, review PR #123
```
