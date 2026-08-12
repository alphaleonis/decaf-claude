✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-12_grafana-122269.md`

Tracked source is untouched — the only tree change is the untracked report. (I first tried writing it outside the repo to keep the subject tree pristine; the harness blocks that, so it went to the skill's standard `.decaf/` location.)

## Verdict: ❌ NEEDS_CHANGES — 5 High, 6 Medium, 3 Low, 6 Minor

Nine reviewers ran; four validators re-checked the contested findings. **One four-finder finding was refuted** and dropped.

**The three most consequential, all introduced by this change:**

1. **`docs/.../_index.md:2325` — the documented toggle name doesn't exist.** Docs say `dedicatedGrafanaComProxyAPIToken`; the registered name is `grafana.dedicatedGrafanaComProxyAPIToken`. I verified there is no prefix normalization anywhere — `ReadFeatureTogglesFromInitFile` and `buildStaticFlagsMap` both key flags verbatim, and unknown names aren't rejected. An operator following the docs gets silence, and the shared SSO token keeps flowing. `toggles_gen.json` shows the rename landed the same day as this commit — the docs went stale in the final rebase.

2. **`pkg/cmd/grafana-cli/utils/command_line.go:111` — the toggle isn't a kill switch.** The CLI prefers `proxy_token` whenever set, with no flag check; `grafana-cli` never initializes OpenFeature, so it can't check. Stage `proxy_token` with the toggle off and the server uses SSO while the CLI uses the dedicated token — against the same API, with the docs asserting the opposite.

3. **`pkg/setting/setting.go:759` — an unenforced lifecycle contract that fails open silently.** The resolver is called from exactly two places; `pkg/tests/testinfra/testinfra.go:124` inits OpenFeature but skips it, then builds `ProvidePluginManagementConfig`. `ReverseProxyGnetReq` drops the `Authorization` header entirely on an empty token — no error, no log. Scoping it honestly: both production binaries *are* patched and no current test regresses, so this is a live design hazard rather than a live outage.

**Probe result worth calling out** — `pkg/setting/setting_test.go:417`: I gutted `ResolveGrafanaComProxyAPIToken` to a no-op and re-ran. The subtest *"uses dedicated token when flag is on and proxy_token is set"* **still passed**; the other two failed correctly. `cfg.Load()` already sets that field from the env var, so the one subtest meant to prove the feature works proves nothing. Tree restored byte-identically, suite re-verified green.

**Two pre-existing findings promoted by `reach=wide`,** both validator-confirmed: `applyCommandLineProperties` (`setting.go:1155`) logs `cfg:` overrides unredacted while its sibling redacts — and I checked the call order, which is what decides it: the reset runs at `:1252`, the unredacted append at `:1272`, so the raw values survive to the log. And `/api/gnet/*` is an any-method, caller-path-controlled proxy carrying the instance credential, reachable anonymously when anonymous access is on (`requireLogin := !c.AllowAnonymous || ...`).

**One unresolved item I did not clear:** whether `%2e%2e` in the gnet wildcard escapes the `/api` prefix. It needs a running instance; it's recorded as unresolved, not dismissed.
