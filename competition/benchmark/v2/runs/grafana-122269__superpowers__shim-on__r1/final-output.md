Reviewer subagent report, verbatim:

---

### Strengths

- **Backward compatibility is genuinely preserved on the default path.** `conf/defaults.ini:1899` ships `proxy_token = ""`, so `ResolveGrafanaComProxyAPIToken` (`pkg/setting/setting.go:762`) always falls through to `cfg.GrafanaComSSOAPIToken`. Existing deployments that set only `sso_api_token` see byte-identical behavior on both the gnet proxy (`pkg/api/grafana_com_proxy.go:54`) and plugin management (`pkg/services/pluginsintegration/pluginconfig/config.go:39`).
- **Secret redaction was not forgotten.** `pkg/setting/setting.go:831` adds `PROXY_TOKEN$` to the `RedactedValue` pattern list, with a covering case at `pkg/setting/setting_test.go:662`. This is the kind of thing that routinely ships broken and then leaks into `LogConfigSources` output; good catch by the author.
- **Tests exercise real flag evaluation, not a mock.** `TestResolveGrafanaComProxyAPIToken` (`pkg/setting/setting_test.go:387`) drives a real `memprovider.NewInMemoryProvider` through the actual OpenFeature default client and covers all three meaningful states (flag off + token set, flag on + token set, flag on + token unset). I ran it: `go test ./pkg/setting/... -run 'TestResolveGrafanaComProxyAPIToken|TestRedactedValue|Test_readGrafanaComSettings'` → `ok`.
- **Generated toggle artifacts are consistent with the registry.** I ran `go test ./pkg/services/featuremgmt/ -run 'TestFeatureToggleFiles|TestRegistry'` → `ok`, so `toggles_gen.{go,csv,json}` match what `make gen-feature-toggles` would produce.
- **Init ordering is correct at both entrypoints.** `cfg.ResolveGrafanaComProxyAPIToken()` sits after `featuremgmt.InitOpenFeatureWithCfg(cfg)` and before `server.Initialize` / `server.InitializeModuleServer` in `pkg/cmd/grafana-server/commands/cli.go:113` and `pkg/cmd/grafana-server/commands/target.go:99`. Since `InitOpenFeatureWithCfg` uses `SetProviderAndWait`, the remote-provider case is ready before evaluation.
- **The security direction is right.** Moving the user-facing `/api/gnet` proxy off the SSO token (which `pkg/services/auth/gcomsso/gcom_logout_hook.go:50` and `pkg/storage/unified/sql/backend.go:57` still use for identity purposes) onto a narrower plugin-scoped token is a real blast-radius reduction.
- Build is clean across all touched packages (`go build ./pkg/cmd/... ./pkg/api/... ./pkg/services/pluginsintegration/...`) and `go test ./pkg/cmd/grafana-cli/... -short` passes.

---

### Issues

#### Critical (Must Fix)

None. There is no path where an existing, currently-working configuration regresses.

#### Important (Should Fix)

**1. The feature flag does not guard the grafana-cli path — the plan's flag requirement is only half-implemented.**
`pkg/cmd/grafana-cli/utils/command_line.go:111-122`

```go
func (c *ContextCommandLine) GrafanaComProxyAPIToken() string {
	cfg, err := c.Config()
	if err != nil { ... }
	if cfg.GrafanaComProxyAPIToken != "" {
		return cfg.GrafanaComProxyAPIToken
	}
	return cfg.GrafanaComSSOAPIToken
}
```

There is no flag check here, and OpenFeature is never initialized in the `grafana-cli plugins install` path (`runPluginCommand` bypasses server DI entirely). So the moment an operator writes `proxy_token` into their config, `grafana-cli plugins install` starts authenticating with the dedicated token **regardless of whether `grafana.dedicatedGrafanaComProxyAPIToken` is enabled**, while the server keeps using the SSO token.

Why it matters: the whole point of the flag is to let operators stage the config change before flipping behavior. If the dedicated token is provisioned with the wrong scopes, CLI installs break while the operator believes the feature is off — and the failure surfaces in a completely different component from the one they touched. It also makes the two halves of the same feature disagree about which token is in use.

This looks like a deliberate workaround (the CLI genuinely has no feature-flag infrastructure), but it is a deviation from the stated plan and should be confirmed as intentional. If it is intentional, it needs to be documented; see issue 4. If not, the CLI needs either its own OpenFeature init or an explicit decision that `proxy_token` is unconditional for the CLI.

**2. The flag is evaluated exactly once at startup, but is not marked `RequiresRestart`.**
`pkg/services/featuremgmt/registry.go:2252-2259`, `pkg/setting/setting.go:762`

`ResolveGrafanaComProxyAPIToken` collapses the flag into a single field mutation at boot, and destructively overwrites `cfg.GrafanaComProxyAPIToken` with the SSO token when the flag is off. Grafana supports remote/dynamic OpenFeature providers (`createRemoteProvider` in `pkg/services/featuremgmt/openfeature.go` builds an OFREP provider with a cache TTL), so this flag *looks* runtime-flippable to whoever operates it, but flipping it does nothing until a restart — and once resolved off, the configured dedicated token is gone from the field entirely.

`RequiresRestart: true` is an established convention in this registry (51 occurrences of the field, e.g. lines 116, 214, 222). Add it to the new entry so the toggle UI and generated docs tell the truth.

**3. Resolution is wired per-entrypoint rather than at config construction, and one existing entrypoint already misses it.**
`pkg/cmd/grafana-server/commands/cli.go:113`, `pkg/cmd/grafana-server/commands/target.go:99` vs. `pkg/tests/testinfra/testinfra.go:124`

`server.InitializeForTest` (wire_gen.go:1073) calls `pluginconfig.ProvidePluginManagementConfig`, which now reads `cfg.GrafanaComProxyAPIToken` — but `testinfra.go` initializes OpenFeature at line 124 and never calls `ResolveGrafanaComProxyAPIToken`. Same for `pkg/services/pluginsintegration/test_helper.go:45`. In those paths a `sso_api_token` configured via `testinfra.GrafanaOpts.GrafanaComSSOAPIToken` (testinfra.go:699-702) now yields an **empty** token instead of the SSO token, and the failure is silent — `ReverseProxyGnetReq` simply omits the `Authorization` header when the token is empty (`pkg/api/grafana_com_proxy.go:44`).

No integration test currently exercises this (I checked: nothing in `pkg/tests/` sets `GrafanaComSSOAPIToken` or hits `/api/gnet`), so today it is latent rather than broken. But it demonstrates the structural problem: any caller that builds a `Cfg` and a server without knowing about this one extra method silently loses the token. The safer shape is to resolve at the point of consumption (`ProvidePluginManagementConfig` and `ProxyGnetRequest` both already have access to feature toggles) or inside `Cfg.Load`, so it cannot be forgotten. At minimum, add the call to `testinfra.go` and `test_helper.go` so test and production topology agree.

**4. Documented feature-toggle name is wrong — users cannot enable the feature by following the docs.**
`docs/sources/setup-grafana/configure-grafana/_index.md:2325`

> Requires the `dedicatedGrafanaComProxyAPIToken` [feature toggle] ... to be enabled.

The registered name is `grafana.dedicatedGrafanaComProxyAPIToken` (`pkg/services/featuremgmt/registry.go:2253`). Dotted names are used verbatim in `[feature_toggles] enable = ...`, so the documented name will simply not match anything. This is almost certainly fallout from the rename in the last commit of the branch.

The same sentence is also inaccurate for `grafana-cli`, which honors `proxy_token` without the toggle (issue 1). And the doc never mentions the `sso_api_token` fallback, which is the single most important thing an operator needs to know about this key.

**5. Test coverage misses the two production consumption paths.**

- `pkg/cmd/grafana-cli/commands/install_command_test.go:103` still asserts `c.GcomToken()` — a method that no longer participates in plugin installs after `install_command.go:102` switched to `c.GrafanaComProxyAPIToken()`. The integration test now validates dead code, and nothing covers the CLI's new fallback logic. `testinfra.GrafanaOpts` has no `proxy_token` option (testinfra.go:960), so this case isn't even expressible today.
- Nothing asserts that `ProvidePluginManagementConfig` or `ProxyGnetRequest` carry the resolved token. `pkg/api` has no `grafana_com_proxy_test.go` at all (pre-existing), but `ProvidePluginManagementConfig` is trivially testable and the field swap at `pluginconfig/config.go:39` is exactly the kind of one-line change a future refactor could silently revert.

#### Minor (Nice to Have)

**6. `GcomToken()` is now dead in production but retained in three places.**
`pkg/cmd/grafana-cli/utils/command_line.go:29,101`, `command_line_mock.go:149`, `upgrade_command_test.go:133`. Its only remaining caller is a test. Two nearly-identical methods on the same interface with subtly different semantics is a trap for the next person. Either delete it or add a comment stating it is retained only for X.

**7. The flag name is a hardcoded string literal in `pkg/setting`.**
`pkg/setting/setting.go:763` cannot use `featuremgmt.FlagGrafanaDedicatedGrafanaComProxyAPIToken` because `featuremgmt` imports `setting`. The risk is not theoretical: this branch renamed the flag three times (`pluginsDedicatedInstallToken` → `dedicatedGnetProxyToken` → `dedicatedGrafanaComProxyToken` → `dedicatedGrafanaComProxyAPIToken` → `grafana.dedicatedGrafanaComProxyAPIToken`), and a registry-only rename would leave this literal silently evaluating a nonexistent flag (which returns the `false` default — indistinguishable from "flag off"). Moving the resolution out of `pkg/setting` (see issue 3) would fix this as a side effect; otherwise add a comment on both sides pinning them together.

**8. `conf/sample.ini` was not updated.** `conf/sample.ini:1815-1819` documents `[grafana_com] sso_api_token` with an explanatory comment but has no `proxy_token` entry. `defaults.ini` gained the key without a comment. Grafana convention is to keep both in sync.

**9. New `grafana_com` test placed in the plugins settings test file.** `pkg/setting/setting_plugins_test.go:284` defines `Test_readGrafanaComSettings_GrafanaComProxyAPIToken` in a file otherwise devoted to `[plugins]`. Residue from the abandoned `[plugins] install_token` design. Also, it only covers the env-var path, not the ini-key path.

**10. `toggles_gen.json` carries three tombstones for names that never existed on `main`.** `pkg/services/featuremgmt/toggles_gen.json` gains `pluginsDedicatedInstallToken`, `dedicatedGnetProxyToken`, `dedicatedGrafanaComProxyToken` and `dedicatedGrafanaComProxyAPIToken`, each with a `deletionTimestamp`, because the generator derives history from the branch's commit log. Generated output, so arguably out of scope, but it permanently records four phantom flags in a tracked file. Worth a squash of the toggle-rename commits if that's cheap.

**11. Docs use a `relref` shortcode against local style, with a likely-wrong anchor.**
`docs/sources/setup-grafana/configure-grafana/_index.md:2325` is the *only* `relref` in this ~3000-line file, and `docs/AGENTS.md:110` says "Use inline Markdown links". Additionally, the sibling cross-reference at line 2309 renders `### [grafana_com]` as `#grafana-com` (underscore → dash), which suggests `#feature_toggles` should be `#feature-toggles`. [Inference — I could not build the docs site to confirm the anchor generation rule.]

**12. `command_line_mock.go` is a mockery `DO NOT EDIT` file that was hand-edited.** The added block at line 162 lacks the `// X provides a mock function with given fields:` comment mockery emits. It is consistent with the existing hand-edited `GcomToken` block above it, so this is pre-existing drift rather than new — but regenerating the mock will now produce a diff.

---

### Recommendations

1. **Resolve at consumption, not by mutating `Cfg`.** Both consumers (`ProvidePluginManagementConfig` and `HTTPServer.ProxyGnetRequest`) already have access to feature toggles. A small helper — `func GrafanaComProxyToken(cfg *setting.Cfg, features ...) string` living in `pluginconfig` or `featuremgmt` — would (a) let the flag be evaluated per-request so it is genuinely dynamic, (b) allow the typed `Flag...` constant instead of a string literal, (c) remove the "must remember to call this method" contract that `testinfra` already violates, and (d) preserve the configured `proxy_token` value instead of overwriting it.
2. **Decide and document the CLI's relationship to the flag.** Either wire OpenFeature into the CLI or state explicitly, in both the doc and a code comment on `GrafanaComProxyAPIToken()`, that the CLI honors `proxy_token` unconditionally. Silently differing behavior between server and CLI for the same config key is the worst of the three options.
3. **Rewrite the doc entry** to name the toggle correctly (`grafana.dedicatedGrafanaComProxyAPIToken`), state the `sso_api_token` fallback, and describe the CLI's actual behavior.
4. **Add `RequiresRestart: true`** to the registry entry as long as the value stays resolved-once-at-boot.
5. **Backfill the two consumption tests** (CLI fallback via `ContextCommandLine`, and `ProvidePluginManagementConfig` passing the resolved token through), and retarget `install_command_test.go:103` off the dead `GcomToken()`.

---

### Assessment

**Ready to merge?** With fixes.

**Reasoning:** The core mechanism is sound, tested, backward-compatible on the default path, and the generated artifacts verify clean — but the feature flag only guards half the feature (the server, not `grafana-cli`), the documented toggle name is wrong so nobody can actually enable it, and the resolution is a per-entrypoint side effect that one existing server-initialization path (`InitializeForTest`) already misses. Items 1, 2 and 4 should land before merge; item 3 can be a follow-up if the test-only impact is accepted knowingly.
