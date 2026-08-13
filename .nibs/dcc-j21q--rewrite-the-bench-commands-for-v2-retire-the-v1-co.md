---
# dcc-j21q
version: 1
title: Rewrite the bench-* commands for v2; retire the v1 command surface
status: completed
type: task
priority: high
created_at: 2026-08-13T09:09:30Z
updated_at: 2026-08-13T09:14:08Z
parent: dcc-ho2w
order: zV
---

## Description

[Describe what needs to be done]

## Verification

- [ ] [How to verify the work is complete]


## Done 2026-08-13

Five of six bench-* commands drove v1. Only `bench-analyze-v2` was current, which left v2 with
sixteen shell scripts and seven Python modules and no command surface at all — the whole pilot was
hand-driven, including re-deriving the same status query four times.

Worse than stale docs: **only 1 of the 12 v1 scripts carried the `BENCH_V1_ALLOW` guard.**
`/bench-status` invoked `bench_status.sh` directly, which had none, so a banner on the command was
the only thing between an operator and a number that may never be cited. A banner is not a control.

Operator chose: delete the v1 commands, v2 takes the plain names.

| Command | Now |
|---|---|
| `/bench-analyze` | v2 — was `bench-analyze-v2`; the `-v2` suffix is gone, and the same-bare-name hazard with it |
| `/bench-status` | v2 — new `v2/status.sh`; reports per subject x repeat and names every INELIGIBLE cell with which of the four failures applies |
| `/bench-run` | v2 — drives `run_cell_v2.sh` / `run_pilot.sh`, carrying the pre-flight discipline that was hand-applied every time: tmpfs floor, clean checkout, detached launch, same-subject serialization, resume-on-`is_error` |
| `/bench-synthesize` | v2 — drives `aggregate_pilot.py` and the established page format; updates the existing artifact rather than minting a new one |
| `/bench-init` | v2 — rebuild gitignored checkouts from committed fixtures, verify byte-identity against the fixture, run both scoring test suites, check the toolchain |

`v2/status.sh` distinguishes the four ineligibility reasons rather than collapsing them, because each
has a different remedy: a probe cell (r0) is never scored by convention, an empty output is a crash,
an `api <code>` is a limit to wait out and not a harness bug, and an isolation state that is not CLEAN
must be read before anything else. Its first version marked the seven r0 probe cells as *eligible* —
exactly how a probe would end up in a pooled analysis — and was fixed before the command shipped.

The guard now covers 11 of 12 v1 scripts (`lib.sh` is sourced, not an entry point, and guarding it
would double-fire). Verified by running: refuses at exit 3 by default, and `BENCH_V1_ALLOW=1` still
serves the legitimate archival case.

One substantive catch while wiring: `scoring/README.md` justifies its empty-severity guard by saying
`/bench-synthesize` reads tool-reported severity for a calibration axis. The rewrite had dropped that
axis, which would have left the guard unjustified. It is back in the command — with the caveat the
pilot found, that at least one tool emits no severities of its own on some runs, so a calibration
figure over those cells measures the extractor rather than the tool.

## Summary

**Completed 2026-08-13** — Rewrote the bench-* command surface for v2 and retired v1's. The five v1 commands are deleted and v2
takes the plain names; bench-analyze-v2 loses its suffix. New v2/status.sh backs /bench-status.
Every v1 entry point now refuses without BENCH_V1_ALLOW (11 of 12 scripts had no guard at all,
including the one /bench-status invoked directly). Verified by running both paths.
