# Code Review

**Preset**: `audit` (explicit) · roster uncapped (all gate-matched) · `models=high` · `evidence=any` · `reach=wide` | **Reviewers**: quick, broad, knowledge, consistency, design, security, adversarial, go, test | **Date**: 2026-08-12
**Source**: local commit range `b262acdd..ccdf7327` — "Auth: Use dedicated token for requests to Grafana.com (#122269)" (proposed, not merged)
**Scope**: 17 files changed, +223/-14 lines (of which `toggles_gen.{csv,json,go}` are generated)
**Spec**: none found
**Validation**: 3 confirmed, 1 refuted, 0 uncertain, 10 waived (corroborated / probe-confirmed)
**Probes run**: 1 (revert-probe on `ResolveGrafanaComProxyAPIToken`) — tree verified byte-identical afterwards

---

## Agent Selection Rationale

**Preset**: `audit`, given explicitly by the user — not second-guessed.

| Agent | Decision |
|---|---|
| `quick-reviewer` | included — always (review floor) |
| `broad-reviewer` | included — always (review floor) |
| `knowledge-reviewer` | included — substantive change encoding a feature-flag/fallback decision |
| `consistency-reviewer` | included — new config key, feature flag, and interface method with ~500 siblings to compare against |
| `design-reviewer` | included — `utils.CommandLine` gains a method; `Cfg` gains a post-load mutating resolver |
| `security-reviewer` | included — auth-token routing to an external API, secret redaction, config surface |
| `adversarial-reviewer` | included — auth domain, ~110 executable lines, credential-selection ordering across entry points |
| `go-reviewer` | included — Go files present (hard gate); `audit` opens the idiom judgment gate |
| `test-reviewer` | included — test files present (hard gate) |
| `performance-reviewer` | skipped — no DB/ORM query, loop-with-I/O, async, pipeline, or caching surface in the diff |
| `spec-compliance-reviewer` | skipped — no spec discoverable (hard gate) |
| `data-migration-reviewer` | skipped — no migration artifacts (hard gate) |
| `prior-feedback-reviewer` | skipped — local commit range, not a PR with review threads (hard gate) |
| `dotnet` / `typescript` / `cpp` / `rust` reviewers | skipped — those languages absent from the changeset (hard gate) |

**Model policy actually applied** (`models=high`): `quick-reviewer` and `consistency-reviewer` on mid-tier per policy; all four validators on mid-tier per policy; `broad`, `knowledge`, `design`, `security`, `adversarial`, `go` inherited the session model. **Deviation:** `test-reviewer` was dispatched mid-tier, where `models=high` calls for the session model. Its findings were independently corroborated (#4, #10) or probe-confirmed (#9), so the deviation did not cost coverage here, but it was not policy-conformant.

**Process deviations, stated rather than implied:** Step 4.9 clustering and the Step 4.95 evidence screen were performed inline by the orchestrator rather than by dispatched agents. With `evidence=any` the screen has no cluster to tier down on score alone, and every cluster below was independently re-derived from the code by the orchestrator before consolidation.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 5 |
| 🟡 Medium | 6 |
| 🟢 Low | 3 |
| 🔵 Minor | 6 |

Under `reach=wide`, pre-existing defects are promoted into the primary list and labelled `pre-existing`; they are counted and verdict-bearing.

**Verdict**: ❌ NEEDS_CHANGES

Three of the five High findings are introduced by this change (#1, #3, #4). Two are pre-existing (#2, #5) and are reported because `reach=wide` asks for them — but #5 is one function away from the line this change edits, and #2 is the exposure this change exists to reduce.

---

## Findings

### #1 🟠 High: Documentation names a feature toggle that does not exist — the `grafana.` prefix is missing

| | |
|---|---|
| **File** | `docs/sources/setup-grafana/configure-grafana/_index.md:2325` |
| **Category** | doc-code contradiction |
| **Confidence** | 100 |
| **Found by** | quick (High), broad (High), knowledge (MUST), design (Medium), security (Medium), adversarial (High) |

**Issue:** The new docs paragraph says the setting "Requires the `dedicatedGrafanaComProxyAPIToken` [feature toggle] to be enabled." The registered and evaluated name is `grafana.dedicatedGrafanaComProxyAPIToken` (`pkg/services/featuremgmt/registry.go:2253`; `pkg/setting/setting.go:763`).

There is no prefix normalization anywhere in the lookup path — verified directly:

- `ReadFeatureTogglesFromInitFile` (`pkg/setting/setting_feature_toggles.go:161-171`) uses `v.Name()`, the ini key, **verbatim** as the flag key.
- `buildStaticFlagsMap` (`pkg/services/featuremgmt/static_provider.go:21-31`) keys standard flags by `flag.Name` verbatim, then `maps.Copy(flags, confFlags)` merges conf flags over them — again verbatim.
- `grep` for any `TrimPrefix`/`"grafana."` handling in `pkg/services/featuremgmt/` and `pkg/setting/` returns nothing.

Unknown toggle names are not rejected — `ParseFlag` returns a valid flag for any string — so there is no startup warning either.

**Failure scenario:** an operator follows the docs, writes `dedicatedGrafanaComProxyAPIToken = true` under `[feature_toggles]`, and sets `proxy_token`. That registers an unrelated flag key. `ResolveGrafanaComProxyAPIToken` looks up the prefixed name, gets the `false` default, and overwrites the configured `proxy_token` with `sso_api_token`. No error, no log, no effect — the operator believes credential separation is in force while the shared SSO token keeps flowing to the user-reachable gnet proxy. The docs lead directly to the outcome the feature exists to prevent.

**Corroborating evidence that the docs simply went stale:** `pkg/services/featuremgmt/toggles_gen.json` in this very diff records `dedicatedGrafanaComProxyAPIToken` with `deletionTimestamp: 2026-05-05T12:28:16Z` and `grafana.dedicatedGrafanaComProxyAPIToken` created at the *same* timestamp. The docs were written against the pre-rename name and not updated with the final commit of the branch.

**Fix:**
```markdown
Requires the `grafana.dedicatedGrafanaComProxyAPIToken` [feature toggle](#feature-toggles) to be enabled.
When the toggle is disabled, or `proxy_token` is unset, requests use `sso_api_token` instead.
```

---

### #2 🟠 High (pre-existing): `/api/gnet/*` proxies any method and any path to Grafana.com with the instance credential

| | |
|---|---|
| **File** | `pkg/api/api.go:587`, `pkg/api/grafana_com_proxy.go:28-57` |
| **Category** | security / attack surface |
| **Confidence** | 100 (validator-confirmed) |
| **Found by** | security (High), adversarial (High), broad (Medium) |

**Issue:** `r.Any("/api/gnet/*", requestmeta.SetSLOGroup(...), reqSignedIn, hs.ProxyGnetRequest)`. `r.Any` registers `Handle("*", ...)` — all HTTP methods. `ProxyGnetRequest` takes `web.Params(c.Req)["*"]` verbatim, and the director deletes the caller's `Authorization` header and substitutes `Bearer <instance grafana.com token>`. No allow-list on path or method exists in the router, in `util.JoinURLFragments`, in `proxyutil.NewReverseProxy`, or in `grafanaComProxyTransport`. Any signed-in user — Viewer included — can drive arbitrary reads and writes against grafana.com as the instance.

**The anonymous-access sub-claim also holds**, verified independently. `reqSignedIn` is `middleware.ReqSignedIn` = `Auth(&AuthOptions{ReqSignedIn: true})`, with `ReqNoAnonynmous` left false. In `pkg/middleware/auth.go:216-219`:

```go
requireLogin := !c.AllowAnonymous || forceLogin || options.ReqNoAnonynmous
if !c.IsSignedIn && options.ReqSignedIn && requireLogin { notAuthorized(c); return }
```

With `AllowAnonymous` enabled and no `forceLogin` query param or mismatched `orgId`, `requireLogin` is false and an unauthenticated request passes straight through to the handler.

**Relevance to this change — and why it is not merely noise here:** the change alters exactly one line of this file (`:54`, `GrafanaComSSOAPIToken` → `GrafanaComProxyAPIToken`). Because the toggle defaults to `false` (`toggles_gen.csv:265`), the resolver assigns the SSO token anyway, so **the credential on this route is unchanged on every default deployment.** The stated benefit does not exist until the toggle is on, and the toggle's documented name is wrong (#1).

**Fix (follow-up, not this PR):** allow-list the proxied path prefixes the frontend actually needs and restrict to GET; add `ReqNoAnonynmous` so anonymous visitors cannot drive an authenticated outbound call; rate-limit the route.

---

### #3 🟠 High: `grafana-cli` ignores the feature toggle entirely, so the toggle is not a kill switch

| | |
|---|---|
| **File** | `pkg/cmd/grafana-cli/utils/command_line.go:111-122` |
| **Category** | behavior inconsistency / contract |
| **Confidence** | 100 |
| **Found by** | quick, broad, knowledge, consistency, design, security, adversarial, go (8 of 9 reviewers) |

**Issue:** The CLI accessor hand-rolls its own fallback with no flag check:

```go
func (c *ContextCommandLine) GrafanaComProxyAPIToken() string {
	cfg, err := c.Config()
	if err != nil { logger.Debug("Could not parse config file", err); return "" }
	if cfg.GrafanaComProxyAPIToken != "" { return cfg.GrafanaComProxyAPIToken }
	return cfg.GrafanaComSSOAPIToken
}
```

The server path (`pkg/setting/setting.go:763`) gates the same decision on `grafana.dedicatedGrafanaComProxyAPIToken`. `grafana-cli` never calls `featuremgmt.InitOpenFeatureWithCfg` — the only callers are `pkg/cmd/grafana-server/commands/{cli,target}.go` and `pkg/tests/testinfra/testinfra.go` — so the CLI cannot evaluate the flag even in principle.

The docs added in the same commit assert the opposite: the setting is "for plugin catalog browsing and plugin installs via `grafana-cli`" and "Requires the ... feature toggle to be enabled."

**Failure scenario:** an operator stages `proxy_token` while leaving the toggle off — the documented, default, "not enabled yet" state. The server keeps using `sso_api_token`; `grafana-cli plugins install <id>` immediately switches to `proxy_token`. If that token is narrowly scoped (the entire point of a dedicated token) or not yet provisioned, CLI installs fail with 401 while the in-app catalog works, and the documented rollback (turn the toggle off) does not restore CLI behavior. Same instance, same grafana.com API, two different bearer tokens, with no way for the operator to tell.

**Fix:** pick one owner for the algorithm. Either initialize OpenFeature in the CLI plugin-command path and call `cfg.ResolveGrafanaComProxyAPIToken()`, or drop the flag gate server-side and make prefer-proxy-else-SSO the single unconditional rule — then correct the docs. If the divergence is intentional, the docs must say so, because they currently assert the opposite.

---

### #4 🟠 High: `ResolveGrafanaComProxyAPIToken` is an unenforced lifecycle contract; a bootstrap that skips it silently sends unauthenticated requests to Grafana.com

| | |
|---|---|
| **File** | `pkg/setting/setting.go:759-767` (contract), `pkg/tests/testinfra/testinfra.go:124` (concrete miss) |
| **Category** | design / silent failure |
| **Confidence** | 100 (validator-confirmed) |
| **Found by** | broad, knowledge, design, security, adversarial, go, test (7) |

**Issue:** Before this change, both consumers read `cfg.GrafanaComSSOAPIToken`, which `parseINIFile` always populates. The change repoints them at `cfg.GrafanaComProxyAPIToken` (`pkg/api/grafana_com_proxy.go:54`, `pkg/services/pluginsintegration/pluginconfig/config.go:39`), whose *effective* value is produced only by a post-load mutator called from exactly two places (`cli.go:113`, `target.go:99`). The contract exists solely as a doc comment; nothing enforces or detects it, and `Cfg` has no resolved/unresolved state.

`pkg/tests/testinfra/testinfra.go:124` is such a path today: it calls `featuremgmt.InitOpenFeatureWithCfg(cfg)`, never the resolver, then `server.InitializeForTest` at `:144` — and `InitializeForTest` does build `pluginconfig.ProvidePluginManagementConfig` (`pkg/server/wire_gen.go:1073`).

The failure is silent by construction. `ReverseProxyGnetReq` (`pkg/api/grafana_com_proxy.go:39,44-46`) deletes the incoming `Authorization` header and only re-adds one when the token is non-empty:

```go
req.Header.Del("Authorization")
...
if grafanaComAPIToken != "" {
    req.Header.Set("Authorization", "Bearer "+grafanaComAPIToken)
}
```

So an unresolved `Cfg` produces an anonymous outbound request with no error and no log.

**Honest scoping of the impact.** Both real production binaries (`grafana server`, `grafana server target`) *are* patched, and `grep` confirms no existing test sets `testinfra.GrafanaOpts.GrafanaComSSOAPIToken` — so nothing regresses in the current suite. The defect is a live design hazard rather than a live outage: `testinfra` already exposes a `GrafanaComSSOAPIToken` option (`testinfra.go:699-703, :960`) that now silently has no effect on these paths, and any new bootstrap — including Grafana Enterprise entry points, not visible from this repo — fails open the same way with nothing to catch it. Rated High for the silent fail-open shape and the zero-cost detection, not for a currently-breaking test.

**Fix:** remove the contract rather than document it. Keep the parsed value in an unexported field and expose an accessor that applies the flag and the fallback at read time, so an unresolved `Cfg` cannot yield an empty token; or resolve inside `Cfg.Load` / a Wire provider so the DI graph enforces the ordering. Minimally, add `cfg.ResolveGrafanaComProxyAPIToken()` after `testinfra.go:124` — but that leaves the next entry point to make the same mistake.

---

### #5 🟠 High (pre-existing): `cfg:` command-line config overrides are logged unredacted — one function away from the redaction list this change extends

| | |
|---|---|
| **File** | `pkg/setting/setting.go:1155` |
| **Category** | security / secret exposure |
| **Confidence** | 100 (validator-confirmed; call order verified independently) |
| **Found by** | security (sole finder) |

**Issue:** This change adds `"PROXY_TOKEN$"` to the `RedactedValue` pattern list (`setting.go:828-831`), correctly covering the env-var and INI paths. But `applyCommandLineProperties` (`setting.go:1145-1160`) appends the **raw** value:

```go
cfg.appliedCommandLineProperties = append(cfg.appliedCommandLineProperties, fmt.Sprintf("%s=%s", keyString, value))
```

while its sibling `applyCommandLineDefaultProperties` (`setting.go:1139`) formats through `RedactedValue(keyString, value)`. `LogConfigSources()` (`setting.go:1820-1831`) writes every entry at Info level, and `cfg.Load` calls it unconditionally (`setting.go:1428`) with no level or flag gate.

**The call-order question decides this finding, and it was checked directly.** `applyCommandLineDefaultProperties` — the one that *resets* the slice — runs at `setting.go:1252`. `applyCommandLineProperties` runs later, at `:1272`, and only appends. So the reset happens *before* the unredacted append; the raw entries survive to `LogConfigSources` at `:1428`. The finding does not collapse.

**Failure scenario:** a secret supplied as `cfg:grafana_com.proxy_token=<secret>` (or `cfg:security.admin_password=<secret>` — the same hole already exposes every other secret set this way) is written to the log in plaintext. `getCommandLineProperties` parses any `cfg:section.key=value` argument with no allow-list, so this is a supported override mechanism, not an exotic path.

`git blame` places these lines before `ccdf7327`; the change did not create the hole. It is reported because the change extends the very control this line bypasses, so a reader could reasonably believe `proxy_token` is now covered on all paths. It is not.

**Fix:** route `:1155` through `RedactedValue(keyString, value)` exactly as `:1139` does, and add a regression test asserting a secret-suffixed key supplied via `cfg:` is redacted in `appliedCommandLineProperties`.

---

### #6 🟡 Medium: Registry entry omits `RequiresRestart: true` for a flag that is only ever read once at startup

| | |
|---|---|
| **File** | `pkg/services/featuremgmt/registry.go:2252-2257` |
| **Category** | convention / metadata correctness |
| **Confidence** | 100 |
| **Found by** | broad, consistency, design, security, go (5) |

**Issue:** The flag's only consumer resolves it exactly once during `RunServer`/`RunTargetServer` and bakes the result into `cfg.GrafanaComProxyAPIToken`; nothing re-evaluates it. `toggles_gen.csv:265` confirms the generated metadata reports `RequiresRestart` as `false`. 40 sibling entries in the same file set `RequiresRestart: true` for exactly this class of startup-only effect, and `pkg/services/featuremgmt/models.go:158` defines the field as "The server must be initialized with the value."

**Failure scenario:** with a remote OFREP/features-service provider, an operator flips the flag on a running instance. The toggles API reports `requiresRestart: false`, so no restart is scheduled, and the instance keeps using `sso_api_token` indefinitely.

**Fix:** add `RequiresRestart: true` to the entry and regenerate with `make gen-feature-toggles`.

---

### #7 🟡 Medium: Flag name is a bare string literal with no compile-time or test link to the generated constant

| | |
|---|---|
| **File** | `pkg/setting/setting.go:763` |
| **Category** | coupling / silent drift |
| **Confidence** | 100 |
| **Found by** | broad, knowledge, consistency, design, adversarial, go (6) |

**Issue:** The evaluation hardcodes `"grafana.dedicatedGrafanaComProxyAPIToken"` rather than `featuremgmt.FlagGrafanaDedicatedGrafanaComProxyAPIToken` (`toggles_gen.go:727`). Every other flag consumer in the repo uses the generated constant (`pkg/expr/graph.go:242`, `pkg/services/updatemanager/plugins.go:224`, `pkg/api/datasources_k8s.go:201`, and five more). The deviation is *forced* — `pkg/services/featuremgmt` imports `pkg/setting`, so the reverse import would cycle — but nothing in the code records that, and nothing guards against drift. The generated constant currently has **zero references anywhere in the tree**.

**Failure scenario:** the flag is renamed in `registry.go`. The generated constant and every constant-based reference update; this literal compiles unchanged, `Boolean` returns the `false` default, and the feature silently stops working. `TestResolveGrafanaComProxyAPIToken` still passes, because `setting_test.go:397` hardcodes the *same* literal — the test cannot detect the drift.

Not hypothetical: `toggles_gen.json` in this diff records four renames of this flag in eight days (`pluginsDedicatedInstallToken` → `dedicatedGnetProxyToken` → `dedicatedGrafanaComProxyToken` → `dedicatedGrafanaComProxyAPIToken` → `grafana.dedicatedGrafanaComProxyAPIToken`).

**Fix:** add a comment stating the import-cycle reason, export the key as a `const` from `pkg/setting`, and assert equality against the generated constant in a `pkg/services/featuremgmt` test — that package sits on the side of the dependency edge that can see both.

---

### #8 🟡 Medium: Flag-evaluation errors are swallowed and the selected token source is never logged

| | |
|---|---|
| **File** | `pkg/setting/setting.go:763` |
| **Category** | error handling / observability |
| **Confidence** | 75 |
| **Found by** | broad, security, go (3) |

**Issue:** `openfeature.NewDefaultClient().Boolean(...)` discards both the error and the resolution reason, inside a method that returns nothing — so there is no channel at all through which a failed evaluation can surface. Three distinct paths land on the same silent outcome: flag off (the shipped default), flag on but `proxy_token` empty, and provider error. None is logged.

The sibling pattern in this repo does not swallow — `pkg/services/updatemanager/plugins.go:224-229` uses `BooleanValueDetails` and logs the error.

**Failure scenario:** a remote provider is configured and the flag is enabled centrally, but the OFREP call fails at startup. `Boolean` returns `false`; `proxy_token` is silently replaced by `sso_api_token` for the process's lifetime. Nothing in the logs distinguishes "flag is off" from "flag lookup failed", and nothing records which credential is in use — so a subsequent grafana.com 401 is undiagnosable from Grafana's logs.

**Fix:** use `BooleanValueDetails`, log evaluation errors, and emit one info line naming the selected **source** (`proxy_token` / `sso_api_token`) — never the value.

---

### #9 🟡 Medium: A new subtest is tautological — it passes against a no-op resolver

| | |
|---|---|
| **File** | `pkg/setting/setting_test.go:417-427` |
| **Category** | false-positive test |
| **Confidence** | 100 (**probe-confirmed**) |
| **Found by** | test-reviewer (sole finder) |

**Issue:** The subtest *"uses dedicated token when flag is on and proxy_token is set"* asserts `cfg.GrafanaComProxyAPIToken == "dedicated-token"` after calling the resolver. But `cfg.Load()` has **already** set that field to `dedicated-token` from `GF_GRAFANA_COM_PROXY_TOKEN` before the resolver runs, so the assertion cannot distinguish "the resolver preserved the dedicated token" from "the resolver did nothing."

**Probe result (run, not reasoned):** the body of `ResolveGrafanaComProxyAPIToken` (`setting.go:762-767`) was replaced with a no-op and the test re-run:

```
--- FAIL: TestResolveGrafanaComProxyAPIToken/falls_back_to_sso_api_token_when_flag_is_off
--- PASS: TestResolveGrafanaComProxyAPIToken/uses_dedicated_token_when_flag_is_on_and_proxy_token_is_set
--- FAIL: TestResolveGrafanaComProxyAPIToken/falls_back_to_sso_api_token_when_flag_is_on_but_proxy_token_is_not_set
```

The subtest passes with the entire function gutted. The working tree was restored byte-identically and the suite re-verified green.

The other two subtests are sound — they do catch a broken resolver. But the one subtest meant to prove the *feature* works (dedicated token actually wins) proves nothing.

**Fix:** make the pre-state distinguishable from the post-state — set the field to a sentinel before calling, or assert on a return value rather than a field the loader already populated:

```go
cfg.GrafanaComProxyAPIToken = "dedicated-token"
cfg.GrafanaComSSOAPIToken = "sso-token"
cfg.ResolveGrafanaComProxyAPIToken()
require.Equal(t, "dedicated-token", cfg.GrafanaComProxyAPIToken) // now meaningful: the SSO value is the visible alternative
```

Better still, add a fourth case where the flag is on and *both* tokens are set to distinct values, asserting the dedicated one wins — the branch the feature exists for.

---

### #10 🟡 Medium: The only CLI token test asserts a method production no longer calls; the method it switched to is untested

| | |
|---|---|
| **File** | `pkg/cmd/grafana-cli/commands/install_command_test.go:103` |
| **Category** | test coverage / stale test |
| **Confidence** | 100 |
| **Found by** | quick, broad, adversarial, go, test (5) |

**Issue:** `newInstallPluginOpts` (`install_command.go:102`) was changed to call `c.GrafanaComProxyAPIToken()`. `TestIntegrationPluginRepoConfig` still asserts `c.GcomToken() == "token3"` — a method with zero remaining production callers. The new accessor's preference logic (`proxy_token` wins; else fall back to `sso_api_token`) has **no** coverage in either branch.

Compounding it: the fixture sets only `GrafanaComSSOAPIToken: "token3"` (`install_command_test.go:92`), never `proxy_token`, so even a retargeted assertion would not distinguish the two tokens.

**Failure scenario:** anyone changing the CLI fallback breaks nothing visible; the suite stays green while guarding a dead path.

**Fix:** retarget the assertion to `c.GrafanaComProxyAPIToken()` and add fixture variants — (proxy set, sso set) expecting proxy; (proxy empty, sso set) expecting sso; (both empty) expecting `""`.

---

### #11 🟡 Medium (pre-existing): Plugin repo client attaches the Grafana.com token by unanchored URL prefix match

| | |
|---|---|
| **File** | `pkg/plugins/repo/client.go:240` |
| **Category** | security |
| **Confidence** | 50 |
| **Found by** | security (sole finder) |

**Issue:**
```go
if strings.HasPrefix(url.String(), c.grafanaComAPIURL) && c.grafanaComAPIToken != "" {
    req.Header.Set("Authorization", "Bearer "+c.grafanaComAPIToken)
}
```
`c.grafanaComAPIURL` comes from the manager's `BaseURL`, which for the CLI is `--repo` / `GF_PLUGIN_REPO` / `api_url`. Two consequences: the token is sent to any configured non-Grafana.com repo host with no check that it *is* Grafana.com; and if the configured base URL has no path component (e.g. `api_url = https://gcom.internal`), the prefix test is not anchored at a host boundary, so `https://gcom.internal.attacker.example/x` also matches and receives the token.

The change routes the newly introduced token through this same code, which is why it appears here. Confidence is 50: the exploitable variant requires a specific `api_url` shape, and no working repro was constructed.

**Fix:** compare parsed URL hosts (exact match, https required) rather than string prefixes, and refuse to attach the credential to any other host regardless of base-URL configuration.

---

### #12 🟢 Low: `GcomToken()` is dead production code retained on an exported interface

| | |
|---|---|
| **File** | `pkg/cmd/grafana-cli/utils/command_line.go:29`, `:101-109`; `command_line_mock.go:149`; `upgrade_command_test.go:133` |
| **Category** | dead contract |
| **Confidence** | 100 |
| **Found by** | broad, knowledge, design, adversarial, go (5) |

**Issue:** Verified by grep: after `install_command.go:102` switched, `GcomToken()`'s only remaining references are the interface declaration, its implementation, the mock, and test doubles — **zero** production call sites. Two near-identical token accessors with different semantics now sit side by side on the same exported interface, and the dead one is the one with a green test (#10). Every implementer, including out-of-tree ones, pays for both.

**Fix:** remove `GcomToken()` from the interface, `ContextCommandLine`, `MockCommandLine`, and `baseCommandLine`, or explicitly deprecate it with a comment naming the replacement.

---

### #13 🟢 Low: `conf/sample.ini` was not updated alongside `conf/defaults.ini`

| | |
|---|---|
| **File** | `conf/sample.ini:1815-1819` |
| **Category** | convention |
| **Confidence** | 100 |
| **Found by** | broad, consistency, security (3) |

**Issue:** `[grafana_com]` in `sample.ini` mirrors `defaults.ini` — `;url`, `;api_url`, and `;sso_api_token` with an explanatory comment. `proxy_token` was added to `defaults.ini:1899` but not mirrored, so operators editing the annotated sample never learn the option exists.

**Fix:**
```ini
# Dedicated Grafana.com API token for plugin catalog browsing and plugin downloads
;proxy_token = ""
```

---

### #14 🟢 Low: New docs entry uses a Hugo `relref` shortcode where the file's convention is a plain Markdown link

| | |
|---|---|
| **File** | `docs/sources/setup-grafana/configure-grafana/_index.md:2325` |
| **Category** | convention |
| **Confidence** | 100 (convention); anchor correctness **unverified** |
| **Found by** | broad, knowledge (2) |

**Issue:** `docs/AGENTS.md:110` states: "Use inline Markdown links: `[Link text](https://example.com)`." The new `[feature toggle]({{< relref "#feature_toggles" >}})` is the **only** `relref` in this ~3000-line file (verified: `grep -c relref` returns 1). Every other in-page link uses plain Markdown — `#grafana-com`, `#auto_assign_org_role`, `#root_url`, `#rendering`.

**Not asserted:** both reviewers additionally claimed the `#feature_toggles` anchor is wrong (should be `#feature-toggles`, by analogy with `### \`[grafana_com]\`` → `#grafana-com` at line 2310). This could not be settled — the same file also links `#auto_assign_org_role` with the underscore preserved, so the two examples imply different slug rules, and the docs were not built to resolve it. The convention violation stands on its own; treat the anchor as needing a docs build to confirm.

**Fix:** replace with a plain Markdown link, and confirm the resulting anchor against a docs build.

---

## Minor Findings

### Consistency

- `conf/defaults.ini:1899` — `proxy_token` added bare, with no comment saying it is inert without the feature toggle and falls back to `sso_api_token`; `sample.ini`'s `sso_api_token` carries one (knowledge-reviewer, broad-reviewer)
- `docs/.../_index.md:2327` — "Set via environment variable: `GF_GRAFANA_COM_PROXY_TOKEN`." is the only such per-setting callout for a standard `GF_`-prefixed key in the file; the doc states the generic override rule once, up front at lines 79-82 (consistency-reviewer)
- `pkg/setting/setting_plugins_test.go:284` — `Test_readGrafanaComSettings_GrafanaComProxyAPIToken` tests a `[grafana_com]` key but lives among plugin-settings tests rather than with the other `parseINIFile` tests in `setting_test.go` (test-reviewer)

### Testing Gaps

- `pkg/api/grafana_com_proxy.go:54` — no test asserts which token reaches the `Authorization` header under either flag state; no test file exists for this file at all (test-reviewer, broad-reviewer, security-reviewer)
- `pkg/services/pluginsintegration/pluginconfig/config.go:39` — `ProvidePluginManagementConfig`'s token propagation is untested (test-reviewer, broad-reviewer)
- `pkg/setting/setting.go:762` — no test pins the idempotency / second-call contract of the resolver (design-reviewer)

### Residual Risks

- `pkg/setting/setting_test.go:400` — `setProvider`'s cleanup restores `openfeature.NoopProvider{}` rather than the provider installed before the subtest, permanently replacing process-global SDK state for the rest of the package's test binary. No failure today (nothing else in `pkg/setting` evaluates flags), and go-reviewer verified there is no data race — the package's `t.Parallel()` tests are top-level, which Go defers until the sequential pass completes. `go test -race` passes (go-reviewer)
- `pkg/api/grafana_com_proxy.go:52` — no audit log records who drove a proxied grafana.com call with the instance credential, so misuse via #2 is unattributable after the fact (security-reviewer)
- Grafana Enterprise entry points are outside this repository. If Enterprise has its own `RunServer` equivalent, it needs the same `ResolveGrafanaComProxyAPIToken()` insertion, and nothing in this change makes that requirement discoverable from the OSS side (broad, adversarial, go)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| broad-reviewer | 13 | 0 |
| security-reviewer | 11 | 3 |
| go-reviewer | 8 | 1 |
| knowledge-reviewer | 7 | 0 |
| adversarial-reviewer | 7 | 0 |
| design-reviewer | 6 | 0 |
| consistency-reviewer | 5 | 1 |
| test-reviewer | 5 | 2 |
| quick-reviewer | 3 | 0 |
| **Total** | **20** | |

- **Issues Found**: consolidated findings listing this agent (shared findings count for each finder)
- **Unique Issues**: findings reported by this agent alone

Note: `security-reviewer` and `test-reviewer` carried the highest-value sole finds — the redaction hole (#5), the repo-client host match (#11), and the probe-confirmed tautological test (#9). `quick-reviewer` found nothing the others missed and, on #4, actively concluded the opposite ("No other production entry point ... without going through this resolution") — correct as far as production binaries go, but it did not check test infrastructure. Retained per Step 5.5 because six other agents flagged it and the validator confirmed it.

---

## Specialist Notes

### Threat Model Notes (security-reviewer)

**Trust boundaries touched.** Two outbound boundaries carry the credential: the in-process reverse proxy `/api/gnet/*`, whose input boundary is any Grafana user (or, with anonymous access enabled, any visitor) and whose output boundary is Grafana.com; and the plugin repo client used by both the server and `grafana-cli`, whose output host is operator-configurable.

**Data sensitivity.** `sso_api_token` is the instance's Unified-SSO identity on Grafana.com — also used by the logout hook (`pkg/services/auth/gcomsso/gcom_logout_hook.go:50`) and unified storage (`pkg/storage/unified/sql/backend.go:57`). It is strictly higher-privilege than plugin-catalog browsing needs, which is the premise of this change and the premise the default-off fallback preserves.

**Attack-surface change.** Net-neutral by default; net-positive only when the toggle is on **and** `proxy_token` is populated. The change does not narrow what `/api/gnet/*` will proxy, who can reach it, or what it will do with the token.

**Summary the reviewer offered, which the evidence supports:** this change builds the mechanism for credential separation without engaging it. That is defensible as a staged rollout — but only if an operator can tell which mode they are in, and between #1, #3, and #8 they currently cannot.

### Considered But Not Flagged

**Refuted by the validation wave:**

- **"The resolver destroys the configured `proxy_token`, making resolution one-way"** (knowledge, design, adversarial, go — 4 finders, Medium/High) — **refuted**. The overwrite at `setting.go:766` is real, but every claimed consequence fails: (a) non-idempotence needs a second call, and the resolver has exactly two call sites, in mutually exclusive startup paths, each invoked once; (b) "a transient provider failure pins the process" is a property of evaluating any flag once at startup, not of the mutation — it would exist identically with a pure function; (c) "unrecoverable from `Cfg`" is factually wrong — `cfg.Raw` (set at `setting.go:1435`) retains the original ini file, so `cfg.Raw.Section("grafana_com").Key("proxy_token")` still holds the operator's value. Both readers want the effective token, not the raw one, and no admin-settings surface exposes the field. What remains is a style preference with no reachable failure. *(The related `RequiresRestart` concern is a separate, surviving finding — #6.)*

**Examined and dismissed with reasoning the orchestrator checked:**

- **Empty `openfeature.EvaluationContext{}` instead of `TransactionContext(ctx)`** — refuted by two reviewers from the SDK source: `mergeContexts` only adopts lower-precedence attributes when higher-precedence ones are absent, so an empty invocation context cannot erase the global context `InitOpenFeatureWithCfg` installs. The identical pattern exists at `pkg/services/accesscontrol/resourcepermissions/service.go:418`.
- **`context.Background()` with no timeout on a possibly-remote flag evaluation** — bounded at the transport layer; `pkg/infra/features/client.go:47-66` sets both `Timeout` and `DialTimeout`.
- **`logger.Debug("Could not parse config file", err)` as a structured-logger arity bug** — refuted. `pkg/cmd/grafana-cli/logger` is not `pkg/infra/log`; its `Debug(args ...any)` is a `fmt.Println` wrapper. No key/value contract exists.
- **`skipStaticRootValidation = true` set without restore at `setting_test.go:388`** — refuted by two reviewers: the package global is already set unconditionally at `setting_test.go:30` and `setting_session_test.go:13`, and it only guards a function that emits a log line and always returns nil. Redundant, not newly harmful.
- **`ret.Get(0).(string)` panicking on nil in the new mock** — identical to every sibling method in the file; standard mockery contract.
- **Runtime `Cfg` reload invalidating the resolution** — searched `pkg/setting`, `pkg/services/settingsprovider`, `pkg/api`; no runtime reload path exists in OSS.
- **Token leakage via redirect from the plugin repo client** — Go's `http.Client` strips `Authorization` on cross-host redirects.
- **`PROXY_TOKEN$` redaction pattern breadth** — will redact any key ending in `PROXY_TOKEN`; over-redaction is the safe direction, and no other key in `conf/` or `pkg/` currently collides.
- **Config exposure via `/api/admin/settings`** — `AdminGetSettings` serializes `SettingsProvider.Current()`, which redacts through `RedactedValue(EnvKey(...))`; it does not serialize the `Cfg` struct, so the resolved field is unreachable.
- **`Generate{Go: true}` vs siblings' `Generate{LegacyGo: true, LegacyFrontend: true}`** — an established alternate pattern used 9 other times in `registry.go`.
- **`toggles_gen.json` tombstone churn** (four historical names) — generated-file output of the rename history. Not a defect, but cited as evidence in #1 and #7.
- **Path traversal through the gnet proxy** (`%2e%2e` escaping the `/api` prefix) — adversarial-reviewer could not confirm whether the router normalizes the wildcard remainder before `web.Params`; two unconfirmed steps, anchor 25. Requires a running instance to settle. **Unresolved, not cleared.**
- **`c.Config()` re-parsing the whole INI file on every CLI accessor call** — pre-existing pattern shared with `GcomToken`/`PluginRepoURL`; cost only, one-shot CLI process.
- **Whitespace-only `proxy_token`** accepted (`" "` is non-empty → `Bearer  ` sent); `pkg/storage/unified/sql/backend.go:57` does `TrimSpace` on the sibling token. Contained — outcome is a plain 401.
- **`[grafana_net]` legacy alias not applying to `proxy_token`** — verified it only ever applied to `url` (`setting.go:1669-1671`); `sso_api_token` behaves identically. Not a regression.

---

## Positive Observations

- Adding `PROXY_TOKEN$` to `RedactedValue` **in the same change**, with a test case (`setting_test.go:662-667`), is exactly right — the credential is redacted on the env-var and INI paths from day one. (#5 is a pre-existing gap on a third path, not a failure of this work.)
- `proxy_token = ""` is added **uncommented** in `defaults.ini`, correctly satisfying the repo's own rule — enforced at `setting_test.go:56` — that entries there must not be commented or env-var overrides break. `GF_GRAFANA_COM_PROXY_TOKEN` works as documented, and a test proves it.
- The fallback direction is the safe one: a flag-lookup failure or missing `proxy_token` degrades to the previously-working credential rather than to no credential.
- `ResolveGrafanaComProxyAPIToken` carries a doc comment stating its ordering precondition — a genuine *why* comment in the spirit of `AGENTS.md`. The problem (#4) is that a comment is the only thing enforcing it.
- `TestResolveGrafanaComProxyAPIToken` uses the real in-memory OpenFeature provider rather than mocking the client, and covers three combinations. Two of the three subtests are sound (#9 concerns only the third).

---

## Session Metrics (--report)

**Wave timing**: review wave dispatched as one synchronous parallel batch of 9 agents; validation wave as one synchronous parallel batch of 4. Slowest reviewer 478.9s (`broad`), slowest validator 147.7s.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|---|---|---|---:|---:|---:|---:|
| broad-reviewer | reviewer | session (high) | 117,995 | 52 | 478,925 ms | 11 primary + minors |
| security-reviewer | reviewer | session (high) | 106,794 | 28 | 332,263 ms | 9 |
| adversarial-reviewer | reviewer | session (high) | 101,827 | 28 | 354,822 ms | 7 |
| go-reviewer | reviewer | session (high) | 93,121 | 30 | 301,933 ms | 7 |
| quick-reviewer | reviewer | mid | 92,686 | 26 | 217,199 ms | 3 |
| knowledge-reviewer | reviewer | session (high) | 91,313 | 26 | 270,987 ms | 8 |
| test-reviewer | reviewer | mid *(policy deviation — see Agent Selection Rationale)* | 90,524 | 27 | 254,890 ms | 8 |
| consistency-reviewer | reviewer | mid | 90,472 | 22 | 231,747 ms | 5 |
| design-reviewer | reviewer | session (high) | 88,480 | 25 | 290,726 ms | 8 |
| validator: resolver contract (#4) | validator | mid | 87,193 | 28 | 147,716 ms | verdict: confirmed |
| validator: destructive overwrite | validator | mid | 62,938 | 10 | 68,559 ms | verdict: **refuted** |
| validator: gnet exposure (#2) | validator | mid | 59,973 | 14 | 64,061 ms | verdict: confirmed |
| validator: redaction hole (#5) | validator | mid | 59,219 | 9 | 56,311 ms | verdict: confirmed |

Totals: 13 subagents, 1,142,535 subagent tokens, 325 tool calls. Figures are the harness-reported values verbatim.

**Pre-flight gates** (run once, shared with every reviewer):
- `go build ./pkg/setting/... ./pkg/cmd/... ./pkg/api/... ./pkg/services/pluginsintegration/pluginconfig/... ./pkg/services/featuremgmt/...` — PASS
- `go test ./pkg/setting/...` — PASS
- `go test ./pkg/cmd/grafana-cli/...` — PASS

**Probes run**: 1 of 8 nominated. The revert-probe on `ResolveGrafanaComProxyAPIToken` was executed and produced finding #9. The remaining nominations were either satisfied by direct orchestrator verification (call-site enumeration, `GcomToken` caller count, redaction call order, docs link census, `RequiresRestart` sibling count, feature-toggle key normalization) or required resources outside this environment (a running Grafana instance for the `%2e%2e` traversal probe; the Enterprise tree for the constant-reference check). The traversal question is recorded as **unresolved**, not cleared.

**Anomalies**: 1 — `test-reviewer` was dispatched on the mid tier where `models=high` specifies the session model. Step 4.9 clustering and the Step 4.95 screen were performed inline by the orchestrator rather than by dispatched agents. No agent failed, timed out, or returned a malformed report. The working tree was verified byte-identical to `ccdf7327` after the probe (`git status --porcelain` empty apart from this untracked report) and the affected test re-verified green.
