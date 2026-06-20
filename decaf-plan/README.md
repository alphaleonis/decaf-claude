# decaf-plan

Decide **what** and **how** to build with Claude Code: research, specs, phased plans, phase breakdowns, design exploration, and architecture review. The third member of the vNext trio alongside [`decaf-build`](../decaf-build) (create new behavior) and [`decaf-quality`](../decaf-quality) (improve existing code) — `decaf-plan` is where you **decide**, and its output is plans, RFCs, and decisions rather than code. It declares no outward dependencies.

## Skills

| Skill | Purpose |
|-------|---------|
| `research` | Dig into an unfamiliar problem or technology from several angles and write up what you find — before drafting a spec, when the domain or trade-offs aren't clear yet. |
| `draft-spec` | Interview the user and explore the code to write a **spec** (PRD): *what* to build and *why*. (Was `write-a-prd`.) |
| `grill-me` | Interview the user one decision at a time to stress-test a plan or design until it holds up. Used standalone or pulled in by `draft-spec`. |
| `draft-plan` | Turn a spec into an ordered, **phased** build plan and create the work-item nibs for it (vertical-slice tracer bullets). (Was `prd-to-plan`.) |
| `breakdown-phase` | Break one phase of a plan into concrete, buildable features, each with a done-checklist. |
| `close-out` | Reconcile built vs. planned, record decisions/deviations, close the item (a phase **or** a whole plan), and file follow-ups for deferred work. (Was `close-plan`.) |
| `explore-designs` | "Design it twice": generate several radically different designs for a decision — from a single method up to a whole architecture — compare them, and write up the chosen one. (Was `design-an-interface`.) |
| `architecture-review` | Explore existing code for structural/testability improvements (deepen shallow modules, untangle coupling); output is recommendations (RFCs), not code. (Was `improve-codebase-architecture`.) |
| `resolve-architecture-review` | Walk `architecture-review` proposals one at a time, designing the interface and writing an RFC for each. (Was `handle-architecture-improvements`.) |

## The planning pipeline

The skills chain into a path from "unfamiliar problem" to "ready-to-build work items":

```
research  →  draft-spec  →  draft-plan  →  breakdown-phase  →  (build)  →  close-out
              ↑ grill-me
```

```
/decaf-plan:research "<topic>"            # explore an unfamiliar space
/decaf-plan:grill-me                       # stress-test a plan/design
/decaf-plan:draft-spec                     # write the spec (PRD)
/decaf-plan:draft-plan                     # spec → phased plan + work items
/decaf-plan:breakdown-phase <phase>        # one phase → features
/decaf-plan:close-out <phase|plan>         # reconcile and close
/decaf-plan:explore-designs                # "design it twice" for a decision
/decaf-plan:architecture-review            # find structural improvements → RFCs
/decaf-plan:resolve-architecture-review    # walk candidates → RFCs
```

## Analyze / resolve pairing

`decaf-plan` follows the family convention: an **analysis** skill produces candidates, and a matching **`resolve-<analysis>`** skill walks them one at a time. Here that pair is `architecture-review` → `resolve-architecture-review` (architecture-review surfaces structural improvements; resolve turns each into an RFC).

## Conventions

The work-item skills (`draft-spec`, `draft-plan`, `breakdown-phase`, `close-out`, `grill-me`, `research`, `resolve-architecture-review`) share `conventions/work-items.md`, which describes how to detect and target the available tracker (GitHub Issues, Azure DevOps, Nibs) or fall back to a local Markdown file. It is bundled with the plugin and referenced as `@../../conventions/work-items.md`.

## Coming in vNext

`draft-plan`, `breakdown-phase`, and `close-out` will gain **unattended modes** so the autonomous delivery loop (`auto-deliver`, living in `decaf-build`) can drive a whole plan to completion. That work is scoped to the loop design — not implemented here.
