I'll invoke the code-review skill as requested.
Team announcement:

```
Review team (preset `review` — explicit · roster uncapped (derived: ~800 executable lines, >400) · models=norm · evidence=norm · reach=norm):
- quick-reviewer (always) — mid tier
- broad-reviewer (always) — mid tier
- knowledge-reviewer — substantive change embedding non-obvious reconstruction/billing decisions — session model
- consistency-reviewer — substantive change with rich sibling code (other flag endpoints, other Rust handler params) — session model? no: mid tier
- design-reviewer — new public REST endpoint, new serializers, new Rust request/response contract fields — session model
- security-reviewer — new bearer-token internal auth path, billing bypass, caller-supplied flag-definition override, new POST endpoint — session model
- adversarial-reviewer — ~800 executable lines, touches auth + billing + data mutation-adjacent surface — session model
- performance-reviewer — new ClickHouse queries, activity-log scan, per-flag property re-merge in evaluation loop — mid tier
- test-reviewer — test files present (hard gate met) — mid tier
- rust-reviewer — Rust files present (hard gate met) + idiom surface (async, error swallowing via .ok()/unwrap_or, panic paths, serde boundary trust) — mid tier
- spec-compliance-reviewer: skipped — no spec available (hard gate)
- data-migration-reviewer: skipped — no migration artifacts in diff (hard gate)
- dotnet/typescript/cpp/go-reviewer: skipped — no C#/TS/C++/Go files in changeset (hard gate)
- prior-feedback-reviewer: skipped — not a PR with prior review threads (hard gate)
```

Pre-flight: `cargo`, `ruff`, and a working `uv` are all unavailable in this environment (`uv run` fails on a version pin mismatch), so no build/lint/test gate could run. Only `python3 -m py_compile` on the five changed Python files succeeded.
API Error: 529 Overloaded. This is a server-side issue, usually temporary — try again in a moment. If it persists, check https://status.claude.com.

