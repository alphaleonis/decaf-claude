---
# dcc-fhp1
version: 1
title: Give v2 cells build and test capability
status: completed
type: task
priority: high
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T20:39:12Z
parent: dcc-ho2w
order: "7"
---

Every subject-2 cell reported the same limitation: no dotnet SDK in the container, so nothing could
be built or tested and all findings are static analysis. One run claimed sub-agents verified
reflection behaviour empirically — unverified, and not reproducible without a toolchain.

This biases the benchmark. Defects that need execution to confirm (races, memory ordering, the
`spawn_blocking` hang in subject 11) are systematically harder to catch than defects visible by
reading. It also blocks the strongest grading idea available — adjudicating a finding by whether a
patch makes a discriminating test flip — since that requires a working build.

## Scope

- Per-language toolchain for the corpus: dotnet, node/tsc, go, cargo
- Decide where it lives: base image, per-subject provisioning, or a documented prerequisite
- Network: package restore usually needs the network, which the leak controls otherwise restrict.
  Restore must be date-neutral (a lockfile or a pinned local cache), not a hole in the time-boxing
- Record in each cell's metadata whether a build/test was actually possible, so runs where it was not
  are identifiable rather than silently weaker

## Acceptance
## Acceptance

- [~] **A v2 cell can build and run the subject's test suite for at least two languages** —
      *build* verified in three (Go: `prometheus#18081` restore+build; .NET: `efcore#34127` build in
      18.5s; JS: `sveltejs/kit#15685` frozen restore in 11.3s). *Build + passing test suite* verified
      in one: Go, `ok github.com/prometheus/prometheus/util/stats`.
      Not fully met, and the reason is a finding rather than a gap in the harness: **there is no
      universal "run the tests" command.** The .NET unit-test project ran past nine minutes without
      finishing, and sveltejs/kit's vitest needs its own invocation recipe. Cells are given the
      capability and told to prefer tests covering the changed code; per-subject test recipes are
      left to [[dcc-vkeh]], where the real invocations get exercised.
- [x] **Package restore does not bypass the checkpoint time-boxing** — every subject carries a pinned
      dependency set, so the frozen variant is always available. Verified empirically on Go:
      `go mod download` under `GOFLAGS=-mod=readonly` left `go.sum` and `go.mod` untouched (0 dirty
      entries). `detect_build.sh` reports `date_neutral: false` rather than building an unpinned
      subject. All 12 subjects are date-neutral.
- [x] **Build availability recorded per cell** — `run_cell_v2.sh` writes `build-capability.json` per
      cell. 11 of 12 subjects buildable; `jellyfin#12834` is not, and says why.

## Summary

**Completed 2026-08-10** — Cells now get a working toolchain, with restore that cannot bypass the time-boxing, and a per-cell
record of what was actually possible.

**The toolchains were there all along; PATH was the problem.** `go` and `dotnet` are both installed
via mise, which activates per interactive shell — so a cell's non-interactive shell saw neither, with
a stale empty `/usr/local/go/bin` on PATH masking the real Go. Left unfixed, every cell would have
reported "no toolchain" and the benchmark would have silently measured static-analysis review only,
which is exactly the bias this nib was filed about. `v2/toolchain.sh` fixes it and is sourced before
the shim directory so the time-boxed `gh` still wins.

Three things surfaced that would each have quietly corrupted results:

- **Node is too new.** Shims do not honour a project's `.nvmrc`, so every checkout resolved to v25.9.0
  while grafana and PostHog declare `engines ">=22 <25"`. Node is now pinned corpus-wide at 24.19.0 —
  the newest satisfying all 12 — for the same reason the model and effort are held constant.
- **Having the runtime is not being able to build.** `jellyfin` pins .NET 8.0.0 with
  `rollForward=latestMinor` and cannot build under the installed SDK 10, while `efcore` pins a 9.0
  preview with `latestMajor` and can. Detection now resolves this up front instead of letting a cell
  discover it mid-run.
- **My own detector lied about an empty result** — an empty bash array printed as `[""]`, which a
  consumer would read as a non-empty missing-toolchain list. Fixed; it is the same
  empty-versus-failed confusion that has now bitten four times in this harness.

Date-neutrality holds for all 12: every subject carries a pinned dependency set, and the frozen
restore was verified to leave `go.sum`/`go.mod` untouched.

Carried forward: full test suites are expensive — one .NET project exceeded nine minutes — and
invocation is per subject, not uniform. [[dcc-vkeh]] should capture the real per-subject test recipes,
and [[dcc-3cm6]] should check whether cells actually used the capability rather than assuming it.
