# vnext — direction for the next iteration of the decaf tools

> Status: **thinking / capture**. This is a design-capture doc, not a committed plan.
> It records the ideas and the DevMeta comparison that motivate a partial rewrite of
> the decaf tooling. Decisions here are provisional until promoted to a PRD/plan.

## Goal

A partial rewrite of the decaf tools to:

1. **Improve** the individual skills/agents (sharper, less redundant).
2. **Make them consistent** — naming above all (skill names, argument shapes,
   vocabulary across planning → dev → review).
3. **Introduce a more autonomous workflow** — a self-driving loop that can take a
   spec and deliver a multi-slice plan with minimal human gating, in the spirit of
   DevMeta's `/devmeta:go`.

The review half of this effort is **already underway**: it was broken out and
improved into **`decaf-exp`** (parallel multi-agent review, consolidation,
`resolve-code-review`, `auto-code-review`, `resolve-pr-feedback`). vnext is about
doing the equivalent for the **planning → development → autonomy** half.

## Why we studied DevMeta

DevMeta (`devmeta/`, also vendored under `course/commands/devmeta/`) is a
free-standing, project-agnostic framework for **autonomous, increment-driven
delivery**. It has one thing decaf lacks: an *unattended outer loop* that drives a
whole scope to completion. We mined it for the connective tissue, not the parts —
decaf's individual tools are generally sharper.

### What DevMeta uniquely provides (vs current decaf)

1. **A long-horizon autonomous driver** (`go`). decaf's auto-loops (`auto-dev`,
   `auto-tdd`, `auto-review`, `batch-dev`) are bounded to a single unit/batch and
   pause for the user. Nothing in decaf self-drives across many slices.
2. **A persistent state machine as the driver.** `tk` + `.devmeta/` are read to
   decide "what next," and the loop is crash-resumable. decaf skills are stateless
   per invocation.
3. **Mandatory recurring Inspect & Adapt.** `reflect` runs after *every* iteration
   (code review + outside-in gap verification + docs audit + replan). decaf's
   equivalents are user-invoked and one-shot.
4. **Self-learning.** Each cycle promotes lessons into CLAUDE.md/docs so "iteration
   N+1 is easier than N." decaf-memory (erinra) is a better store but isn't wired
   into a per-slice promotion ritual.
5. **Anti-stop engineering + scope-immutability.** The loop is deliberately built
   *not* to hand back at slice boundaries; only the human cuts scope.

The honest flip side: for almost every *individual* capability — review, planning
interviews, memory, TDD discipline — the decaf tools are richer. The gap is
**autonomy and horizon, not capability.**

## Vocabulary mapping (decaf ↔ DevMeta)

The two frameworks are the same shape one level apart. Settle on **one** vocabulary
during the rewrite (likely keep decaf's plan/phase/feature and drop increment/iteration).

| decaf-planning      | DevMeta            | Unit                                   |
|---------------------|--------------------|----------------------------------------|
| **plan** (all phases) | **increment**    | what an autonomous run drives, then stops |
| **phase** (one vertical slice) | **iteration** | one PR's worth of value + its closure  |
| **feature**         | **feature**        | one subagent's work                    |
| (impl-time tasks)   | **task**           | sequential steps                       |

Pipeline correspondence:

| decaf step                        | DevMeta step          | Notes |
|-----------------------------------|-----------------------|-------|
| `write-a-prd` + `prd-to-plan`     | `start-increment-spec`| decaf authors *why/what* far more thoroughly (see below) |
| `breakdown-phase`                 | `plan-iteration`      | both: phase/iteration → features, JIT |
| `batch-dev`                       | `run`                 | **batch-dev is the richer executor** (mechanism selection) |
| `close-plan` (+ per-item review)  | `reflect`             | decaf covers reconcile; missing verify-and-fix, learn, replan |
| **— none —**                      | **`go`**              | the missing autonomous outer loop |

## Spec rigor: decaf's advantage, and why it matters more under autonomy

The more autonomous the executor, the more load-bearing the spec — an unattended run
has no human checkpoint to catch drift, so the spec (esp. acceptance criteria) is its
only ground truth.

- **decaf authors specs far more rigorously.** `write-a-prd` delegates to `grill-me`
  (breadth-first area mapping → depth-first branch exhaustion → dependency resolution
  → progress ledger). `start-increment-spec` is a flat 8-question pass. No contest.
- **DevMeta's compensating bet** is the *loop*, not the spec: plan JIT, reflect,
  replan, cheap rebuild. But reflect's outside-in verification checks code against the
  spec's *own* criteria — it catches **execution drift**, and is **blind to spec/intent
  error**. With a thin interview the risk is "reliably builds the wrong thing."
- **Implication:** decaf's planning front-end is exactly the right input to a
  go-style loop. Keep `write-a-prd`/`grill-me` for decision-completeness.
- **Graft to keep from DevMeta:** its **"verify on screen" executable acceptance
  criteria**. A robot can run a command and diff output; it can't verify a narrative
  user story. The ideal spec = grill-me's decision-completeness expressed with
  machine-checkable acceptance.

## Proposed `decaf:go` (autonomous driver)

```
prd-to-plan  →  nibs hierarchy (epic/phase, blocked-by edges)        [once, up front]
                          │
            ┌─────────────▼──────────── decaf:go (new outer driver) ──────────────┐
            │  1. SELECT next ready phase   ← nibs --ready + topo  (≈ tk next)     │
            │  2. breakdown-phase  (JIT, non-interactive)  → feature nibs          │
            │  3. batch-dev (gates off), scoped to this phase's children           │
            │  4. REFLECT: verify-and-fix + reconcile + (learn) + replan           │
            │  5. merge phase → integration branch; loop                           │
            │                                                                      │
            └──────────  stop only when no ready phases remain (plan complete) ────┘
```

- **Loop over `breakdown-phase` (JIT), not all-phases-up-front** — so each phase is
  planned against the code earlier phases produced. Matches DevMeta deliberately.
- **Step 4 is four jobs, not one:**
  1. **Verify-and-fix (outside-in)** — run acceptance criteria; **fix gaps now, don't
     defer** (opposite of today's `close-plan` posture).
  2. **Reconcile + close** — `close-plan` proper; close the phase nib, spawn
     follow-ups for genuinely descoped work.
  3. **Learn** — promote lessons to CLAUDE.md/docs/erinra. *No decaf skill does this
     yet.*
  4. **Replan** — reassess remaining phases against what now exists. `close-plan`
     doesn't; DevMeta reflect Step 11 does.

## What exists vs what to build

**Reuse as-is (the sharp tools already exist):**
- `prd-to-plan` — plan authoring → nibs.
- `breakdown-phase` — phase → features.
- `batch-dev` — executor with **mechanism selection** (series / fan-out-worktree /
  workflow / agent-team) + dependency ordering + merge protocol. Strictly richer than
  DevMeta's `run`; keep this.
- **nibs as the state machine.** `nibs --ready` + `blocked-by` + topo order *is*
  `tk next`. Gives "what next" and crash-resumability for free — no `.devmeta/`-style
  state store to rebuild.
- `decaf-exp` review stack — the reflect step's review can call it instead of an
  inline checklist.

**Surgery needed:**
- **`breakdown-phase` → unattended mode** (suppress the "show breakdown, ask user"
  gate).
- **`batch-dev` → gates stripped** for loop use (drop Phase 1 confirm, Phase 3
  clarify, Phase 5 Approve/Adjust/Cancel, per-cluster check-ins, merge-to-main
  decision). Scope its queue to the current phase's children. **Keep** mechanism
  selection + merge protocol.
- **`close-plan` → flip posture** from defer-and-record to fix-now-within-phase
  (defer only *across* phases). Possibly split: fix-now in 4.1, reconcile in 4.2.

**New pieces to build:**
- **The driver (`decaf:go`)** — thin outer loop; picks next ready phase, refuses to
  stop at phase boundaries, re-derives position from nibs each lap.
- **Executable acceptance criteria** — a convention (and/or a verification subagent)
  so `prd-to-plan`/`breakdown-phase` emit machine-runnable acceptance, not just
  narrative checkboxes. *This is the graft that makes the loop trustworthy.*
- **Learn/replan step** — the self-improvement half (optional but high value).

Net: a **smaller build than DevMeta was**. We're adding connective tissue and
inverting a few human gates, not writing the engine from scratch.

## Consistency / naming cleanup (the second goal)

To capture as we touch each tool — provisional, decide during the rewrite:

- Unify the **plan/phase/feature/task** vocabulary across planning, dev, and review;
  retire any leftover increment/iteration language if devmeta ideas are absorbed.
- Consistent **autonomy suffixes**: today `auto-*` (auto-dev/auto-tdd/auto-review)
  vs `batch-dev` vs `handle-*` (interactive). Pick a coherent scheme:
  interactive vs `--auto`/unattended vs the full driver.
- Consistent **argument shapes** across `auto-*` / `batch-dev` (`--review`,
  `--max-iterations`, scope, `--base-branch`).
- Align decaf-exp's `low/mid/high/max` review modes with whatever the rest adopts.

## Open questions

- **Plan vs phase as the autonomous unit.** `go` stops at the plan boundary
  (= increment). Confirm a single `decaf:go` run = one whole plan, and that the
  human owns "which plan next" (matches DevMeta's increment-boundary stop).
- **Where does `learn` write?** CLAUDE.md vs docs vs erinra — and is it wired per
  phase or per plan?
- **Executable acceptance** — convention in the nib body, a separate criteria file,
  or a verification subagent that interprets narrative criteria? Related known gap:
  nib status isn't updated when work is delegated to a subagent (the subagent gets a
  fresh, work-item-unaware context) — so the driver, in the main context, must own
  nib status transitions before/after each dispatch.
- **How much of DevMeta's anti-stop discipline to import** vs leaving lightweight
  check-ins for safety.
- **Scope-immutability** — adopt as a hard rule, or keep decaf's softer
  deviation-rules model (auto-fix / ask / never) from `prd-to-plan`?

## References

- `devmeta/` — the studied framework (README + go/start-increment-spec/plan-iteration/run/reflect/status).
- `course/` — the Atomic-CRM multi-agent harness that vendors devmeta; source of the
  `batch-dev`-style mechanism-selection ideas (single/fan-out/workflow/team).
- `decaf-exp/` — the already-completed review rewrite; the template for this effort.
</content>
</invoke>
