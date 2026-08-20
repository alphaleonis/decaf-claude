---
# dcc-9vta
version: 1
title: detect_build.sh misses nested Rust workspaces — build_possible:true for a subject whose majority language has no toolchain
status: completed
type: bug
created_at: 2026-08-20T13:40:48Z
updated_at: 2026-08-20T19:48:15Z
parent: dcc-ho2w
order: zzs
---

`detect_build.sh` detects Rust only at the repository root:

```sh
# detect_build.sh:116
if [ -f "$R/Cargo.lock" ]; then
  langs+=("rust"); managers+=("cargo"); ...
```

Go, in the same script, is nested-aware:

```sh
# detect_build.sh:66
gosum="$(find "$R" -maxdepth 3 -name go.sum 2>/dev/null | head -1)"
```

So a monorepo whose Rust lives in a subdirectory workspace is reported as having no Rust at all.

## Observed on PostHog-posthog-55149 ([[dcc-fm7x]])

- Root `Cargo.lock`: **absent**. Nested: `rust/Cargo.lock`, `cli/Cargo.lock`, `funnel-udf/Cargo.lock`.
- **13 of the 18 changed files are under `rust/`** — the majority of the subject.
- Every cell recorded `languages: [js, go, python]`, `missing_toolchains: []`, `build_possible: true`,
  and an empty `detect_build.stderr`. Self-consistent, and wrong in effect.
- `cargo` is **not installed on this machine**, so correct detection would have reported
  `missing_toolchains: ["cargo"]` and a truthful `build_possible`.

## Why it matters beyond a wrong field

The cell prompt tells every reviewer: *"A build toolchain IS available (node, go, dotnet, python,
cargo as the project requires). You may build the project and run its tests to confirm or refute a
finding."* On this subject that sentence was false for the majority language. Two `ours-bugs` cells
independently reported working around it — one recording all 13 of its findings as `traced` or `read`
with 7 below full confidence, the other flagging 8 of 16 as static traces rather than builds.

This does not bias the comparison — every arm faced the same environment — but it silently changes
what the subject measures: static reasoning, not verified reasoning, across 13 of 18 files. A subject
can be selected partly *because* `build_possible: true`, as this one was, on a claim that does not
hold. That is the harness's recurring shape: a green field that is indistinguishable from a real one.

## Fix

- Make Rust detection nested-aware, matching the Go idiom (`find -maxdepth 3 -name Cargo.lock`).
  Consider whether js (`detect_build.sh:45`) and python (`:105`) need the same treatment — both are
  root-only today.
- Where a language IS detected but its toolchain is absent, the cell prompt must not claim that
  toolchain is available. Either provision it or state the gap to the reviewer.
- `audit_subject.sh` / subject selection should surface "majority-language toolchain missing" rather
  than a bare `build_possible`.

## Acceptance

- [ ] A repo with only a nested `Cargo.lock` reports `rust` in `languages`
- [ ] With `cargo` absent, that subject reports it in `missing_toolchains` and `build_possible` reflects it
- [ ] The cell prompt's toolchain sentence is derived from `build-capability.json`, not hardcoded
- [ ] PostHog-posthog-55149's `build-capability.json` re-derived and the [[dcc-fm7x]] write-up carries
      the static-reasoning caveat for its Rust half

## Downstream evidence: the missing toolchain also caused a tool-side silent failure

`ours-review` r1 on this subject self-reported that a backgrounded `cargo check` was recorded as
**"completed (exit code 0)"** while its actual output was `cargo: No such file or directory`. The
tool surfaced the discrepancy itself, so it did not stay silent — but the same run left 14 nominated
probes unexecuted and its pre-flight gates at `partial` (no venv, no Rust toolchain, no ruff).

Two independent layers therefore turned an absent toolchain into a success-shaped signal: this
script's `build_possible: true`, and a backgrounded command's exit code. Fixing detection removes the
first and makes the second visible before a reviewer wastes probes on it.

## Broader than nested detection: `build_possible` is never validated

Two arms independently report that **`uv sync --frozen` fails** on this subject — `ours-bugs` r1
("refused") and `ours-review` r2 ("fails on a version mismatch"). `uv` IS installed and `uv.lock` IS
present, so `detect_build.sh:105-110` records python as buildable and `build_possible: true` follows.
The command still does not work.

So the field is a **static inference from lockfile presence plus binary presence**, never a
validation. Nested Rust detection is one way it goes wrong; a lockfile the installed tool cannot
resolve is another, and the acceptance item "derive the prompt sentence from `build-capability.json`"
does NOT fix this one — a corrected capability file would still claim python.

Measured consequence on this subject: `ours-review` r2 left **all 9** nominated probes unrun and
recorded pre-flight gates as PARTIAL; `ours-review` r1 left 14 unrun. No arm executed a probe. The
subject was selected partly because `build_possible: true`, and no arm could build anything.

Additional acceptance:

- [ ] `build_possible` reflects a restore that was actually ATTEMPTED once at fixture-build time
      (per language), with the failure recorded, not inferred from file presence
- [ ] A subject whose restore fails is either fixed or labeled static-reasoning-only before cells run

## Summary

**Completed 2026-08-20** — Rust detection is nested-aware (`find -maxdepth 3 -name Cargo.lock`, matching the Go idiom), and js
and python got the same treatment — the nib asked whether they needed it and they did; all three were
root-only in a corpus full of monorepos. Root still wins when both exist, since a root lockfile
governs the workspace.

PostHog-55149 now reports `languages:[js,go,python,rust]`, `missing_toolchains:["cargo"]`,
`build_possible:false` — where it previously reported a clean build for a subject whose majority
language had no toolchain.

The cell prompt's toolchain paragraph is now generated from `build-capability.json` by a new
`build_note.py`, with three distinct states: complete, partial (naming the missing languages and
telling the reviewer to mark those findings as static), and detection-failed. The partial text also
warns not to trust a command's exit status without reading its output — a cell recorded a
backgrounded `cargo check` as exit 0 while cargo did not exist. Tested in `test_build_note.py`.

Not done: re-deriving PostHog-55149's `build-capability.json` inside its recorded cells. Those cells
are already run; the caveat belongs in the write-up dcc-tvk8 still owes.
