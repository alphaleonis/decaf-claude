---
# dcc-evph
version: 1
title: 'code-review: axis vocabulary and argument surface'
status: todo
type: feature
priority: high
estimate: m
tags:
    - code-review
created_at: 2026-07-29T18:29:16Z
updated_at: 2026-07-29T18:30:12Z
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

3. **Replace the `low`/`mid`/`high`/`max` ladder with the presets** (defined in #dcc-rbkl). `max`
   has no natural home among the three — it becomes `audit` with everything on the session model.
   Accept the legacy keywords as aliases for one release so existing invocations do not break;
   `competition/benchmark/tools.json` invokes `mid --report` and would otherwise fail.

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

- [ ] [run] `rg -n "roster|models|evidence|reach" decaf-quality/skills/code-review/SKILL.md` —
      expect: all four axes defined in one place with values and defaults
- [ ] [run] `rg -n "never tier" -A3 decaf-quality/skills/code-review/SKILL.md` — expect: the
      never-tier-up rule survives the rename to `models`
- [ ] [run] `rg -rn "\b(low|mid|high|max)\b" decaf-quality/skills/*/SKILL.md decaf-quality/README.md`
      — expect: remaining hits are the alias table or the `models` values, not roster/mode meanings
- [ ] [manual] A legacy `mid --report` invocation still resolves, or every caller is updated in the
      same change — the benchmark harness depends on it
