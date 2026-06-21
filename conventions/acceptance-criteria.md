# Acceptance Criteria — the `## Acceptance` section

How to write the `## Acceptance` section that goes in a work-item body (spec, phase, or
feature). This is the **ground truth** an autonomous run verifies against: an unattended
loop has no human checkpoint to catch drift, so acceptance criteria are the only thing that
says "this phase is actually done." Write them so a machine can check as many as possible.

Acceptance lives in the **work-item body** (not a side file), so it travels across every
tracker via the adapter `read` op (see [work-items.md](work-items.md)).

## The A+C hybrid format

Each criterion is a checklist item tagged either `[run]` (runnable) or `[manual]`:

```
## Acceptance

- [ ] [run] `<command>` — expect: <observable result>
- [ ] [manual] <prose criterion that cannot be mechanically checked>
```

- **`[run]`** — a deterministic check. The command goes in backticks (so shell metacharacters like `>` are safe); `— expect:` introduces the observable pass condition (exit status, matched output, a value). The verify step runs the command and compares.
- **`[manual]`** — a prose criterion that can't be run (visual/UX, external service, judgement). It is **subagent-verified** (an agent inspects code/output and judges), flagged **lower-confidence**, and **held for human confirmation** — it must **never block the loop forever**: the loop surfaces unmet/unverified manual criteria and proceeds.

### Rules

1. **Prefer `[run]`.** If a criterion *can* be expressed as a command + expected result, write it that way — a robot can run a command and diff output; it can't verify a narrative.
2. **Tag honestly.** Mark `[manual]` only when there is genuinely no runnable form. Don't dress prose up as runnable.
3. **One observable per item.** Each item checks one thing, so a failure points at one gap.
4. **Self-contained commands.** Prefer commands runnable from the repo root with the project's standard toolchain (test runner, build, linter, a curl against a known local endpoint). State any required setup in the command itself.
5. **Cover the slice's external behavior**, not implementation detail — the same bar as a good test (test what the feature does, not how).

### Example

```
## Acceptance

- [ ] [run] `dotnet test --filter Category=Auth` — expect: exit 0, all auth tests pass
- [ ] [run] `curl -s localhost:8080/health` — expect: body is `{"status":"ok"}`
- [ ] [run] `rg -n "TODO|FIXME" src/auth/` — expect: no output
- [ ] [manual] The password-reset email renders correctly in Outlook and Gmail
- [ ] [manual] The login screen matches the agreed design mock
```

## Who emits it

- **`draft-spec`** — emit `## Acceptance` for the spec/feature: the top-level behaviors that mean "this is built," runnable where possible.
- **`draft-plan`** — give **each phase** work item a `## Acceptance` section: what makes *that phase* shippable.
- **`breakdown-phase`** — give **each feature** a `## Acceptance` section: the concrete done-check for that unit.

## Who reads it

The `auto-deliver` verify step reads `## Acceptance` (via the adapter `read` op), runs every
`[run]` item, dispatches focused fixes for failures (fix-now, in-scope), and surfaces
`[manual]` items for human confirmation without blocking.
