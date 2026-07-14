# decaf's Claude Plugins

A personal marketplace of [Claude Code](https://code.claude.com) plugins, organized around what each one *does*: **build** (create new behavior), **quality** (improve existing code), **plan** (decide what/how), plus **memory** and **protection**.

Originally forked from [everything-claude-code](https://github.com/affaan-m/everything-claude-code) — you probably want that one rather than this, which is tailored to my own workflow.

| Plugin | Does | Depends on |
|--------|------|------------|
| [`decaf-quality`](#decaf-quality) | improve existing code (behavior-preserving) | — |
| [`decaf-build`](#decaf-build) | create new behavior | quality, plan (auto-installed) |
| [`decaf-plan`](#decaf-plan) | decide what/how (plans, RFCs, decisions) | — |
| [`decaf-memory`](#decaf-memory) | store/recall knowledge | [erinra](https://github.com/alphaleonis/erinra) MCP server |
| [`decaf-protection`](#decaf-protection) | block secret-leaking commands | — |

## Installation

```bash
/plugin marketplace add alphaleonis/decaf-claude
/plugin install decaf-quality@decaf
/plugin install decaf-build@decaf
/plugin install decaf-plan@decaf
/plugin install decaf-memory@decaf       # needs the erinra MCP server (see decaf-memory)
/plugin install decaf-protection@decaf
```

`decaf-build` declares dependencies on `decaf-quality` and `decaf-plan`, so installing it pulls both in automatically. Restart Claude Code after installing.

## Skills

Skills are invoked as `/<plugin>:<skill>`. Click any skill for details and usage.

**decaf-quality** — improve existing code
- [`code-review`](#code-review) — parallel multi-agent review of a diff/PR → consolidated findings
- [`auto-code-review`](#auto-code-review) — review → fix → re-review loop until the code stabilizes
- [`resolve-code-review`](#resolve-code-review) — walk findings one at a time: fix / skip / dismiss / defer
- [`resolve-pr-feedback`](#resolve-pr-feedback) — resolve unresolved PR threads (ADO/GitHub)
- [`coverage-review`](#coverage-review) — run coverage, assess which gaps matter, suggest tests
- [`resolve-coverage-review`](#resolve-coverage-review) — walk coverage gaps and write tests
- [`refactor`](#refactor) — analyze structure → prioritized, behavior-preserving plan
- [`resolve-refactor`](#resolve-refactor) — walk the refactoring plan and apply opportunities
- [`coherence-audit`](#coherence-audit) — find + fix drift between docs/specs/comments/config and code
- [`diagnose`](#diagnose) — root-cause investigation via competing hypotheses (diagnoses, never fixes)

**decaf-build** — create new behavior
- [`tdd`](#tdd) — red → green → refactor, one vertical slice at a time
- [`auto-tdd`](#auto-tdd) — a TDD session followed by an automated review gate
- [`auto-dev`](#auto-dev) — non-test-first implementation followed by an automated review gate
- [`batch-dev`](#batch-dev) — orchestrate multiple work items in one run, best mechanism per cluster
- [`auto-deliver`](#auto-deliver) — drive a whole plan to completion, unattended

**decaf-plan** — decide what/how
- [`research`](#research) — investigate an unfamiliar problem/tech from several angles
- [`draft-spec`](#draft-spec) — interview + read code → a spec (PRD)
- [`grill-me`](#grill-me) — decision-by-decision interview to stress-test a plan/design
- [`draft-plan`](#draft-plan) — turn a spec into a phased, vertical-slice plan + work items
- [`breakdown-phase`](#breakdown-phase) — break one phase into buildable features with done-checklists
- [`close-out`](#close-out) — reconcile built vs. planned, close the item, file follow-ups
- [`explore-designs`](#explore-designs) — "design it twice": generate and compare radical alternatives
- [`architecture-review`](#architecture-review) — find structural/testability improvements → RFCs
- [`resolve-architecture-review`](#resolve-architecture-review) — walk those proposals → RFCs
- [`challenge-decision`](#challenge-decision) — argue against a decision → STAND/REVISE/ESCALATE verdict
- [`capture`](#capture) — jot a follow-up as a work-item draft without breaking flow
- [`refine`](#refine) — take an under-specified work item to actionable → `todo` + acceptance criteria

**decaf-memory** — remember
- [`remember`](#remember) — store a memory in erinra
- [`recall`](#recall) — search memories (hybrid semantic search)
- [`init-memory`](#init-memory) — manually load erinra session context (hook fallback)
- [`memory-dashboard`](#memory-dashboard) — open the erinra dashboard in the browser

**decaf-protection** — safety hooks only (no skills); see [decaf-protection](#decaf-protection).

---

# Skill reference

## decaf-quality

Analyze and improve existing code without changing its behavior. The three core capabilities each follow an **analyze → resolve** pattern (and code review adds an **automate** option on top); reports land under `.decaf/` and nothing is posted to a PR unless you ask.

### code-review
Runs parallel specialized reviewer agents over a diff — uncommitted changes, a path, or an ADO/GitHub PR — and consolidates them into one deduplicated report with severity, confidence, and a verdict, written under `.decaf/code-reviews/`. This step only *reports*: hand the findings to [`resolve-code-review`](#resolve-code-review) to work through them one at a time, or skip straight to [`auto-code-review`](#auto-code-review) to run the whole review → fix → re-review loop hands-off.
```
/decaf-quality:code-review                 # uncommitted changes; mode chosen interactively
/decaf-quality:code-review high            # deeper roster, session-model end-to-end
/decaf-quality:code-review 42              # review PR #42
/decaf-quality:code-review --spec docs/design.md
```
Modes `low | mid | high | max` trade roster size and model tier; append a number (`mid4`) to cap the roster.

### auto-code-review
The hands-off loop: it runs [`code-review`](#code-review), triages, fixes via subagent, and re-reviews, iterating until the code stabilizes or the iteration cap is hit. Use it when you want issues *fixed*, not just reported; for manual control over each fix, run `code-review` then [`resolve-code-review`](#resolve-code-review) instead.
```
/decaf-quality:auto-code-review
/decaf-quality:auto-code-review max --max-iterations 5
```

### resolve-code-review
Walk the latest [`code-review`](#code-review) report's findings one at a time, deciding a resolution for each — fix (optionally TDD), skip, dismiss, or defer to a work item. Each fix re-verifies the finding first. `auto` resolves autonomously after one upfront confirmation — at which point you're effectively doing what [`auto-code-review`](#auto-code-review) does in one shot.
```
/decaf-quality:resolve-code-review
/decaf-quality:resolve-code-review auto high     # autonomously resolve Critical+High
```

### resolve-pr-feedback
Walk unresolved PR review threads (Azure DevOps or GitHub) and resolve each — fix, reply, decline with evidence, or escalate. Replies are drafted, batch-approved, signed, and posted with matching thread-status changes. (To *generate* a fresh review of a PR rather than resolve existing threads, use [`code-review`](#code-review) on the PR number.)
```
/decaf-quality:resolve-pr-feedback               # current branch's PR, interactive
/decaf-quality:resolve-pr-feedback auto 42       # PR 42, drafts approved before posting
```

### coverage-review
Run the project's coverage tools, assess which uncovered paths actually matter, and suggest targeted tests; report goes to `.decaf/code-reviews/`. Reads a `## Coverage` config from the project's CLAUDE.md. Act on the gaps with [`resolve-coverage-review`](#resolve-coverage-review).
```
/decaf-quality:coverage-review                   # diff mode, changed files
/decaf-quality:coverage-review full              # whole-project baseline
```

### resolve-coverage-review
Walk the gaps found by [`coverage-review`](#coverage-review) one group at a time and write tests — write / skip / dismiss / defer. `auto` writes tests autonomously.
```
/decaf-quality:resolve-coverage-review
/decaf-quality:resolve-coverage-review auto high
```

### refactor
Analyze code structure for improvement opportunities and produce a prioritized plan (impact × effort ★ ratings) under `.decaf/refactoring-plans/`. Behavior-preserving — better structure, no behavior change. Apply the plan with [`resolve-refactor`](#resolve-refactor).
```
/decaf-quality:refactor                          # deep mode, changed files
/decaf-quality:refactor full                     # whole project (sampled)
```

### resolve-refactor
Walk the plan produced by [`refactor`](#refactor) one opportunity at a time and apply them — apply / apply incrementally / skip / dismiss / defer. `auto` applies autonomously.
```
/decaf-quality:resolve-refactor
/decaf-quality:resolve-refactor auto
```

### coherence-audit
Audit a codebase for places where documentation, specs, comments, config, names, or versions disagree with the actual code, then resolve each (update docs / flag code / accept). Unlike the review/refactor pairs, this one *finds and fixes in a single skill*. Good after big changes or before a release.
```
/decaf-quality:coherence-audit
/decaf-quality:coherence-audit src/auth          # scope to a path
```

### diagnose
Root-cause investigation: gate the problem to one testable statement, generate competing hypotheses, gather evidence to distinguish them, and report the cause. It **diagnoses only** — once you know the cause, fix it directly or hand it to a [`decaf-build`](#decaf-build) skill. For a delegated, self-contained deep dive instead, dispatch the `debugger` agent.
```
/decaf-quality:diagnose "sessions expire immediately on mobile"
```

## decaf-build

Create new behavior. The automated loops call [`decaf-quality`](#decaf-quality) for their review gate; the orchestrators ([`batch-dev`](#batch-dev), [`auto-deliver`](#auto-deliver)) drive the single-item skills and the [`decaf-plan`](#decaf-plan) skills at scale.

### tdd
Test-driven development — red → green → refactor, one vertical slice (tracer bullet) at a time. Ships supporting guides for deep modules, interface design, mocking, and the final refactor pass. This is the interactive core; [`auto-tdd`](#auto-tdd) wraps it with an automated review gate, and [`batch-dev`](#batch-dev) / [`auto-deliver`](#auto-deliver) run it at scale.
```
/decaf-build:tdd
```

### auto-tdd
Runs a TDD session (plan → red-green-refactor, via subagent) then an automated [`auto-code-review`](#auto-code-review) gate. Use for test-first feature work with a quality bar. For work that isn't naturally test-driven, use [`auto-dev`](#auto-dev); it handles one item, so for several at once reach for [`batch-dev`](#batch-dev).
```
/decaf-build:auto-tdd "add rate limiting to the upload API"
/decaf-build:auto-tdd "<feature>" --review high --max-iterations 3
```

### auto-dev
Direct (non-test-first) implementation then an automated [`auto-code-review`](#auto-code-review) gate — for UI, config, scaffolding, infrastructure. Like [`auto-tdd`](#auto-tdd) but without the test-first loop; for many items at once, use [`batch-dev`](#batch-dev).
```
/decaf-build:auto-dev "wire up the settings page layout"
/decaf-build:auto-dev "<feature>" --spec docs/feature.md
```

### batch-dev
Orchestrate **multiple** work items (nibs) in one run: understand them collectively, cluster them, pick the best mechanism per cluster (single series / parallel fan-out / scripted workflow / agent team), and dispatch behind one approval gate. It runs `auto-dev` / `auto-tdd`-style execution per nib; the autonomous driver that calls batch-dev for you, phase by phase, is [`auto-deliver`](#auto-deliver).
```
/decaf-build:batch-dev --ready                   # all ready nibs
/decaf-build:batch-dev abc1 def2 --review high   # specific nibs
```

### auto-deliver
The autonomous whole-plan loop: `SELECT → BREAKDOWN → EXECUTE → VERIFY → RECONCILE → LEARN → REPLAN → MERGE`, one phase at a time, **without stopping at phase boundaries**. It composes [`breakdown-phase`](#breakdown-phase) → [`batch-dev`](#batch-dev) → [`close-out`](#close-out) (all `--unattended`) over the tracker-adapter contract and stops only at plan completion. Resumable run state lives in `.decaf/auto-deliver/`. Point it at a plan produced by [`draft-plan`](#draft-plan).
```
/decaf-build:auto-deliver <plan-id>
/decaf-build:auto-deliver <plan-id> --base-branch integration --review max
```

## decaf-plan

Decide what and how to build; output is plans, RFCs, and decisions — not code. The skills chain into a pipeline: [`research`](#research) → [`draft-spec`](#draft-spec) → [`draft-plan`](#draft-plan) → [`breakdown-phase`](#breakdown-phase) → *(build)* → [`close-out`](#close-out).

### research
Dig into an unfamiliar problem or technology from several angles and write up what you find — when the domain or trade-offs aren't clear yet. Feeds into [`draft-spec`](#draft-spec).
```
/decaf-plan:research "options for replacing our REST API with GraphQL"
```

### draft-spec
Interview the user and explore the code to write a spec (PRD): *what* to build and *why*, including top-level acceptance criteria. Pulls in [`grill-me`](#grill-me) to pressure-test the decisions; next, turn the spec into a plan with [`draft-plan`](#draft-plan).
```
/decaf-plan:draft-spec
```

### grill-me
A relentless, decision-by-decision interview that stress-tests a plan or design until it holds up — walking each branch of the decision tree and resolving dependencies between choices. Used by [`draft-spec`](#draft-spec), or standalone whenever you want to pressure-test thinking.
```
/decaf-plan:grill-me
```

### draft-plan
Turn a spec from [`draft-spec`](#draft-spec) into an ordered, **phased** build plan of vertical slices (tracer bullets) and create the work-item nibs for it, each with a `## Acceptance` section. Then detail each phase with [`breakdown-phase`](#breakdown-phase) — or hand the whole plan to [`auto-deliver`](#auto-deliver).
```
/decaf-plan:draft-plan
```

### breakdown-phase
Break one phase of a plan into concrete, independently buildable features, each with a done-checklist — run just before starting a phase, against the code earlier phases produced. Build the resulting features (e.g. via [`batch-dev`](#batch-dev)), then close the phase with [`close-out`](#close-out).
```
/decaf-plan:breakdown-phase 2
/decaf-plan:breakdown-phase <phase-id> --unattended
```

### close-out
Reconcile what was built against what was planned, record decisions and deviations, close the item (a single phase **or** a whole plan), and file follow-ups for deferred work. The follow-ups it files are what [`auto-deliver`](#auto-deliver)'s replan step picks up.
```
/decaf-plan:close-out 3
/decaf-plan:close-out <plan-id> --unattended
```

### explore-designs
"Design it twice": generate several radically different designs for a decision — from a single method up to a whole architecture — compare them, and write up the one you choose. Sibling decision tools: [`challenge-decision`](#challenge-decision) (stress-test one stated choice) and [`architecture-review`](#architecture-review) (find improvements in existing structure).
```
/decaf-plan:explore-designs
```

### architecture-review
Explore existing code for structural/testability improvements (deepen shallow modules, untangle coupling) and write up recommendations as **RFCs** — not code changes. Walk its proposals one at a time with [`resolve-architecture-review`](#resolve-architecture-review).
```
/decaf-plan:architecture-review
```

### resolve-architecture-review
Walk the candidates from [`architecture-review`](#architecture-review) one at a time, designing the interface and writing an RFC for each.
```
/decaf-plan:resolve-architecture-review
```

### challenge-decision
Stress-test a decision you're about to make by arguing *against* it — decompose it into claims/assumptions/constraints, verify each, steel-man the strongest case for the opposite, and return a `STAND` / `REVISE` / `ESCALATE` verdict. For architectural choices, tech selection, and trade-offs. Related: [`grill-me`](#grill-me) (interview-style pressure-testing) and [`explore-designs`](#explore-designs) (generate alternatives rather than judge one).
```
/decaf-plan:challenge-decision "use Redis for session storage instead of PostgreSQL"
```

### capture
Jot a follow-up idea or task as a work-item draft without interrupting your current work — it picks a sensible parent from context. Works with any tracker in [`work-items.md`](conventions/work-items.md) (nibs, GitHub, Azure DevOps, Markdown).

Captured items are created as **drafts**, because you gave a one-line note and the skill inferred the rest. Drafts are deliberately excluded from ready work, so [`batch-dev --ready`](#batch-dev) and [`auto-deliver`](#auto-deliver) will *not* build them — run [`refine`](#refine) when you've confirmed what one should actually do. (You can still hand a draft to `batch-dev` by naming its id explicitly.)
```
/decaf-plan:capture "add retry to the upload path"
/decaf-plan:capture parent:abc1 "tighten the auth error messages"
```

### refine
Take one under-specified work item and make it actionable: read the code, resolve the open questions in a short interview, add `## Acceptance`, and promote it `draft` → `todo`. This is the exit for [`capture`](#capture)'s drafts, but works on any open item too vague to start on.

It reads *first* and interviews from a **proposal** — "`RetryPolicy` is used in five sibling paths, three attempts, exponential; same here?" — rather than from a blank page, so a simple task costs you one question instead of twenty. If the item turns out to be too large it hands off to [`draft-spec`](#draft-spec); if it turns out to hide a real design fork, to [`grill-me`](#grill-me); if the code says it's already done, it proposes scrapping it.

Acceptance criteria come out honestly tagged: `[run]` where a command can check it, `[manual]` (with a stated reason) where only a human can. An item that ends up mostly `[manual]` is still *finished* — it just can't be **verified** autonomously, and refine tells you so rather than quietly handing a loop something it can't check.
```
/decaf-plan:refine dcc-pak3
/decaf-plan:refine            # picks up the item in conversation context
```
Related: [`breakdown-phase`](#breakdown-phase) decomposes a decision you already made; refine establishes whether there is a decision at all.

## decaf-memory

Store and recall knowledge across sessions via the [erinra](https://github.com/alphaleonis/erinra) MCP server (hybrid semantic search). Set it up once:
```bash
claude mcp add erinra -- erinra serve -s user
```
A `SessionStart` hook then loads the memory protocol automatically each session.

### remember
Store a memory in erinra for future reference (returns similar existing memories so you can dedup). Find them again with [`recall`](#recall).
```
/decaf-memory:remember "we use pnpm, not npm, in this monorepo"
```

### recall
Search stored memories via hybrid (vector + keyword) search — the counterpart to [`remember`](#remember).
```
/decaf-memory:recall "database migration conventions"
```

### init-memory
Manually load the erinra session context — a fallback for when the automatic `SessionStart` hook didn't fire.
```
/decaf-memory:init-memory
```

### memory-dashboard
Open the erinra memory dashboard in the browser.
```
/decaf-memory:memory-dashboard
```

## decaf-protection

Safety hooks only — no skills or agents. A `PreToolUse` hook, **`block-op-secrets`**, blocks 1Password CLI invocations (`op read`, `op item get`, `op inject`, `op run`, …) that could emit secret values into the session transcript. Allowlist: `op --version`, `op --help`, `op whoami`. It exits with code 2, so the block holds even under `--dangerously-skip-permissions`. To prime a 1Password approval, run `op` yourself via the `!` prefix so nothing lands in the transcript.

---

# Development

## Agents

Agents are referenced via the Task tool as `<plugin>:<agent>`; most are dispatched by skills, but all can be invoked directly. See each plugin's README for full agent docs.

- **decaf-quality** — the `code-review` roster (`broad-reviewer`, `quick-reviewer`, `adversarial-reviewer`, `consistency-reviewer`, `knowledge-reviewer`, `design-reviewer`, `security-reviewer`, `performance-reviewer`, `spec-compliance-reviewer`, `prior-feedback-reviewer`, `test-reviewer`, `data-migration-reviewer`), language stack reviewers (`cpp-`, `dotnet-`, `go-`, `rust-`, `typescript-reviewer`), and specialists (`finding-validator`, `pr-thread-resolver`, `coverage-reviewer`, `structural-analyst`, `coherence-analyst`, `debugger`).
- **decaf-build** — `technical-writer` (LLM-optimized docs).
- **decaf-plan** — `architect` (feature-architecture blueprints).

## Conventions

Shared reference files live at repo-root `conventions/` and are pulled into skills/agents via `@file` references:

| Convention | Used by |
|------------|---------|
| `work-items.md` | decaf-plan skills + auto-deliver (tracker-adapter contract) |
| `acceptance-criteria.md` | the `## Acceptance` format (draft-spec/draft-plan/breakdown-phase; auto-deliver) |
| `code-review-consolidation.md`, `severity.md`, `intent-markers.md`, `structural.md`, `temporal.md`, `security.md`, `code-quality/`, `coverage-config.md`, `refactoring.md`, `pr-etiquette.md`, `persona-authoring.md` | decaf-quality review/refactor skills + agents |
| `documentation.md` | technical-writer; documentation guidance |

Generated **artifacts** (review reports, refactor plans, loop state, etc.) are written under a single per-project root, **`.decaf/`** — see [`conventions/artifacts.md`](conventions/artifacts.md).

### Sharing conventions across plugins (symlinks)

**Installed plugins can only read files inside their own directory** — on install, Claude Code copies just the plugin's own subtree into the plugin cache, so a reference that escapes the plugin root (e.g. `@../../../conventions/x.md`) resolves in this repo but silently fails once installed. See [Plugin caching and file resolution](https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution).

The fix is the officially recommended **symlink pattern**: keep one canonical copy of each convention at repo-root `conventions/`, and have each plugin's `conventions/` hold **symlinks** into it (`ln -s ../../conventions/<file>.md <plugin>/conventions/<file>.md`). Git stores symlinks (no duplicated content); on install, Claude Code dereferences within-marketplace symlinks and copies the real content into the cache. Skills reference conventions plugin-locally as `@../../conventions/<file>.md` (or `@../conventions/<file>.md` from an agent) — never a path that climbs out of the plugin. Symlinks require `git config core.symlinks true` (automatic on Linux/macOS/WSL; native Windows needs Developer Mode).

## License

MIT
