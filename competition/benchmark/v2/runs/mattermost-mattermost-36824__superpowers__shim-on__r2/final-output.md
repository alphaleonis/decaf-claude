Reviewer subagent's report, verbatim:

---

I reviewed the full diff, the four call sites of the changed decoder, the downstream post pipeline, the i18n catalog, and ran the package tests plus a coverage profile of `IsValid`.

---

### Strengths

- **The response-type rule matches the documented contract.** The Mattermost custom-slash-command docs state `response_type` is "blank or `ephemeral` … or `in_channel`", and the check at `command_response.go:81` allows exactly those three. Correctly permitting `""` is the easy thing to get wrong here, and it wasn't.
- **`nil` elements in `ExtraResponses` are skipped** (`command_response.go:91-93`), mirroring the existing `nil` handling in the decode loop at `:65-70`. The existing `"null array items"` test case proves that shape reaches this code, so the guard is warranted rather than defensive noise.
- **The test-harness bug fix is real and valuable.** Before this change, `TestCommandResponseFromJSON` only asserted `assert.Nil(t, response)` in the error branch — a case that returned `(nil, nil)` would have passed silently. Adding `assert.Error(t, err)` at `command_response_test.go:236` closes that hole for all existing cases too.
- Recursion into `ExtraResponses` terminates safely: `encoding/json`'s scanner caps nesting at 10 000, so no unbounded-depth stack concern from parsed input.
- Tests pass and `go vet` is clean (`go test ./model/ -run TestCommandResponse` → ok).

### Issues

#### Critical (Must Fix)

None. Nothing here loses data or opens a security hole; the problems below are correctness-of-layering, compatibility, and convention issues.

#### Important (Should Fix)

**1. The two new i18n message IDs do not exist in `server/i18n/en.json`** — `server/public/model/command_response.go:82` and `:87`

`model.command_response.is_valid.response_type.app_error` and `model.command_response.is_valid.text.app_error` are absent from the catalog (verified by grep; the diff touches no i18n file). `NewAppError` calls `Translate`, and `i18n.T` returns the translation ID verbatim when the key is missing (`server/public/shared/i18n/i18n.go:41-49`, `model/utils.go:281-296`). So `AppError.Message` becomes the literal string `model.command_response.is_valid.text.app_error`, which then propagates into the wrapping errors at `web/webhook.go:115` and `app/command.go:596` and into server logs. Every sibling model validator has an entry (e.g. `model.authorize.is_valid.response_type.app_error`, the ~40 `model.incoming_hook.*` keys). Fix: add both entries to `server/i18n/en.json` (`make i18n-extract`), and only to `en.json` — the i18n CI workflow fails PRs that touch other locales.

**2. Validation is placed in a bidirectional decoder, so a Go API client now rejects the server's own legitimate responses** — `command_response.go:72-74`, consumed at `client4.go:5961` and `client4.go:5982`

`CommandResponseFromJSON` is used in two opposite directions: as an *ingest* boundary (`app/command.go:595` for third-party integration replies, `web/webhook.go:114` for delayed `response_url` replies) and as a *client-side response decoder* (`Client4.ExecuteCommand` / `ExecuteCommandWithTeam`). Validation only makes sense on the first.

Concretely, the producers of the response the client parses are never validated. A plugin's `ExecuteCommand` hook result is returned straight through `app/plugin_commands.go:165-179` with no `IsValid()` call, and for ephemeral responses `CreateCommandPost` → `SendEphemeralPost` (`app/post.go:692`) never runs `Post.IsValid` because nothing is persisted. So a plugin returning 100 KB of ephemeral text, or a typo'd `"in-channel"`, works today in the webapp and will keep working — but `Client4.ExecuteCommand` now returns `nil, "failed to decode command response: …"`. The server emits a response its own shipped client refuses to parse, and the client has no way to opt out. Since `server/public` is a separately tagged module, this lands as a silent behavioral break for third-party Go bots on upgrade.

Fix: call `IsValid()` at the ingest sites (`DoCommandRequest` in `app/command.go` and `commandWebhook` in `web/webhook.go`), or add a separate strict entry point, and leave `CommandResponseFromJSON` a pure decoder. That also matches the sibling precedent — `IncomingWebhookRequestFromJSON` (`incoming_webhook.go:193-211`) decodes and normalizes only.

**3. One bad `extra_responses` entry now discards the entire payload, including the valid main message** — `command_response.go:90-98`

`HandleCommandResponse` (`app/command.go:604-628`) deliberately processes the main response and each extra response independently, logging per-item failures and continuing. Before this change, an unknown `response_type` on an extra response meant that one item produced no post (`CreateCommandPost` falls through both branches at `:73` and `:82` and returns without posting) while everything else went through. Now the whole response fails at parse time and the user gets a generic "command failed", losing the main message too.

Related over-strictness: `IsValid` recurses arbitrarily deep, but `HandleCommandResponse` walks exactly one level of `ExtraResponses`. A bad `response_type` three levels down — data the server would never render — now rejects the whole payload.

Note this is not an argument against validating the top-level `response_type`: converting the old silent-drop into an explicit error there is a genuine improvement. It's the all-or-nothing aggregation and the unbounded recursion depth that regress behavior with no upside.

**4. The text limit is measured in the wrong unit and doesn't correspond to any real constraint** — `command_response.go:85-88`

`len(o.Text)` counts bytes; the limit that actually governs whether the text can become a post is `utf8.RuneCountInString(o.Message) > PostMessageMaxRunesV2` (16 383) in `Post.IsValid` (`model/post.go:508`). The two neither agree nor nest:

- 20 000 ASCII characters passes the new check and still fails post creation — no protection gained.
- 16 383 four-byte runes (65 532 bytes) passes both; 16 384 four-byte runes fails the new check for the wrong stated reason.

Memory is already bounded upstream by `io.LimitReader(resp.Body, MaxIntegrationResponseSize)` (1 MB, `app/command.go:586`). As written the check rejects essentially nothing the post layer wouldn't already reject, while adding a second, differently-shaped failure mode on a public API. If a limit is wanted, use the rune count and `PostMessageMaxRunesV2`, or drop the check.

**5. The `application/json` and `text/plain` branches now disagree** — `command_response.go:36-42`

`CommandResponseFromHTTPBody` routes plain-text bodies through `CommandResponseFromPlainText` (`:40`), which bypasses `IsValid` entirely. The identical 200 KB body is rejected as `application/json` and accepted as `text/plain`. The docs explicitly tell integrators that `response_url` replies "should either be a plain text or JSON-encoded body", so both are first-class paths. Whatever limit is settled on should be enforced in one place that both branches reach.

**6. Test gaps** — `command_response_test.go:159-182`

- **No assertion on *which* error is returned.** All three new cases assert only `assert.Error`. The length case, for example, would still pass if the 64 KB payload failed for an unrelated reason. Assert `appErr.Id` (and `StatusCode`) so the tests are actually pinned to the new code.
- **No boundary case.** `strings.Repeat("a", 65536)` is one past the limit; exactly 65535 (must pass) is untested, so a `>` → `>=` regression goes unnoticed.
- **The `nil` skip branch is uncovered.** A coverage profile of the new code shows `command_response.go:91.18,92.12` (`if resp == nil { continue }`) at 0 hits — no test has a `null` element in `extra_responses`, only in `attachments`. That branch is the difference between working and a nil-deref panic.
- **No positive `in_channel` case.** The only two tests using `in_channel` both expect failure, so nothing proves the constant is accepted.
- **`IsValid()` is now exported public API with no direct unit test** — it is only exercised transitively through the decoder.
- **No test documents the plain-text asymmetry** from issue 5.

#### Minor (Nice to Have)

- `command_response.go:85` — `maxLength := 65535` is a local variable holding a magic number that already exists as a package constant in the same package: `PostMessageMaxBytesV2 = 65535` (`model/post.go:72`). Reference the constant, or declare a package-level `CommandResponseTextMaxBytes` next to the existing `CommandResponseType*` constants at `:15-18`.
- `command_response.go:80` — `// check response type` restates the code on the next line. Codebase convention is to comment *why*; a comment citing the documented tri-state contract (blank defaults to ephemeral) would earn its place.
- `command_response.go:98-99` — missing blank line before the final `return nil`, inconsistent with the spacing used between the other blocks in the same function.
- The commit says "strict validation", but `ChannelId` (fed to `GetChannelMember` at `app/command.go:648`), `Type` (rejected at `CreateCommandPost:65-68` if it carries the `system_` prefix), `Username`, and `IconURL` are all unvalidated. Not a defect — but if the goal is a canonical `IsValid`, `Type`'s system-prefix rule is the one with a clear existing precedent to pull in.

### Recommendations

1. **Move the call.** Validate at the two ingest boundaries, not inside a decoder that also runs on the client. That resolves issues 2 and 5 together and leaves `CommandResponseFromJSON` semantics unchanged for existing consumers of the public module.
2. **Make extra-response validation non-fatal.** Either restrict `IsValid` to the top level and let `HandleCommandResponse` validate each extra response as it processes it (skipping the bad ones, as it does today for post failures), or bound the recursion at one level to match what the server actually renders.
3. **Decide what the text limit is for.** If it's post-length, use `PostMessageMaxRunesV2` and rune counting. If it's payload size, `MaxIntegrationResponseSize` already covers it and the check can go.
4. **Add the en.json entries** and run `make i18n-extract` before this can merge.
5. **Flag the compatibility change.** `server/public` is tagged and released independently (`.github/workflows/tag-public-module.yaml`); a decoder that starts rejecting previously-accepted payloads warrants a note for integration authors.

### Assessment

**Ready to merge?** No — with fixes.

**Reasoning:** The validation rules themselves are well-chosen and match the documented contract, but they're installed in a decoder that also parses the server's own responses on the client side, which turns previously-working plugin and ephemeral responses into client-side decode failures; combined with the missing `en.json` entries (guaranteed untranslated IDs in logs), the byte-vs-rune mismatch against the actual post limit, and the plain-text path that skips validation entirely, the change needs a layering fix before it's safe on a public, plugin-facing API.
