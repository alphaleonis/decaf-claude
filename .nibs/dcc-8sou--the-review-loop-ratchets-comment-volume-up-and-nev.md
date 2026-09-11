---
# dcc-8sou
version: 1
title: Comment corrections are always expansions, so review ratchets prose volume up
status: todo
type: feature
priority: high
created_at: 2026-09-10T20:33:13Z
updated_at: 2026-09-11T12:11:55Z
order: yV
---

Nearly half of every review's findings are about a comment that stopped matching
the code, and the remedy offered for one is always a longer comment. The loop
cannot cut.

Measured on `nibs` (`~/code/nibs`): 159 review reports in `.decaf/code-reviews/`,
783 findings, attributed by their `Found by` field.

## The evidence

| Measure | Value |
| --- | --- |
| Findings about a prose artifact (comment / doc / help text / README claim) | **355 of 783 (45%)** |
| `knowledge-reviewer` findings | 170 — second-largest producer of any agent |
| …about a prose artifact | 115 of 170 (67%) |
| …whose **Fix** contains any cut verb | **18 of 115** |
| …demanding genuinely absent knowledge | ~17 (10%) |
| Comment lines, non-test Go | 19,099 of 60,524 (31%) |
| Lines in comment blocks >25 lines | 4,238 (21% of comment volume) |

The prose share is not one persona's habit — it is system-wide:
`quick-reviewer` 51%, `broad-reviewer` 48%, `consistency-reviewer` 48%,
`solo-reviewer` 47%.

The 2026-09-10 hand-trim pass (`9a01046..c1fbdc6`, six `docs(...)` commits)
removed 818 comment lines and wrote 649 back: **net −169, 0.9%**. A pass whose
whole purpose was cutting could barely cut.

## The mechanism

`knowledge-reviewer` is not mainly demanding comments — it is auditing them, and
the audit has one direction. The dominant finding is "this comment is false", and
the finding's `**Fix:**` field hands the fixer a drafted replacement:

- "Append a short paragraph to the `StatusConfig` doc block…"
- "Replace *'so a nib always answers to exactly one of the two groups'* with the
  true statement **and its exception**…"

So the reviewer authors the prose. A false claim is never deleted; it is restated
more precisely, which is longer and carries more surface to go false next round.
The drift findings are interest on the volume, and each payment raises the
principal.

What drifts is overwhelmingly the **checkable** claim — enumerations and
completeness assertions: "the single definition", "every deliberate raw read
carries a directive", "one call site per mirror", "the two classes". A comment
asserting a checkable property is a test that does not run.

## What to change

### 1. Flip the default remedy for drifted prose (primary)

Where a reviewer finds a comment that no longer matches the code, the first
remedy offered is **delete the claim**. Restating it more precisely requires a
stated reason the claim has to live in the code at all — the existing
not-recorded-elsewhere and durable-relevance gates
(`decaf-quality/agents/knowledge-reviewer.md:215`), which today apply only to
*missing*-knowledge findings. And bound the drafted replacement: no longer than
what it replaces without saying why.

**Placement**: the **Base Context Template** in
`decaf-quality/skills/code-review/SKILL.md:453`. It is the one block every seat
in a wave receives, and the prose share is spread across all of them — a rule in
`knowledge-reviewer` alone reaches 22% of the findings. `solo-reviewer` carries
its own brief and needs it written in directly.

### 2. Convert checkable claims to mechanism (second)

A finding whose subject is an enumeration or a completeness claim proposes a
guard or a test, plus deletion of the sentence — not a corrected sentence. The
repo-level rule already exists and no persona carries it: *"Execute a claim
before you write it… Prefer a guard that makes the claim checkable to a sentence
asserting it."*

### 3. A knowledge-excess rule (third — smallest lever)

The original ask, at SHOULD/COULD, never MUST. Worth doing, but it reaches ~71
blocks against 355 drift findings, so it is not the fix.

Design constraints, measured on the same tree (112 blocks >25 lines):

- **Exempt** doc comments on **exported** identifiers (25 — godoc is Go's
  documented home for that prose; flagging it collides with RULE 1), package/file
  docs (5), and generated files (2).
- The target is docs on **unexported** functions (59), blocks **inside a function
  body** (9), and free-floating blocks (3).
- **Trigger at ~25 lines** for doc comments, ~10 only inside a body. A flat
  10-line trigger reaches 478 blocks and half the comment volume — far past the
  intended target.
- Phrase it as *"should a type, a guard, or a narrower interface carry this?"*,
  never "shorten it".
- **Exempt canonical invariants.** `internal/nibcore/flock.go` is 65% comment and
  its deadlock warning earns every line. `internal/graph/interfaces.go:42` is the
  wanted shape — "CANONICAL INVARIANT … internal/graph defer here rather than
  re-derive it". Reward the pointer, flag the re-derivation.

## Risks

- The excess rule must hand narrative and history to the existing
  `TEMPORAL_CONTAMINATION` / `BASELINE_REFERENCE` categories (MUST) and claim only
  truthful-but-surplus prose (SHOULD). If both fire on one block, consolidation's
  "highest severity wins" promotes a volume finding to MUST and inverts RULE 0.
- No collision with `consistency-reviewer`: `CONS_COMMENT` is falsity, this is
  volume.
- Not a comment-stripping mandate. The house style is comment-heavy on purpose
  and much of it is load-bearing. The 65% in `flock.go` is why a Critical
  lock-order bug was diagnosable.
- Counting phrases is not a measurement. `"rather than"` at 661 looked like the
  signature of pre-emptive defense; sampled, most instances are timeless-present
  contrastive phrasing, which is often the tightest way to state a constraint. Do
  not build a rule on a phrase list.

## Acceptance

- [ ] [run] `grep -c "Remedy direction" decaf-quality/skills/code-review/SKILL.md` — expect: ≥1, and the match sits inside the Base Context Template so every wave seat receives it
- [ ] [manual] For drifted prose the first remedy offered is deleting the claim; restating it more precisely requires a stated reason the claim must live in code
- [ ] [manual] A drafted replacement comment may not exceed what it replaces without a stated reason
- [ ] [run] `grep -l "Remedy direction" decaf-quality/agents/solo-reviewer.md` — expect: a match (the `bugs` seat carries its own brief)
- [ ] [run] `grep -l KNOWLEDGE_EXCESS decaf-quality/agents/knowledge-reviewer.md conventions/severity.md conventions/code-review-consolidation.md` — expect: all three (persona rule, severity row, consolidation alias)
- [ ] [manual] The excess rule sits below RULE 0, exempts exported-identifier docs / package docs / generated files, triggers at ~25 lines (~10 inside a function body), and routes narrative to TEMPORAL_CONTAMINATION so the two cannot both fire
- [ ] [run] Review a `~/code/nibs` changeset touching the 43-line in-body block at `cmd/list.go:327` — expect: a finding proposing deletion or a mechanism, not an expansion
- [ ] [run] Review a `~/code/nibs` changeset containing a comment the diff falsifies — expect: the fix names deletion of the claim before any rewrite
