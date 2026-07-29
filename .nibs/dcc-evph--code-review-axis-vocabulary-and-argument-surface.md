---
# dcc-evph
version: 1
title: 'code-review: axis vocabulary and argument surface'
status: completed
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:37:26Z
parent: dcc-9q01
order: a0
---

# Why

Everything else in #dcc-9q01 needs a vocabulary that exists in one place. Today the mode keyword
`low`/`mid`/`high`/`max` conflates two independent dials — the skill says so itself: *"The mode
ladder factors two independent dials — roster size and model assignment"* — and there is no way to
express the other two axes at all.

This nib is the foundation. It ships the vocabulary and the parsing; the axes themselves are
implemented in the sibling nibs.

# What to change

`decaf-quality/skills/code-review/SKILL.md`:

1. **Define the four axes in one place**, with values and defaults:

   | axis | values | controls |
   |---|---|---|
   | `roster` | integer | how many personas review |
   | `models` | low / norm / high | model policy **per role** — mechanical work stays cheap at every level |
   | `evidence` | strong / norm / any | how well-evidenced a finding must be to survive the screen |
   | `reach` | narrow / norm / wide | what counts as reportable |

   All four point the same way: less output ← `small`/`low`/`strong`/`narrow` … `large`/`high`/`any`/`wide` → more.

2. **Rename the model-tier vocabulary to `models`.** Step 2d already describes a *policy* across
   roles (judgment / volume / verification), not a single model. `models: high` means the high
   policy, not "everything on the top model". Keep the never-tier-up rule intact.

3. ~~Replace the ladder with the presets.~~ **Deferred to #dcc-rbkl**, where the presets are
   actually defined. This nib keeps the modes as the interface and re-expresses them as points in
   the axis space, so every intermediate state of the epic is a working skill. `competition/
   benchmark/tools.json` invokes `mid --report` and keeps working unchanged.

4. **Keep every axis individually overridable** for the tuning case, per the operator's decision
   that presets should not be the only way in.

# Naming — settled, do not re-litigate

Recorded in #dcc-9q01. In short: `severity` collides with finding severity, `strictness`/`level`
invert direction against the other axes, `gate` is the fourth meaning of an overloaded word,
`scope` is taken by the `[path]` argument, and `tier` implies a single model.

# Blast radius

`code-review/SKILL.md` (argument parsing, mode table, Steps 2b.5 and 2d), `decaf-quality/README.md`
item 12, `auto-code-review` and `resolve-code-review` (they pass modes through),
`competition/benchmark/tools.json`.

# Acceptance

- [x] [run] `rg -n "roster|models|evidence|reach" decaf-quality/skills/code-review/SKILL.md` —
      expect: all four axes defined in one place with values and defaults
- [x] [run] `rg -n "never tier" -A3 decaf-quality/skills/code-review/SKILL.md` — expect: the
      never-tier-up rule survives the rename to `models`
- [x] [run] `rg -rn "\b(low|mid|high|max)\b" decaf-quality/skills/*/SKILL.md decaf-quality/README.md`
      — expect: remaining hits are the alias table or the `models` values, not roster/mode meanings
- [x] [manual] A legacy `mid --report` invocation still resolves, or every caller is updated in the
      same change — the benchmark harness depends on it

## Done 2026-07-29

Shipped as a vocabulary refactor with one deliberate behavior change.

**Vocabulary.** A new `## Review axes` section defines all four axes, their values, their shared
direction, and where each is applied. `models` replaces the tier vocabulary throughout; Step 2d is
now the only place model names appear. The mode table is restated as *modes as axis settings*.
`roster=<N>` and `models=<low|norm|high>` are accepted as direct overrides alongside the `mid4`
suffix form.

**`evidence` and `reach` are defined but not settable.** Their mechanisms land in #dcc-xewu and
#dcc-jt58. The skill says so explicitly rather than accepting an argument that parses and does
nothing — a knob with no mechanism is worse than an absent one.

**Behavior change: `max`'s no-down-tiering policy is retired.** `high` and `max` now differ only in
`roster`; both use `models=high`, which keeps `quick`, `consistency` and the verification agents
down-tiered. This follows the operator's stated intent — *"we probably still want to utilize cheaper
models for mechanical tasks even on high"* — and the measurement behind it: on clustering the mid
tier matches the top tier (#dcc-xewu), and a top-tier model re-deriving a quotable convention
violation buys nothing. **A `max` run is now cheaper than it was**, which is a real change to
existing behavior and is called out in the skill.

Also touched `decaf-quality/README.md` (item 12 rewritten around the axes, examples updated).

## Summary

Shipped as a vocabulary refactor. A `## Review axes` section now defines all four axes, their
values, their shared direction (`small`/`low`/`strong`/`narrow` → less output) and where each is
applied. `models` replaces the tier vocabulary throughout, with Step 2d the only place model names
appear. Modes are restated as points in the axis space, and `roster=<N>` / `models=<...>` work as
direct overrides.

`evidence` and `reach` are defined but deliberately not settable — their mechanisms land in
#dcc-xewu and #dcc-jt58, and an argument that parses but does nothing is worse than an absent one.

Scope changed during the work: replacing the mode ladder with presets moved to #dcc-rbkl, where the
presets are actually defined. Keeping modes as the interface here means every intermediate state of
the epic is a working skill, and the benchmark's `mid --report` invocation keeps working unchanged.

One deliberate behavior change: `max`'s no-down-tiering policy is retired. `high` and `max` now
differ only in `roster`, and mechanical lanes stay cheap at every level. A `max` run is cheaper than
it was.
