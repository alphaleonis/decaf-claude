---
# dcc-fhp1
version: 1
title: Give v2 cells build and test capability
status: todo
type: task
priority: high
created_at: 2026-08-10T17:43:02Z
updated_at: 2026-08-10T17:43:41Z
parent: dcc-ho2w
order: Z
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

- [ ] A v2 cell can build and run the subject's test suite for at least two languages
- [ ] Package restore does not bypass the checkpoint time-boxing
- [ ] Build availability recorded per cell
