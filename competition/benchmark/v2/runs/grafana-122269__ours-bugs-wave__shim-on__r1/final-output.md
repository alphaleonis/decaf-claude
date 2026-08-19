✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_16-39-07.md`

No prior reviews exist, so the Recurring Findings scan was skipped. Working tree unmodified — `git status` shows only the untracked `.decaf/` report.

## Verdict: ❌ NEEDS_CHANGES

**#1 🟠 High — `pkg/cmd/grafana-cli/utils/command_line.go:111`: the CLI half is ungated.**
`ContextCommandLine.GrafanaComProxyAPIToken()` prefers `proxy_token` without ever checking the `grafana.dedicatedGrafanaComProxyAPIToken` flag, while the server's `Cfg.ResolveGrafanaComProxyAPIToken()` does. With the flag at its default OFF and `proxy_token` set, the server sends `sso_api_token` and `grafana-cli plugins install` sends `proxy_token` — from the same config file. The flag isn't a kill switch for the CLI, and a staged rollout breaks container plugin installs while the catalog UI keeps working. Found independently by all three general reviewers; validator confirmed the CLI entry point never initializes OpenFeature.

**#2 🟡 Medium — `docs/.../_index.md:2325`: documented toggle name is missing the `grafana.` prefix.**
Docs say `dedicatedGrafanaComProxyAPIToken`; the flag registered in the same commit is `grafana.dedicatedGrafanaComProxyAPIToken`. Toggle names match literally — no normalization exists anywhere — and unknown names raise no error. An operator following the docs enables an inert flag and sees the new `proxy_token` setting do nothing, with no diagnostic. The commit message shows the rename landed after the docs line was written.

## Worth knowing about the preset

`bugs` runs `evidence=strong`, which needs ≥80 from a lone finder. Two real findings scored below that and were tiered down to Minor rather than reported as primary:

- **`pkg/api/grafana_com_proxy.go:54` (screen 72)** — the token swap covers all of `/api/gnet/*`, not just plugin paths. Community dashboard import and the template gallery ride on it too, while the docs describe `proxy_token` as plugin-only, so operators will provision a narrower credential than the code needs. This would have been a **primary High** at the default `review` preset.
- **`pkg/setting/setting.go:762` (screen 55)** — `Resolve` is a self-overwriting read-then-write: it destroys the configured value, swallows OpenFeature evaluation errors as "flag off", and logs nothing about which credential ended up active.

Also promoted from a reviewer's dismissed items and verified: `GcomToken()` is now a dead contract with zero production callers, and `install_command_test.go:103` still asserts on it — so the only CLI-level token test no longer guards the path that actually runs.

Two coverage trades the `roster` cap of 4 forced, both relevant here: `go-reviewer` (hard gate matched, Go is the entire diff) and `security-reviewer` (credential handling). Re-running as `review` or `bugs roster=6` would buy those back and promote the two tiered-down findings.
