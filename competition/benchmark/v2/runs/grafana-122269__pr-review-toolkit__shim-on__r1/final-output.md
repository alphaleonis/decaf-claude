`InitializeForCLI` does **not** wire `ProvidePluginManagementConfig` (verified at `pkg/server/wire_gen.go:1721`), so the `grafana-cli` runner path one agent flagged is not affected — dropping that claim. Working tree remained clean throughout; no files were modified.

---

# PR Review Summary — "Auth: Use dedicated token for requests to Grafana.com" (`b262acdd..ccdf7327`)

**Scope:** 17 files, +223/−14. Adds `[grafana_com] proxy_token` (`GF_GRAFANA_COM_PROXY_TOKEN`), resolved at startup behind the new experimental toggle `grafana.dedicatedGrafanaComProxyAPIToken`, falling back to the existing `sso_api_token`. Consumers: the `/api/gnet` reverse proxy, server-side plugin repo requests, and `grafana-cli plugins install`.

**Verification performed:** `go build` of all changed packages succeeds; `go test ./pkg/setting/...` passes (also under `-race -shuffle=on`); `TestFeatureToggleFiles` passes, so the generated toggle files match `make gen-feature-toggles`.

---

## Critical (3)

**1. `grafana-cli` ignores the feature toggle, contradicting the docs shipped in the same commit**
`pkg/cmd/grafana-cli/utils/command_line.go:111-122`

```go
if cfg.GrafanaComProxyAPIToken != "" {
    return cfg.GrafanaComProxyAPIToken
}
return cfg.GrafanaComSSOAPIToken
```

No toggle check. `install_command.go:102` now routes plugin installs through this, so `proxy_token` takes effect for `grafana-cli plugins install` **whenever it is set**, toggle off or absent. The docs at `docs/sources/setup-grafana/configure-grafana/_index.md:2325` state the opposite: *"plugin installs via `grafana-cli` … Requires the `dedicatedGrafanaComProxyAPIToken` feature toggle to be enabled."*

This is structural, not a dropped line: `grafana-cli` never calls `featuremgmt.InitOpenFeatureWithCfg` (only callers are `cli.go:110`, `target.go:96`, `testinfra.go:124`), so adding an OpenFeature check there would evaluate against `NoopProvider` and make the dedicated token permanently unreachable from the CLI. The experimental gate provides no rollback lever for the CLI path in either direction. **Decide one behavior and document it.**

**2. The documented toggle name is missing its `grafana.` prefix, and a wrong name is silently accepted**
`docs/sources/setup-grafana/configure-grafana/_index.md:2325`

Registered name is `grafana.dedicatedGrafanaComProxyAPIToken` (`pkg/services/featuremgmt/registry.go:2253`, `toggles_gen.go:727`), and `setting.go:763` looks up that exact string. Flags are keyed verbatim — `ReadFeatureTogglesFromInitFile` (`pkg/setting/setting_feature_toggles.go:151-175`) copies any `[feature_toggles]` key into the map with **no registry validation**. An operator following the docs writes `dedicatedGrafanaComProxyAPIToken = true`, Grafana starts clean, the real key resolves to `false`, and `proxy_token` is silently discarded at `setting.go:766`. No log, no warning. Only 4 of ~600 flags carry a prefix, so a reader has no reason to suspect one.

Related, verified: dotted flag names **cannot** be enabled via `--configOverrides cfg:feature_toggles.<name>=true` — `pkg/setting/setting_feature_toggles.go:107-109` explicitly `continue`s on any key containing a `.`. Worth knowing before planning the rollout.

**3. Integration-test harness never resolves the token — `sso_api_token` stops reaching both consumers**
`pkg/tests/testinfra/testinfra.go:124`

`testinfra` mirrors `cli.go:110-115` exactly *minus* the new line: it calls `InitOpenFeatureWithCfg(cfg)` then `server.InitializeForTest` at `:144`, which wires `ProvidePluginManagementConfig` (`pkg/server/wire_gen.go:1073` → `pluginconfig/config.go:39`). So every integration-test server runs with the raw, unresolved field — `""` by default. The `GrafanaOpts.GrafanaComSSOAPIToken` option written to ini at `testinfra.go:699-702` no longer reaches the proxy or plugin repo, where before this commit it did. Latent only because no test sets that opt today; it will fail silently the first time one does.

---

## Important (8)

**4. Not one log line exists anywhere in this feature; every failure mode is indistinguishable**
`pkg/setting/setting.go:762-767`

`Boolean()` is the error-discarding variant (`go-sdk@v1.17.1/openfeature/client.go:578-582` — `value, _ := c.BooleanValue(...)`). It swallows `ProviderNotReadyError`, `FLAG_NOT_FOUND`, `TYPE_MISMATCH`, `PARSE_ERROR`, and transport failures, all into a bare `false`. This matters most on the remote provider path: `ofrep.Provider` does a live HTTP POST per evaluation and does not implement `StateHandler`, so `SetProviderAndWait` (`featuremgmt/openfeature.go:31`) returns success without ever contacting the relay — the first real network call is the one at boot in `setting.go:763`. A transient relay hiccup pins the process to the SSO token **for its entire lifetime**, silently.

Downstream, empty and failed are also identical: `grafana_com_proxy.go:44-46` and `pkg/plugins/repo/client.go:240-241` both just omit the `Authorization` header when the token is `""`, and `proxyutil/reverse_proxy.go:97-108` logs nothing for non-2xx. Operator symptom: catalog page fails, devtools shows 401 from `/api/gnet/plugins`, `grafana.log` is clean. Use `BooleanValue`/`BooleanValueDetails` and log both the error and the decision.

**5. Hardcoded flag literal — and the test hardcodes the same literal, so a rename passes CI green**
`pkg/setting/setting.go:763` vs `pkg/services/featuremgmt/toggles_gen.go:727`; test at `pkg/setting/setting_test.go:397`

This is the only raw-literal OpenFeature call site in `pkg/` (compare `pkg/expr/graph.go:242`, `pkg/services/updatemanager/plugins.go:224`, `pkg/registry/apis/appplugin/register.go:49`). The constant genuinely cannot be imported — `featuremgmt/openfeature.go:7` imports `setting`, so the cycle is real — but the test registers its `memprovider` flag under the *same literal*, validating it against itself rather than the registry. A rename leaves production evaluating a nonexistent key → `false` forever, with tests green. Not hypothetical: `toggles_gen.json` records four prior names for this flag. The in-package precedent (`setting_unified_alerting.go:434`) at least carries `// use literal to avoid cycle imports`; this does not.

**6. Two-phase initialization: the field is both raw input and resolved output, destructively**
`pkg/setting/setting.go:541` (field), `:1677` (parse), `:762-767` (overwrite)

Three consequences: (a) a `*Cfg` that never had `Resolve` called is indistinguishable from a resolved one — which is exactly why finding 3 fails silently rather than loudly; (b) the operator's configured `proxy_token` is unrecoverable after a flag-off resolve, so no support bundle or debug endpoint can answer "was it configured, and did we reject it?"; (c) after a flag-off resolve, a second call with the flag on sees a non-empty field (the SSO token) and early-returns, keeping the dedicated token discarded. The precondition at `setting.go:759` is prose only and, per finding 4, its violation is undetectable. Both consumers already have `featuremgmt.FeatureToggles` injected (`pluginconfig/config.go:17` uses `featuremgmt.Flag*` two lines later at `:33-34`; `HTTPServer.Features`), which would remove the ordering contract, the global lookup, and the literal all at once.

**7. Flag is sampled once at boot but `RequiresRestart` is not set**
`pkg/services/featuremgmt/registry.go:2252-2257`, `toggles_gen.csv:265` (`...,false,false,false`)

Both consumers read the cached struct field, not the flag (`grafana_com_proxy.go:54`, `pluginconfig/config.go:39`, captured at Wire time). On a deployment using the remote provider — whose entire purpose is runtime flips — flipping this toggle does nothing, with no log, while the metadata says no restart is needed. 40 other entries in this registry do set `RequiresRestart: true`.

**8. `GcomToken()` is dead production code, and the coverage inverted with it**
`pkg/cmd/grafana-cli/utils/command_line.go:29` (interface), `:101-108` (impl)

`install_command.go:102` was its last caller. Remaining references: the interface decl, the impl, `command_line_mock.go:149`, `upgrade_command_test.go:133`, and one assertion at `pkg/cmd/grafana-cli/commands/install_command_test.go:103`. So the only test touching CLI token selection asserts the **dead** method, and the live one — `GrafanaComProxyAPIToken()`, which has no test file in `pkg/cmd/grafana-cli/utils/` at all — is uncovered. A test there would have caught finding 1 immediately. If `GrafanaComProxyAPIToken()` regressed to `""`, nothing in the repo would fail.

**9. `conf/sample.ini` was not updated**
`conf/defaults.ini:1899` gained `proxy_token = ""`, but `conf/sample.ini:1815-1819` — the template operators copy, which documents `sso_api_token` with an explanatory comment — was left untouched (verified: `proxy_token` does not appear in `sample.ini`).

**10. Docs understate the surface the token is attached to**
`docs/.../_index.md:2325` says "plugin catalog browsing and plugin installs via `grafana-cli`". The token goes on **every** `/api/gnet/*` request (`grafana_com_proxy.go:44-46`, route at `pkg/api/api.go:587`) — used by the plugin catalog, community-dashboard import (`public/app/features/manage-dashboards/import/legacy/actions.ts:47`) and the dashboard library (`.../DashboardLibrary/api/dashboardLibraryApi.ts:82,117`) — and separately on **server-side** plugin repo requests (`pluginconfig/config.go:39` → `pkg/plugins/repo/service.go:49`), which are not CLI installs. Since it is forwarded on behalf of any signed-in user hitting `/api/gnet/*`, the token-scoping consequence deserves an explicit sentence.

**11. CLI config-parse error logs at `Debug`, which is a hard no-op by default**
`pkg/cmd/grafana-cli/utils/command_line.go:114-117` → `pkg/cmd/grafana-cli/logger/logger.go:12-16` (`if debugmode`). An unreadable config produces zero output and an empty token, which flows to an unauthenticated request. Copied from the pre-existing `GcomToken()`, so not a regression — but propagated to a second method rather than fixed. `Warn`/`Error` always print.

---

## Suggestions (9)

- **`docs/.../_index.md:2325`** — `[feature toggle]({{< relref "#feature_toggles" >}})` is the only `relref` in this ~3000-line file (verified: `grep -c relref` = 1). `docs/AGENTS.md:111` mandates inline Markdown links; siblings use `[…](#grafana-com)` at `:2310`, `[…](#root_url)` at `:2764`. Use `[feature toggle](#feature_toggles)`.
- **`pkg/setting/setting.go:763`** — 176-char single line packing client construction, flag evaluation, and the emptiness check, with the *interesting* outcome expressed as a bare `return`. Inverting to `if !useDedicated || cfg.GrafanaComProxyAPIToken == "" { … }` makes the doc comment largely redundant.
- **`pkg/setting/setting.go:759-761`** — the comment describes two outcomes; the third (never called → raw value, no toggle, no fallback) is the one a maintainer will hit. State it.
- **`pkg/setting/setting.go:540`** — field comment says "the dedicated auth token", but in the default configuration it holds `sso_api_token` after resolution. Note the two lifecycle meanings; `!= ""` is a valid "was `proxy_token` configured?" test *before* resolution (which `command_line.go:118` relies on) and meaningless after.
- **`pkg/services/featuremgmt/registry.go:2252`** — Description "Grafana.com proxy requests and plugin installs" reads as covering `grafana-cli` (it does not) and omits that the flag is a no-op unless `proxy_token` is set.
- **`pkg/setting/setting_test.go:387-438`** — three byte-identical subtest bodies differing only in inputs; the file already uses table style at `:441` and `:661`. Also `skipStaticRootValidation = true` at `:388` is set without restore (matches `:30`, and `validateStaticRootPath` returns `nil` unconditionally, so benign today — latent if a parallel test ever writes it).
- **`pkg/setting/setting_plugins_test.go:284`** — `Test_readGrafanaComSettings_*` names a function that does not exist anywhere in the repo; the setting is under `[grafana_com]`, not `[plugins]`. Also, because it drives the value via env var, it does **not** exercise the new `conf/defaults.ini:1899` line — nothing covers it.
- **`pkg/cmd/grafana-cli/utils/command_line_mock.go:162`** — hand-edit to a `// Code generated by mockery v2.31.4. DO NOT EDIT.` file, missing the `// GrafanaComProxyAPIToken provides a mock function…` header every other method has, and out of mockery's alphabetical order. There is no `//go:generate` directive or `.mockery.yaml`, so the drift won't be caught until someone regenerates.
- **`pkg/services/featuremgmt/toggles_gen.json:2046-2085, 4558-4571`** — ships four rename tombstones (`pluginsDedicatedInstallToken`, `dedicatedGnetProxyToken`, `dedicatedGrafanaComProxyToken`, `dedicatedGrafanaComProxyAPIToken`). Generated output and `TestFeatureToggleFiles` passes, so it's legitimate — but it permanently records four phantom flags in the registry; worth confirming a regenerate from a clean base doesn't carry them.
- **`pkg/cmd/grafana-cli/commands/upgrade_command_test.go:64`** — `// Use our test implementation that properly implements GcomToken()` now names the wrong method (the path calls `GrafanaComProxyAPIToken()`) and misattributes it (`baseCommandLine` supplies it, not `testCommandLine`).

---

## Checked and found correct

- **`PROXY_TOKEN$` redaction** (`setting.go:831`, test at `setting_test.go:662-667`) — correctly covers `GF_GRAFANA_COM_PROXY_TOKEN`; confirmed empirically in the config-source log (`var="GF_GRAFANA_COM_PROXY_TOKEN=*********"`). This part is done right.
- **Empty `openfeature.EvaluationContext{}`** (`setting.go:763`) — not a bug. `client.go:695` `mergeContexts` folds in the API-level context set by `InitOpenFeatureWithCfg` (`openfeature.go:35-37`), so targeting rules still apply.
- **Generated toggle files** — `TestFeatureToggleFiles` passes; `toggles_gen.{go,csv,json}` match `make gen-feature-toggles`. The `2026-05-05` CSV date is derived from the JSON `creationTimestamp`, not hand-written. The `grafana.` prefix has precedent (`grafana.assetSriChecks`, `grafana.newPreferencesPage`, `grafana.meticulousAIRecorder`).
- **Server entry points** — `RunServer` (`cli.go:113`) and `RunTargetServer` (`target.go:99`) both call `Resolve` after OpenFeature init and before wiring; the module server shares the same already-resolved `*Cfg` pointer. `InitializeForCLI` does not wire `pluginconfig` (verified at `wire_gen.go:1721`), so it needs no resolution today.
- **`Resolve` idempotency** — converges across all four state combinations, though see finding 6(c) for the flag-off-then-on ordering.
- **Test assertions are mutation-sensitive** — deleting the body, dropping either condition clause, or inverting the condition each fails at least one of the three subtests. The one mutation that escapes is changing the flag string (finding 5).

---

## Recommended action

1. **Resolve the `grafana-cli` toggle contradiction (1)** — this is a shipped contract the code does not honor; fix the code or the docs, but not silently.
2. **Fix the toggle name in the docs (2)** and **add `Resolve` to `testinfra.go:124` (3)** — both are one-line fixes with disproportionate impact.
3. **Add logging to `ResolveGrafanaComProxyAPIToken` (4)** — this is the difference between "the toggle didn't work" being a log grep and a source dive; findings 1, 2, 3, 5 and 7 all currently present the identical symptom.
4. Then 5–8. Findings 5 and 7 are the ones that will bite months from now.
5. Suggestions are optional polish.

Nothing was posted anywhere, and no files were modified.
