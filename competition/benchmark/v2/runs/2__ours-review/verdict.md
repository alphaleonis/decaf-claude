# Subject 2 / ours-review — first end-to-end v2 cell

checkpoint `3aa499ae7d23` (base `a2a5480e4b59`), 2026-07-07 · opus-4-8 · effort high
rc=0 · wall 471s · cost $4.16 · external accesses 0

## Scoring against v2/analysis/subject-02/answer-key.json

| Entry | Verdict |
|---|---|
| **e1** — DeclaredOnly→FlattenHierarchy does not fix AmbiguousMatchException | **TP-primary — CAUGHT** |
| ~~e2~~ — dropped `IgnoreCase` | **WITHDRAWN as invalid** (not a miss; see key `rejected[]`) |

**1 of 1 valid entries caught.**

The reviewer's High #1 matches e1's `must_flag` exactly, and is sharper than the key statement:
it names the precise trigger — the property hidden at an *intermediate* ancestor with the leaf
inheriting without redeclaring, so `DeclaredOnly` returns null and the fallback walks the full
hierarchy and throws. It adds that `FlattenHierarchy` is a no-op for instance lookups, which
strengthens the argument, and grounds the claim in the pre-fix behavior rather than asserting it.

## Findings beyond the key (would score valid-other)

- **Medium #2**: the six added tests never drive the fallback branch — deleting the entire fallback
  block leaves them all green. A test-adequacy finding about the PR's own tests.
- FlattenHierarchy is a misleading no-op for instance lookup; no rationale comment on the two-step
  lookup; `MidLevelModelWithShadow` is inert scaffolding; `IgnoresStaticProperty` has no positive
  control.

## False-positive discipline

Explicitly reasoned that dropping `BindingFlags.Static` is intentional and safe, and declined to
report it — the same class of reasoning as the invalid e2, handled correctly.

## Caveats

- **The tool-access controls were never exercised**: 0 gh calls, 0 docs-at calls. The leak audit is
  clean but uninformative. The shims are verified in isolation, not under a reviewer that wants the
  network.
- **No dotnet SDK in the container**, so the reviewer could not build or run tests; findings are
  static analysis. Subjects whose defects need execution to confirm will be weaker here.
- One cell, one tool, one subject. This validates the pipeline, not the tools.
