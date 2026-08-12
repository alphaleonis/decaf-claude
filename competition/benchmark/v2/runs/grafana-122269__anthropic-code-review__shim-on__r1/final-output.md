All five review agents have reported and I've independently verified each anchor against the code. No comment was posted anywhere; nothing was modified.

---

### Code review

`b262acdd..ccdf7327` — "Auth: Use dedicated token for requests to Grafana.com (#122269)"

Found 5 issues at or above the reporting threshold.

**1. `grafana-cli` bypasses the feature toggle entirely — the flag does not gate the one consumer the docs say it gates**

`pkg/cmd/grafana-cli/utils/command_line.go:111-122`

```go
func (c *ContextCommandLine) GrafanaComProxyAPIToken() string {
	cfg, err := c.Config()
	...
	if cfg.GrafanaComProxyAPIToken != "" {
		return cfg.GrafanaComProxyAPIToken
	}
	return cfg.GrafanaComSSOAPIToken
}
```

This re-implements `Cfg.ResolveGrafanaComProxyAPIToken` (`pkg/setting/setting.go:762-767`) minus the flag check. It is what `pkg/cmd/grafana-cli/commands/install_command.go:102` now calls. `grafana-cli` never initializes OpenFeature — `InitOpenFeatureWithCfg` appears only in `pkg/cmd/grafana-server/commands/cli.go:110`, `target.go:96`, and test infra (verified by repo-wide grep), so no flag check is possible on this path as written.

Net effect with `proxy_token` set and the toggle at its default `false` (`registry.go:2258`): the server correctly keeps using `sso_api_token`, while `grafana-cli plugins install` switches to `proxy_token`. That is the exact opposite of what this PR's own docs promise at `docs/sources/setup-grafana/configure-grafana/_index.md:2325` ("plugin installs via `grafana-cli`. Requires the ... feature toggle to be enabled"). The toggle's value as an opt-in/kill-switch is defeated on the CLI path.

**2. New feature toggle is missing `RequiresRestart: true`**

`pkg/services/featuremgmt/registry.go:2252-2259`

The flag is evaluated exactly once at boot (`cli.go:113`, `target.go:99`) and the result is baked permanently into the plain string `cfg.GrafanaComProxyAPIToken`, consumed statically thereafter by `pkg/api/grafana_com_proxy.go:54` and `pkg/services/pluginsintegration/pluginconfig/config.go:39`. `pkg/services/featuremgmt/models.go:157-158` documents `RequiresRestart` for precisely this case ("The server must be initialized with the value"), and 51 entries in `registry.go` already set it. Under a dynamic provider (FeaturesService/OFREP) flipping this toggle silently has no effect until restart, with nothing in the registry to say so.

**3. Docs name a feature toggle that isn't registered under that name**

`docs/sources/setup-grafana/configure-grafana/_index.md:2325` says `` `dedicatedGrafanaComProxyAPIToken` ``. The registered name is `grafana.dedicatedGrafanaComProxyAPIToken` (`registry.go:2253`; `toggles_gen.go:727`). The static provider matches `[feature_toggles]` keys verbatim against the registered names (`pkg/services/featuremgmt/static_provider.go:34-39`), so the `grafana.` prefix is load-bearing, not cosmetic.

**4. `conf/sample.ini` was not updated — required by the contributor checklist**

`conf/defaults.ini:1899` adds `proxy_token = ""`, but `conf/sample.ini:1815-1819` (`[grafana_com]`) still lists only `url`, `api_url`, `sso_api_token`. `contribute/create-pull-request.md:138-141` states verbatim: "If your pull request includes configuration changes, all the following files must be changed correspondingly: `conf/defaults.ini`, `conf/sample.ini`, ...". The sibling key there also carries an explanatory comment (`# Grafana instance - Grafana.com integration SSO API token`); the new key has none in either file.

**5. Docs use a Hugo `relref` shortcode where the file uses plain Markdown links**

`docs/sources/setup-grafana/configure-grafana/_index.md:2325` — `[feature toggle]({{< relref "#feature_toggles" >}})`. This is the only `relref` in the entire file; every sibling cross-reference uses a plain anchor (e.g. line 2310 `` [`[grafana_com]`](#grafana-com) ``, line 2065, line 2051). `docs/AGENTS.md:110`: "Use inline Markdown links: `[Link text](https://example.com)`."

---

### Below threshold — recorded, not part of the review above

- `_index.md:2325` — "plugin catalog browsing and plugin installs via `grafana-cli`" understates scope: the resolved token also feeds the server's `/gnet` reverse proxy (`grafana_com_proxy.go:54`) and the server-side plugin repo client (`pluginconfig/config.go:39` → `pkg/plugins/repo/service.go:36`).
- `command_line.go:101-109` — `GcomToken()` now has zero production callers; `install_command_test.go:103` still asserts against it, so the method the CLI actually uses has no `ContextCommandLine`-level coverage. (AGENTS.md does say "Write tests for new functionality," but the method this was modeled on was equally untested, so this is precedent-matching rather than a clean regression.)
- `setting.go:763` — hardcoded `"grafana.dedicatedGrafanaComProxyAPIToken"` instead of `featuremgmt.FlagGrafanaDedicatedGrafanaComProxyAPIToken`. Structurally forced: `featuremgmt` imports `setting`, so the reverse import would cycle. Consequence is real but unavoidable here — a rename via `make gen-feature-toggles` won't be caught by the compiler.
- `setting.go:540-541` — the field comment ("is the dedicated auth token") is inaccurate after resolution, when the field commonly holds the SSO token instead.
- `pkg/tests/testinfra/testinfra.go:124` — initializes OpenFeature but never calls `ResolveGrafanaComProxyAPIToken`, so integration tests setting `sso_api_token` would see an empty token at the proxy/pluginconfig consumers. Latent only: no test currently sets `GrafanaComSSOAPIToken` (verified by grep).

**Verified as not-issues:** the `PROXY_TOKEN$` addition to `RedactedValue` (`setting.go:831`) is correctly `$`-anchored and matches both the ini key and `GF_GRAFANA_COM_PROXY_TOKEN`; `ResolveGrafanaComProxyAPIToken`'s boolean logic is correct and idempotent across all four (flag × token-set) combinations; both production server entry points call it after OpenFeature init and before `server.Initialize`; the generated toggle files are consistent with the registry.

`go test ./pkg/setting/ -run 'TestResolveGrafanaComProxyAPIToken|Test_readGrafanaComSettings_GrafanaComProxyAPIToken|TestRedactedValue' -count=1` → **ok**.

One caveat on coverage: the prior-PR agent could not read review-thread text on *any* PR — `gh pr view --comments` and all `gh api` calls are refused in this environment regardless of PR age. Findings 1-5 are grounded in the code and the repo's own documented conventions, not in unseen review history; that axis of the review returned no data rather than no findings.
