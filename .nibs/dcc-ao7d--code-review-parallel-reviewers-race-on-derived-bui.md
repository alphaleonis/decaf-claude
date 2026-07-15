---
# dcc-ao7d
version: 1
title: 'code-review: parallel reviewers race on derived build/test state (compiled output, caches, ports)'
status: completed
type: bug
priority: normal
created_at: 2026-07-15T14:52:49Z
updated_at: 2026-07-15T15:01:24Z
order: zz
---

Split from #dcc-bw5j: same invariant — during the parallel review wave, no agent may mutate state another agent reads — but a different resource. Tracked source is fixable by prohibition; derived build state is not, at least not cheaply.

## Evidence (verified, from this repo's own corpus)

`reports/2026-07-14-nibs-batch-buffer-safety-code-review-session/README.md` records that `typescript`, `performance`, and `go` returned clean "after verifying against installed package source or **compiled output** rather than by assumption". Reviewers read derived artifacts as evidence — and that was written up as a strength, correctly.

Meanwhile the Pre-flight gates block in `code-review/SKILL.md` tells reviewers "Do NOT re-run the standard gate suite above — it already ran once for this wave" but "Targeted execution (repro probes, race detector, focused test runs) is still encouraged." In most ecosystems a targeted test run compiles first, so it rewrites the very output a sibling may be reading.

## Failure modes

- An agent reads compiled output mid-rebuild, sees a symbol absent or partial, and files a finding. Structurally identical to the #dcc-bw5j race — a phantom finding from a mid-write read.
- Contention on shared runtime resources (ports, test databases, lock files, caches) produces spurious test failures that an agent may attribute to the diff.

[Unverified] No instance has been observed in the corpus. Unlike #dcc-bw5j, this is a mechanism identified by inspection, not a reproduced defect. Filed now so it is not rediscovered later.

## Why not the same fix as #dcc-bw5j

Serializing through the orchestrator works for revert-probes because a probe is rare, discrete, and one-shot. Test execution is iterative exploration: run, read, form a hypothesis, run again. Nominate-and-wait would gut what the 07-14 report identifies as the reviewers' strongest behavior. Per-agent worktrees would fix it properly but cost a cold build per agent with no shared cache — disproportionate. (See #dcc-bw5j Notes for the verified isolation recipe if this is ever revisited.)

## Fix

Downgrade the evidence rather than serialize the work. This is portable across every repo the skill runs in, which matters because the generic skill cannot know the project's build system.

## Todo

- [x] code-review SKILL.md Base Context Template: add an evidence-admissibility rule — a failing test, a missing symbol, or an absent/partial compiled artifact observed during the parallel wave is not admissible on its own, because siblings may be building concurrently. Re-verify in a quiet tree before reporting, or report at reduced confidence and nominate re-verification (same channel as #dcc-bw5j's probe nomination).
- [x] code-review SKILL.md: extend the orchestrator's post-wave step to run nominated re-verifications alongside nominated probes — one serial pass, single actor. Depends on #dcc-bw5j landing that step.
- [x] Considered and deliberately NOT done here: per-agent build/cache/temp directories (via the toolchain's env var or flag) would isolate writable derived state properly, but the mechanism is ecosystem-specific and this repo ships a *generic* skill that cannot know the project's build system. It belongs in per-project config in the consuming repo. The admissibility rule above is the portable substitute; revisit only if a real instance shows the rule is not enough.
- [x] Record that the existing pre-flight gate already embodies the right instinct — serialize the expensive shared build once, up front. The gap is only that targeted runs were left unconstrained.

## Notes

- The Pre-flight gates section encourages running a "race detector" — concurrently, in a shared tree.
- I initially assessed this as "much less likely to fabricate a Critical" than #dcc-bw5j. That was unlabeled speculation and the corpus evidence above points the other way: reviewers demonstrably read compiled output as evidence, which is precisely the racy resource.

Related: #dcc-bw5j, #dcc-wyba, #dcc-unre.

## Summary

Fixed on branch `dcc-bw5j-probe-isolation` (off main), alongside #dcc-bw5j — both touch the same Base Context Template.

**`decaf-quality/skills/code-review/SKILL.md`** — added an **Admissibility** rule to the Pre-flight gates block of the Base Context Template. It names the asymmetry directly: tracked source is now stable (nobody may mutate it, per #dcc-bw5j) but derived state is not — compiled output, caches, and fixtures are shared and mutable while siblings run targeted builds. So a failing test, a missing symbol, or an absent/partial build artifact seen during the wave is not admissible on its own; confirm it reproduces, or report at reduced confidence and nominate re-verification through the same `### Probe Requests` channel #dcc-bw5j introduced. Findings grounded in source reads are explicitly unaffected.

The orchestrator's Step 4.5 handles nominated re-verifications alongside probes — one serial pass, single actor.

Per-agent build/cache directories were considered and deliberately not done: the mechanism is ecosystem-specific and this repo ships a generic skill that cannot know the project's build system. It belongs in per-project config. The admissibility rule is the portable substitute; revisit if a real instance shows it insufficient.

Note the fix leans on #dcc-bw5j: the rule can say "source is stable" only because reviewers no longer mutate it. Had these landed separately, this one would have been weaker.
