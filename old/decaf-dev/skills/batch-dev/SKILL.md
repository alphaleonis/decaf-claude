---
name: batch-dev
description: Orchestrate execution of MULTIPLE nibs in one run. Selects a queue, understands the nibs collectively (including how they fit together), then chooses the best execution mechanism per cluster — single series agent, parallel fan-out, scripted workflow, or agent team — and dispatches with ONE approval gate. Use when the user wants to work several nibs together (in parallel or series) rather than one at a time. Complements /auto-dev and /auto-tdd (which handle a single nib).
argument-hint: "<nib-id...> | --filter <expr> | --ready  [--review quick|std|max] [--max-iterations N] [--base-branch <name>]"
---

# Batch Dev

You are the **conductor** for a batch of nibs. Your job is **triage and dispatch**: understand the work collectively, decide *how* to run each piece (not just *what* to build), get one approval, then drive it to completion.

You are NOT locked to one execution shape. From here you can invoke any executor:
- `Skill` → reuse `/auto-dev` / `/auto-tdd` patterns
- `Agent` → fan-out subagents, or a named **team** coordinated with `SendMessage`
- `Workflow` → a deterministic scripted pipeline

Choosing the right one per cluster is the whole point of this skill.

## Core principle — bias toward simplicity

**Most nibs are plain single series agents.** Fan-out, workflow, and agent-team are *escalations*, each requiring a concrete trigger (see the heuristics). Never reach for a heavier mechanism than the work warrants — spending more effort *choosing* a mechanism than the work merits is the failure mode to avoid. When in doubt, run a nib as a single series agent.

A second hard rule: **when parallel-safety is uncertain, serialize.** Under-parallelizing is cheap; a corrupted worktree merge is not.

## Prerequisites

- This project uses **nibs**. If you are unsure of any `nibs` syntax, run `nibs prime --full` before using it. Do not guess.
- Detect the project's build/verify commands during Phase 1. For NZBrowse the canonical commands are `dotnet build NZBrowse.slnx` and `dotnet test` (see `CLAUDE.md`). Confirm before relying on them.
- Parallel fan-out (Phase 6b) uses git worktrees under `.claude/worktrees/` — ensure that path is gitignored so worktree contents are never accidentally committed.

## Argument parsing

Parse `$ARGUMENTS`:

1. **Queue source** (one of):
   - Bare nib IDs (one or more) — the explicit queue.
   - `--filter <expr>` — a nibs search/filter expression resolved via `nibs list`/`nibs query`.
   - `--ready` — all ready/unblocked nibs (`nibs list --json --ready`).
   - If none given, ask the user which nibs to batch.
2. `--review quick|std|max` (default `std`) — passed to per-nib review.
3. `--max-iterations N` (default `3`) — review iteration cap.
4. `--base-branch <name>` — override the batch branch name (default derived in Phase 6).

---

# Phases

Run the phases in order. Phases 1–5 are planning (interactive where noted). Phase 5 is the single approval gate. Phases 6–8 execute, with check-ins at every cluster boundary.

## Phase 1 — Select

1. Resolve the queue from the arguments. Show the resolved set as a table: `id | type | title | status`.
2. Drop anything already `completed`/`scrapped`; flag anything `in-progress` (ask whether to include).
3. Detect project context: language(s), framework, **build command**, **test command** (confirm with the user if ambiguous).
4. Confirm the resolved queue with the user before proceeding. This is a lightweight confirmation, not the approval gate.

## Phase 2 — Comprehend

Understand every nib **individually and collectively**. This step itself fans out.

1. Pull each nib's full body: `nibs show --json <id> [id...]`.
2. Pull declared relationships: `nibs links --json <parent-or-each> --rel blocked-by,blocking,children` as relevant; capture `blocked_by` edges. Use `nibs links --rel children --order topo` when the queue is an epic's children.
3. **Fan out one read-only `Explore` agent per nib** (single message, multiple `Agent` calls so they run concurrently). Each returns a structured summary:
   - `files` — files/areas the nib will likely create or modify
   - `types` — key types/components/modules touched
   - `declared_deps` — blocked_by / blocking from nibs
   - `overlap_candidates` — other nibs in the batch it likely shares files/types with
   - `approach_hint` — does this produce testable logic (→ tdd) or UI/config/scaffolding (→ dev)?
   - `risks` / `unknowns` — anything ambiguous
4. Assemble the collective picture: a **dependency graph** (declared edges) and an **overlap map** (inferred shared files/types).

## Phase 3 — Clarify

Surface genuine ambiguities from Phase 2 (conflicting assumptions, unclear scope, missing decisions) and ask the user. Keep it to questions that actually change the plan. This is one of only two interactive moments; use it well, then proceed.

## Phase 4 — Strategize

Produce the execution strategy.

### 4a. Assign an approach to each nib (tdd vs dev)

- **tdd** — the nib produces testable logic with clear behaviors: Core domain/entities, operations, services, parsing, state machines.
- **dev** — UI/Razor components, styling, config, scaffolding, infra, templates.
- Prefer **tdd** when in doubt and the code is testable. Mirrors the `/auto-tdd` vs `/auto-dev` split.

### 4b. Cluster the nibs and assign a mechanism

| Mechanism | Warranted when | Executor |
|-----------|----------------|----------|
| **Single series agent** *(default)* | A normal, self-contained nib | `/auto-dev` / `/auto-tdd` execute+review tail (see Phase 6a) |
| **Fan-out parallel subagents** | Several nibs **provably independent** — no declared edges between them AND no inferred file/type overlap | `Agent` × N with `isolation: "worktree"` (Phase 6b) |
| **Workflow** | A single large nib (or tight cluster) that decomposes into a **uniform, repeatable** sub-task over many items (apply the same change to N call sites, a migration, a broad sweep); wants determinism, structured per-item results, loop-until-done, or adversarial verification | `Workflow` script (Phase 6c) |
| **Agent team** | A cluster of **interdependent** nibs that must **negotiate** (one defines an interface the others consume; implementers coordinate the contract as it emerges) | `Agent` + `SendMessage`, named workers (Phase 6d) |

Apply the bias-toward-simplicity principle: only escalate beyond "single series agent" when a concrete trigger above is clearly met.

### 4c. Order the clusters (two layers)

- **Declared dependencies** = *correctness* order. Authoritative; never violate. A nib runs only after everything in its `blocked_by` has completed.
- **Inferred file overlap** = *parallel-safety*. If two nibs overlap (or overlap is uncertain), they must NOT be in the same fan-out/parallel cluster — serialize them.

Produce: clusters, each with its mechanism and member nibs (with approach), and a total order with explicit check-in points.

## Phase 5 — Approve (the single gate)

Print the strategy as a rich textual plan:

```
## /batch-dev Strategy — {N} nibs, {M} clusters

Cluster 1  [series, sequential]
  1. {id}  {title}            approach: {tdd|dev}
  2. {id}  {title}            approach: {dev}   (blocked-by {id})

Cluster 2  [fan-out parallel, worktrees]   — independent of Cluster 1
  - {id}  {title}             approach: {tdd}
  - {id}  {title}             approach: {tdd}

Cluster 3  [workflow]                      — runs after Cluster 2 merges
  - {id}  {title}             approach: {dev} (uniform pipeline)

Batch branch: batch/{slug}
Order:        C1 -> C2 -> (merge) -> C3
Check-ins:    after C1 | before C2 launch | after C2 merge | before C3 | final
Review:       {reviewMode}, max {maxIterations} iterations
```

Then ask via `AskUserQuestion` (a single gate): **Approve / Adjust / Cancel.**

- **Approve** → proceed to Phase 6.
- **Adjust** → the user describes changes in free-form prose (drop/add a nib, re-cluster, change a cluster's mechanism, change a nib's approach, reorder, change parallelism degree). Apply them, re-present the plan **once**, and ask again.
- **Cancel** → stop; leave all nibs unchanged.

**The approved plan naming a `workflow` cluster IS the user's explicit opt-in to run a `Workflow` for that cluster.** Do not launch any workflow before this approval.

---

## Phase 6 — Execute

### Common rules (apply to every cluster)

- **Batch branch**: before the first cluster, create one branch for the whole run off current HEAD: `git switch -c batch/{slug}` (slug derived from the batch theme or first nib; or `--base-branch`). Never commit straight to `main`. Record the starting branch to return to at the end.
- **Nib status**: set each nib `in-progress` **before** launching its worker; set it `completed` **after** the worker reports success. Subagents/workflows run fresh and will NOT update nibs — you (the conductor, in the main context) own status updates.
- **Commits**: commit code **and** the nib file together. Keep the nib's todo items checked off as work completes.
- **Check-ins**: at each cluster boundary, report what finished and what's next, and pause for the user — especially **before launching any parallel/workflow/team cluster** and **after each integration/merge**.
- **Verify**: run the build (and tests, for tdd work) after each unit of work; fix breakage before moving on.

### Phase 6a — Single series agent (the default)

For each nib in the cluster, in order. The batch-level plan already covers the per-nib plan, so **do NOT call `/auto-dev` / `/auto-tdd` wholesale** (their interactive Step-1 plan gate would re-prompt and break the unattended run). Instead reuse their **execute + review tail**:

1. Set the nib `in-progress`.
2. Launch a **general-purpose `Agent`** with the pre-approved-plan prompt pattern (as in `/auto-dev` Step 2 / `/auto-tdd` Step 2 — *"the plan is already approved, do NOT ask for confirmation"*). For `tdd` nibs, instruct a full red-green-refactor loop following the project's test conventions; for `dev` nibs, implement step-by-step verifying the build after each step.
3. After it reports, run `/decaf-review:auto-review {reviewMode} --max-iterations {maxIterations}` (it auto-detects scope from uncommitted changes and manages its own subagent lifecycle). If a running-app build lock or a trivial change makes the full auto-review impractical, a focused manual review of the diff is an acceptable substitute — note the substitution in the report.
4. Commit code + nib; set the nib `completed`.

### Phase 6b — Fan-out parallel subagents

Only for a cluster of **provably independent** nibs.

1. Set all cluster nibs `in-progress`.
2. Ensure the batch branch working tree is clean (commit/stash anything pending).
3. Launch one `Agent` per nib **in a single message** (multiple `Agent` calls) with `isolation: "worktree"` so each works in its own git worktree without colliding. Each agent prompt must:
   - **Provision the frontend before building** — a fresh worktree has no `node_modules`, and the build regenerates Tailwind/TypeScript, so a plain build fails the frontend step. Tell the worker to junction the main repo's packages first (instant, read-only): from the worktree root run `cmd /c "mklink /J src\NZBrowse.UI\node_modules <main-repo-abs-path>\src\NZBrowse.UI\node_modules"` (fallback: `npm install` in `src/NZBrowse.UI`). Validated essential — without it every worktree UI build fails.
   - Implement its nib (tdd/dev per the plan), verify build/tests **inside its worktree**. On Windows, avoid `cd /d` in the Bash tool (it errors); use plain `cd` or the PowerShell tool (its cwd is already the worktree).
   - Self-review its changes inline (focused diff review for correctness + conventions). Do NOT invoke the main-context `/decaf-review:auto-review` from inside a worktree.
   - **Commit code only** (NOT `.nibs/*.md` — the conductor manages nib status) and report: files changed, build/test result, final commit **SHA** (`git rev-parse HEAD`), and branch (`git rev-parse --abbrev-ref HEAD`).
4. Proceed to Phase 7 to merge — by branch or by reported SHA.

> **Confirmed behavior** (validated run nz-dct3, 2026-06-05): `isolation: "worktree"` creates a worktree at `.claude/worktrees/agent-<id>` on a branch `worktree-agent-<id>`, and the agent result reports both the path and branch. Committed work persists in the shared object store, so the reported branch/SHA merges cleanly in Phase 7; pinning a stable ref (`git branch batch/{slug}/{id} {sha}`) before cleanup is optional insurance, not required. After merging, prune with `git worktree remove --force <path>` + `git branch -D worktree-agent-<id>`.

### Phase 6c — Workflow

For a cluster best run as a deterministic pipeline (uniform sub-task over many items).

1. Scout the work-list inline first (e.g. the call sites to change), then author a `Workflow` script that pipelines each item through implement → verify (and adversarial-verify if warranted), returning structured per-item results.
2. Use `isolation: 'worktree'` on workflow agents if they mutate files in parallel.
3. Set the cluster's nib(s) `in-progress` before launching; the workflow runs in the background and notifies on completion.
4. On completion, integrate its branch/commits via Phase 7, commit + set nib(s) `completed`.

### Phase 6d — Agent team

For an interdependent cluster needing negotiation.

1. Set the cluster nibs `in-progress`.
2. Spawn named `Agent`s (e.g. a `contract` owner + `consumer` workers), each addressable; coordinate via `SendMessage` as the contract emerges. Use worktrees if they mutate overlapping files in parallel; otherwise serialize the shared parts.
3. Integrate via Phase 7; commit + set nibs `completed`.

## Phase 7 — Integrate (merge protocol)

Applies to any cluster that produced separate branches/worktrees (6b/6c/6d). Series clusters (6a) commit directly onto the batch branch and need no merge.

1. **Safety net first**: tag the pre-merge batch-branch state (`git tag batch-{slug}-premerge-{cluster}`) so any bad merge is recoverable.
2. Merge the cluster's commits into the batch branch **sequentially** — declared-dependency order first, then smallest-diff-first to shrink conflict surface. Merge by branch or by pinned SHA.
3. **After each merge**, run build (+ tests) so an integration break is attributed to the specific merge that caused it. Fix before the next merge.
4. **On conflict**: pause at the cluster boundary and surface the conflict to the user. Auto-resolve ONLY trivial/unambiguous cases; never silently force-resolve.
5. Clean up worktrees/temp branches once merged.

## Phase 8 — Report

```
## /batch-dev Complete — batch/{slug}

| Cluster | Mechanism | Nibs | Result |
|---------|-----------|------|--------|
| 1 | series   | n    | ✅ completed |
| 2 | fan-out  | n    | ✅ merged |
| 3 | workflow | n    | ⚠️ 1 parked |

**Completed**: {ids}
**Parked/failed**: {ids + why}
**Build/tests on batch branch**: {pass/fail}
```

- Run a final `dotnet build NZBrowse.slnx` + `dotnet test` on the batch branch. **First check no app instance is running** — a live `NZBrowse.exe` locks the WinForms output DLLs and fails the build's copy step (`MSB3021/MSB3027 ... file is locked by NZBrowse`). If one is running and can't be closed, verify via the test projects instead (`dotnet test tests/NZBrowse.Core.Tests/...` and `tests/NZBrowse.UI.Tests/...`) — they rebuild the changed Core/UI code without producing the locked WinForms exe — and flag that the exe build plus any **visual** acceptance criteria need the app closed (purely-visual criteria can't be auto-verified — leave such nibs `in-progress` until confirmed).
- Leave the **merge-to-main / push decision to the user** (honors "commit/push only when asked; branch first").
- Offer follow-up nibs for anything deferred or parked.

---

## Failure handling (default policy — overridable at approval)

- **Skip-and-continue**: a failed nib does not abort the batch.
- **Park** the failed nib: keep it `in-progress`, append a `## Batch failure note` to its body (what failed, build/test output summary, where it stopped). Never write secrets/log output that could contain credentials into the nib.
- **Hold dependents**: any nib whose `blocked_by` includes a failed nib is skipped and reported as held.
- Report all parked/held nibs in Phase 8.

## Notes & caveats

- The conductor stays in the main context; heavy work is isolated in subagents/workflows so the main context isn't exhausted.
- `/decaf-review:auto-review` runs from the main context and manages its own subagent lifecycle → use it for **series** clusters; for **parallel** clusters each worker reviews its own changes inside its worktree.
- Workflows cannot pause for the user mid-run — that is exactly why the whole strategy is approved up front (Phase 5 before any launch).
- Mixed mechanisms add coordination cost: when a background workflow runs while series work proceeds, sequence carefully and integrate at clean boundaries.
- Keep the batch small enough to supervise. If the queue is large, propose splitting it across multiple `/batch-dev` runs at Phase 1.
