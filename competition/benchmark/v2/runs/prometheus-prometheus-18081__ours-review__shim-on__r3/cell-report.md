I'll start by invoking the requested skill.
I'll start by gathering context on the change.
Pre-flight gates pass. Now the review team.

**Review team** (preset `review` — explicit · roster uncapped (derived: ~1390 executable lines) · models=norm · evidence=norm · reach=norm):
- `quick-reviewer` (always) — mid tier
- `broad-reviewer` (always) — mid tier
- `knowledge-reviewer` — new stats semantics embed non-obvious attribution decisions — session model
- `consistency-reviewer` — new `SamplesRead*` API mirrors existing `TotalSamples*` API; symmetry is checkable — mid tier
- `design-reviewer` — new public JSON fields, new exported stats methods, new engine metric — session model
- `adversarial-reviewer` — ≥50 executable lines; subquery/step attribution composes across evaluators — session model
- `performance-reviewer` — `countSamplesAfter` runs per-step in the range-eval hot loop — mid tier
- `test-reviewer` — 1131 added test lines (hard gate) — mid tier
- `go-reviewer` — Go files (hard gate) + idiom surface: slice indexing, nil receivers, shared `samplesStats` aliasing — mid tier
- `security-reviewer`: skipped — no trust-boundary trigger in the diff (no new parsing, auth, crypto, secrets, or path building)
- `spec-compliance-reviewer`: skipped — no spec available (hard gate)
- `data-migration-reviewer`: skipped — no migration artifacts (hard gate)
- `dotnet`/`typescript`/`cpp`/`rust`-reviewer: skipped — no such files (hard gate)
- `prior-feedback-reviewer`: skipped — local diff, no PR threads (hard gate)
Tree is clean. Now running the nominated probes — in isolated worktrees so the review tree is never touched.
Now I'll write a self-contained probe that runs identically at BASE and HEAD.
P1, P2 and P3 confirmed at BASE vs HEAD. Now probing the adversarial-reviewer's allocation claim.
Probes confirmed the major claims. Two more verifications before consolidating.
Confirmed and reproducible (+30% on plain `rate()` with stats disabled). Cleaning up probe worktrees.
All probes run and the tree is verified clean. Writing the consolidated report.

