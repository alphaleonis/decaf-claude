I'll run the comprehensive review skill as requested.
I'll start with pre-flight: gathering the diff, manifest, and context.
No remote — running locally as instructed. Let me get the full diff.
Context gathered. Dispatching the review agents in parallel.
Now the remaining roster agents.
Two agents in. Let me verify one remediation claim while the rest run.
Three of ten agents complete, converging strongly. Waiting on the rest.
Truth table confirmed. Waiting on the final three agents.
Redaction verified complete across both the env-override log and `/api/admin/settings` (`pkg/setting/provider.go:124`). Waiting on the last three agents.
Confirmed: `pkg/cmd/grafana-cli/utils` has **no test files at all**, so the new CLI accessor has zero coverage. Waiting on the last three agents.
All scope claims verified. Waiting on the final agent.
Nine of ten agents complete with strong convergence. Waiting on the adversarial reviewer before consolidating.
Nine of ten review agents have reported, with strong cross-agent convergence. I'm waiting on the adversarial reviewer (the last one) before I consolidate and dedupe the findings into the final report.

Verification I've done independently in the meantime:
- Build and vet pass on all touched packages; `pkg/setting`, `pkg/cmd/grafana-cli/...`, and `pkg/services/pluginsintegration/pluginconfig` tests pass.
- Confirmed `pkg/cmd/grafana-cli/utils` has **no test files at all**.
- Confirmed the redaction change is complete (covers both env-override logging and `/api/admin/settings` via `pkg/setting/provider.go:124`).
- Confirmed the new token also backs `/api/gnet/dashboards` (community dashboard library) and the admin plugin-install API (`pkg/api/api.go:449`), not just the paths the docs name.
The adversarial reviewer is still running. Ten agents launched; nine have reported.
Redaction confirmed complete (OSS `CurrentVerbose()` returns nil, so there's no second dump path). Still waiting on the adversarial reviewer — it's the last of the ten and has been running about eight minutes. I'll consolidate the full report as soon as it lands.
All ten agents reported. Verifying the last few novel claims before consolidating.
All ten agents reported and every novel claim is verified. Consolidating.

**Verified during consolidation:** `verifyFlagName` (`pkg/services/featuremgmt/toggles_gen_test.go:182`) *requires* the dotted form for non-legacy flags, and `buildStaticFlagsMap` (`pkg/services/featuremgmt/static_provider.go:21-31`) keys flags verbatim with no prefix normalization — so the documented toggle name is definitively wrong, not a stylistic variant.

---

# Comprehensive Review — "Auth: Use dedicated token for requests to Grafana.com" (#122269)

`b262acdd..ccdf7327` · 17 files, +223/−14 · Go, INI, Markdown · reviewed locally (no remote; provider operations unavailable)

## Summary

Introduces `proxy_token` under `[grafana_com]` as a dedicated credential for Grafana.com API requests, falling back to `sso_api_token`, gated by the new experimental toggle `grafana.dedicatedGrafanaComProxyAPIToken`. Three consumers are switched over: the `/api/gnet/*` reverse proxy, the plugin-management config, and `grafana-cli` installs.

The mechanical parts are clean — redaction, parsing, and the resolver's own unit tests are all correct. **Two of the PR's own claims do not hold against the code**: the feature flag gates two of three consumers, and the documentation instructs operators to enable a toggle name that does not exist.

**Overall risk: High** — the rollout switch is broken at both ends.

**Build/test status:** `go build` and `go vet` pass on all touched packages. `pkg/setting`, `pkg/cmd/grafana-cli/...`, and `pkg/services/pluginsintegration/pluginconfig` tests all pass.

## Walkthrough

| File | Change | Notes |
|---|---|---|
| `pkg/setting/setting.go` | New `GrafanaComProxyAPIToken` field, `ResolveGrafanaComProxyAPIToken()`, ini parse, `PROXY_TOKEN$` redaction | Core of the change; see F3–F6 |
| `pkg/api/grafana_com_proxy.go:54` | Proxy forwards new token | Empty token ⇒ no `Authorization` header |
| `pkg/cmd/grafana-cli/utils/command_line.go` | Interface widened + new accessor | **Ungated** — see F1 |
| `pkg/cmd/grafana-server/commands/{cli,target}.go` | Call `Resolve()` after OpenFeature init | Ordering correct on both |
| `pkg/services/pluginsintegration/pluginconfig/config.go:39` | Plugin config takes new token | Untested |
| `pkg/services/featuremgmt/registry.go:2253` + generated | New toggle | Dotted name is correct |
| `docs/.../_index.md:2321-2327` | New `proxy_token` section | Three inaccuracies — see F2, F8, F12 |
| `conf/defaults.ini:1899` | `proxy_token = ""` | `sample.ini` not updated (F11) |
| tests (3 files) | Resolver + parse + redaction coverage | Consumers uncovered (F7) |

---

## Review Findings

### High

**F1 — `grafana-cli` bypasses the feature flag entirely** — `pkg/cmd/grafana-cli/utils/command_line.go:111-122`

`ContextCommandLine.GrafanaComProxyAPIToken()` returns `cfg.GrafanaComProxyAPIToken` whenever it is non-empty, with no flag check. `grafana-cli` never initializes OpenFeature (verified: zero `openfeature` references under `pkg/cmd/grafana-cli/`), so it *cannot* evaluate the flag as structured. `install_command.go:102` routes plugin installs through it.

Truth table vs. the server-side `ResolveGrafanaComProxyAPIToken` (`pkg/setting/setting.go:762`):

| flag | `proxy_token` | `sso_api_token` | server | grafana-cli | agree |
|---|---|---|---|---|---|
| ON | set | any | proxy_token | proxy_token | ✔ |
| ON | empty | set | sso | sso | ✔ |
| **OFF** | **set** | **set** | **sso** | **proxy_token** | **✘** |
| **OFF** | **set** | **empty** | **"" (no auth)** | **proxy_token** | **✘** |
| OFF | empty | set | sso | sso | ✔ |

An operator pre-provisioning `proxy_token` with the flag off immediately changes which credential `grafana-cli plugins install` presents, while the server still sends the SSO token. The kill switch does not cover the path most likely to be run by hand during an incident. Flagged independently by 8 of 10 agents (confidence 82–92).

*Fix:* gate the CLI path on the same flag, or state explicitly in the flag description and docs that the CLI is intentionally ungated and why. Note `pkg/cmd/grafana-cli/runner/runner.go:17` already carries `featuremgmt.FeatureToggles`.

---

**F2 — Documentation names a toggle that does not exist** — `docs/sources/setup-grafana/configure-grafana/_index.md:2325`

Docs say "Requires the `dedicatedGrafanaComProxyAPIToken` feature toggle to be enabled." The registered name is `grafana.dedicatedGrafanaComProxyAPIToken` (`pkg/services/featuremgmt/registry.go:2253`), and that exact literal is what `setting.go:763` evaluates. The undotted form is a *deleted prior name* of this same flag (`toggles_gen.json`, `deletionTimestamp: 2026-05-05`).

This is a functional break, not a typo:
- `verifyFlagName` (`pkg/services/featuremgmt/toggles_gen_test.go:182`) *requires* the dot for non-legacy `Generate{Go: true}` flags — the undotted name cannot be adopted.
- `ReadFeatureTogglesFromInitFile` (`pkg/setting/setting_feature_toggles.go:162-173`) accepts unknown keys without validation, and `buildStaticFlagsMap` (`pkg/services/featuremgmt/static_provider.go:21-31`) keys verbatim with no normalization.

So an operator following the docs registers an unrelated flag, the real flag stays at its `false` default, their configured `proxy_token` is silently discarded, and — per F5 — nothing logs it. Combined with F1, the half of the feature that *is* gated will never turn on for anyone following the documentation.

*Fix:* use `grafana.dedicatedGrafanaComProxyAPIToken` in the docs.

---

**F3 — Resolution contract is unenforced; a skipped call now drops auth entirely** — `pkg/setting/setting.go:759`, `pkg/tests/testinfra/testinfra.go:124`, `pkg/services/pluginsintegration/test_helper.go:45`

"Must be called after OpenFeature is initialized" is enforced only by a doc comment. `proxy_token` defaults to `""` (`setting.go:1677`), and `ReverseProxyGnetReq` omits the `Authorization` header entirely when the token is empty (`pkg/api/grafana_com_proxy.go:44-46`).

The key regression: **before this change the proxy read `GrafanaComSSOAPIToken`, which `parseINIFile` always populates — a missed init step could not produce an unauthenticated request. Now it can.**

Both OSS production entry points are correctly patched (`cli.go:113`, `target.go:99`, both after `InitOpenFeatureWithCfg` and before `server.Initialize`), so production is covered. But `testinfra.go:124` initializes OpenFeature and starts a full server serving `/api/gnet/*` without resolving, and `test_helper.go:45` calls `ProvidePluginManagementConfig` on an unresolved `Cfg`. Integration tests therefore run with an empty token — a token-forwarding assertion would pass vacuously. `testinfra.GrafanaOpts` (`testinfra.go:960`) also has no `proxy_token` field, so the dedicated path is structurally unreachable in integration tests.

*Fix:* convert resolution to a read accessor so it cannot be skipped; at minimum add `cfg.ResolveGrafanaComProxyAPIToken()` to `testinfra.go` and `test_helper.go`, plus a `GrafanaComProxyAPIToken` option on `GrafanaOpts`.

### Medium

**F4 — Resolution is destructive, non-idempotent, and not marked `RequiresRestart`** — `pkg/setting/setting.go:766`, `pkg/services/featuremgmt/registry.go:2252`

`cfg.GrafanaComProxyAPIToken = cfg.GrafanaComSSOAPIToken` uses one field as both input and output, destroying the parsed `proxy_token` whenever the flag is off. A second call (flag now on) sees a non-empty field and returns early, permanently pinning the SSO token. Nothing can afterwards answer "was a dedicated token configured?"

The flag is snapshotted once at startup, but the registry entry sets no `RequiresRestart` (confirmed `false,false,false` in `toggles_gen.csv`). `InitOpenFeatureWithCfg` supports remote providers whose values change at runtime, so flipping the flag for rollback does nothing until every replica restarts — with no operator signal, and with replicas presenting different credentials mid-rollout.

*Fix:* keep the parsed value immutable and resolve at read time; or set `RequiresRestart: true` so the metadata matches behavior.

---

**F5 — Zero operational visibility into credential selection** — `pkg/setting/setting.go:762`

The resolver has three outcomes (dedicated / flag-on-but-unset fallback / flag-off fallback discarding a configured token) and logs none of them. `grafana_com_proxy.go:44` silently omits auth on an empty token. When the plugin catalog starts returning 401/403 in production there is no log line distinguishing "using dedicated token", "fell back to SSO", "no token at all", or "flag name misconfigured (F2)". This is what makes F2 and F3 dangerous rather than merely wrong.

*Fix:* log once at startup which *source* was chosen — never the value — and `WARN` when a configured `proxy_token` is discarded because the flag is off.

---

**F6 — Flag name hardcoded instead of the generated constant** — `pkg/setting/setting.go:763`

Duplicates `featuremgmt.FlagGrafanaDedicatedGrafanaComProxyAPIToken` (`toggles_gen.go:727`). The import cycle is real and verified (`featuremgmt/openfeature.go:7` imports `setting`), so this is a forced workaround, not negligence. But `toggles_gen.json` records this flag renamed **four times in eight days**; the fifth rename will compile cleanly and silently disable the feature — which is F2's failure mode already realized once.

*Fix:* add a cross-package test asserting the literal matches the generated constant, or declare the name in `pkg/setting` and reference it from `registry.go`.

---

**F7 — None of the three changed call sites are covered by tests**

`pkg/cmd/grafana-cli/utils` has **no test files at all** (verified via `go test ./pkg/cmd/grafana-cli/...`), so the new accessor and its config-error branch are entirely untested. `pkg/api/grafana_com_proxy.go` has zero tests for `ReverseProxyGnetReq`/`ProxyGnetRequest`. `pluginconfig/config_test.go` has no token assertion. `install_command_test.go:103` still asserts `c.GcomToken()` — a method production no longer calls. Reverting any of the three one-line switches would not fail a test.

The three added resolver tests are good (real in-memory OpenFeature provider, all three branches) but cover only the isolated function.

---

**F8 — Documentation understates the token's scope and gives no scoping guidance** — `docs/.../_index.md:2321-2327`

Docs scope it to "plugin catalog browsing and plugin installs via `grafana-cli`". Verified, the token actually backs:
- the entire `/api/gnet/*` reverse proxy (`pkg/api/api.go:587`, `r.Any` behind `reqSignedIn` only — any authenticated user, Viewer included, any method);
- the **community dashboard library** (`public/app/features/dashboard/dashgrid/DashboardLibrary/api/dashboardLibraryApi.ts:82,117`);
- **admin-API plugin installs** (`pkg/api/api.go:449` → `hs.InstallPlugin` → `pkg/plugins/repo/service.go:49`), not just `grafana-cli`.

No required token type, scopes, or rotation guidance is stated. Operators will likely reuse the `sso_api_token` value — defeating the entire purpose of the change, which is a narrowly-scoped credential.

---

**F9 — `GcomToken()` is now dead production code but remains on the interface** — `pkg/cmd/grafana-cli/utils/command_line.go:29,101`

After `install_command.go:102` switched over, the only remaining references are the interface, its impl, the mock (`command_line_mock.go:149`), and two tests. Every implementer now carries two near-identical accessors that differ only in fallback, with inconsistent naming (`Gcom` vs `GrafanaCom`) in the same interface. The widening was only necessary because the old method was left behind.

---

**F10 — Docs link deviates from convention and the anchor is likely wrong** — `docs/.../_index.md:2325`

`{{< relref "#feature_toggles" >}}` is the **only** `relref` in the entire `docs/sources/setup-grafana/` tree, and `docs/AGENTS.md:110` mandates inline Markdown links. The in-file precedent for the same heading style is `[`[grafana_com]`](#grafana-com)` at line 2310 — brackets stripped, underscore → hyphen — so the real anchor for `### \`[feature_toggles]\`` is very likely `#feature-toggles`. *[Unverified: I could not render the Hugo site to confirm the generated anchor id.]* Worth checking before merge, since a failed `relref` breaks the build rather than rendering a dead link.

### Low

**F11 — `conf/sample.ini` not updated** — `conf/sample.ini:1815-1819`

`defaults.ini:1899` gains `proxy_token`, but the `[grafana_com]` block in `sample.ini` — which already carries `;url`, `;api_url`, and a commented `;sso_api_token` — was not given a matching entry. `sample.ini` is the file operators copy to `custom.ini`, so the setting is undiscoverable outside the docs site.

**F12 — `Cfg` field comment omits the two-phase lifecycle** — `pkg/setting/setting.go:540`, `759-761`

The field comment gives no indication that the value means "raw `proxy_token`" before `Resolve()` and "effective token" after, nor that resolution never happens on the `grafana-cli` path. The method comment says "falls back to sso_api_token" without disclosing that this is a *destructive overwrite* of an operator-configured value.

**F13 (informational) — `cfg:` overrides silently drop dotted flag names** — `pkg/setting/setting_feature_toggles.go:107-108`

`if keyName == "" || strings.Contains(keyName, ".") { continue }` means `cfg:feature_toggles.grafana.dedicatedGrafanaComProxyAPIToken=true` is a silent no-op. Pre-existing infrastructure affecting all dotted flags, not introduced here — but it removes one standard enablement mechanism for this toggle, and the new docs point at `[feature_toggles]` generically.

## Positive observations

- **Redaction is complete** — `PROXY_TOKEN$` (`setting.go:831`) covers env-override logging *and* `/api/admin/settings` via `OSSImpl.Current()` → `RedactedValue(EnvKey("grafana_com","proxy_token"), …)` (`pkg/setting/provider.go:124`). `CurrentVerbose()` returns nil in OSS, so there is no second dump path. This is the thing most often forgotten, and it has a real (non-tautological) test.
- The toggle correctly uses the dotted `component.flagName` convention with `Generate{Go: true}` — required by `verifyFlagName`. The undotted siblings nearby are legacy, not the pattern to copy.
- Call-site ordering in `cli.go`/`target.go` is correct, and nothing reads the token between `Load()` and `Resolve()`.
- The token is not widened in reach: it flows only into the plugin repo client, not to plugin subprocesses.
- No endpoint that previously received no credential starts receiving one.

## Explicitly dismissed (checked, not defects)

- **Four "stale" toggle entries in `toggles_gen.json`** — 98 tombstoned entries already exist at base vs. 102 at HEAD; retaining deleted-flag history is normal generator behavior, not hand-edited clutter.
- **`skipStaticRootValidation = true` without restore** (`setting_test.go:388`) — matches the existing package convention (`setting_test.go:30`, `setting_session_test.go:13`). Inherited, not introduced.
- **`openfeature.Boolean()` discarding the evaluation error** — consistent with the codebase-wide idiom (`pkg/expr/graph.go:242`, `pkg/api/datasources_k8s.go:139`, and ~4 others).
- **Data race on `Resolve()`** — called once before serving begins; speculative.
- **Missing comment on `defaults.ini:1899`** — its siblings in the same stanza are uncommented too.

## Recommended actions

1. **Before merge:** fix F1 and F2 — they are two halves of the same broken rollout switch.
2. **Before merge:** verify the `relref` anchor (F10) — build-breaking if wrong.
3. Add the `Resolve()` call to `testinfra.go` and `test_helper.go`, plus a `GrafanaComProxyAPIToken` option on `GrafanaOpts` (F3).
4. Add startup logging of the selected token *source* (F5).
5. Correct the documented scope and add token-scoping guidance (F8).
6. Either set `RequiresRestart: true` or move to read-time resolution (F4) — the latter also resolves F3 and F12.
7. Add tests for the three changed call sites; repoint `install_command_test.go:103` (F7).
8. Delete `GcomToken()` (F9); add `;proxy_token` to `sample.ini` (F11).

---

### Run metadata

**Agents run (10):** architecture-reviewer, security-reviewer, blind-hunter, edge-case-hunter, adversarial-general, code-reviewer, silent-failure-hunter, pr-test-analyzer, comment-analyzer, type-design-analyzer.
**Skipped:** `issue-linker` (no git remote / `--local`); `dependency-check` and static analyzers (no dependency-manifest changes; no analyzer binaries matched). `pr-summarizer` was not dispatched — the Summary and Walkthrough above are mine, built from the diff and commit narrative.
**Nothing was posted anywhere and no code was modified**, per the review-only instruction.

| Agent | Model | Tokens | Tools | Est. cost |
|---|---|---:|---:|---:|
| architecture-reviewer | Opus | 73,404 | 14 | ~$3.30 |
| security-reviewer | Opus | 78,581 | 20 | ~$3.54 |
| adversarial-general | Opus | 104,191 | 53 ⚠ | ~$4.69 |
| edge-case-hunter | Sonnet | 80,041 | 21 | ~$0.72 |
| code-reviewer | Sonnet | 79,777 | 25 | ~$0.72 |
| comment-analyzer | Sonnet | 74,959 | 33 ⚠ | ~$0.67 |
| pr-test-analyzer | Sonnet | 74,939 | 22 | ~$0.67 |
| silent-failure-hunter | Sonnet | 73,383 | 18 | ~$0.66 |
| type-design-analyzer | Sonnet | 70,969 | 12 | ~$0.64 |
| blind-hunter | Sonnet | 56,788 | 2 | ~$0.51 |
| **Agents total** | | **~767k** | | **~$16.12** |
| Orchestrator | Opus | — | — | — see `/cost` |

⚠ = exceeded the 25-tool budget. Costs are blended-rate estimates; run `/cost` for exact figures.

