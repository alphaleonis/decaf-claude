I'll start by loading the skill.
Now dispatching the reviewer subagent.
Reviewer subagent's report, verbatim:

---

### Strengths

- **The response-type whitelist matches the documented contract.** I checked the official slash-command docs (`developers.mattermost.com/integrate/slash-commands/custom/`): `response_type` is documented as "blank or `ephemeral`… or `in_channel`", defaulting to ephemeral. The three-value whitelist at `server/public/model/command_response.go:81` is exactly right, including allowing `""` — a very easy thing to get wrong, and getting it wrong would have broken the most common integration payload shape.
- **No typed-nil trap.** `if err := o.IsValid(); err != nil { return nil, err }` (`command_response.go:72-74`) compares the *concrete* `*AppError` against nil before widening it into the `error` return. The obvious sloppy version (`return nil, o.IsValid()`) would have returned a non-nil `error` holding a nil `*AppError` on every success. This was done correctly.
- **The `assert.Error(t, err)` addition at `command_response_test.go:236` is a real test-quality fix, not filler.** Before this line, the three pre-existing `ShouldError` cases asserted only `assert.Nil(t, response)` — they would have passed if the function returned `nil, nil`. That is exactly the "empty is not the same as failed" class of silent-failure bug. Good catch by the author.
- **Nil-element guard is present and mirrors the existing loop.** `command_response.go:91-93` copies the `if resp == nil { continue }` shape already used at lines 65-70, so it won't panic on `{"extra_responses":[null]}`.
- **Verified green:** `go vet ./model/` clean; `go test ./public/model/ -run CommandResponse -count=1` passes; the full `./model/` package passes (20s). I also grepped the whole repo for existing Go tests, JSON fixtures, and the Cypress `webhook_serve.js` harness that emit a slash-command `response_type` — none use an out-of-whitelist value, so nothing in the existing suite regresses.

### Issues

#### Critical (Must Fix)

None. I looked hard for a data-loss, security, or crash defect *introduced* by this diff and did not find one. The most serious items below are a shipped-behavior regression on a public integration boundary and a missing-i18n defect, both squarely "Important."

#### Important (Should Fix)

**1. The two new i18n keys do not exist in `server/i18n/en.json`, so the error message is the raw key string.**
`server/public/model/command_response.go:82` and `:87`

`model.command_response.is_valid.response_type.app_error` and `model.command_response.is_valid.text.app_error` appear nowhere in `server/i18n/en.json` (verified: only `model.authorize.is_valid.response_type.app_error` matches that grep, in all 20+ locale files). `NewAppError` calls `ap.Translate(translateFunc)` eagerly (`server/public/model/utils.go:365-376`), and go-i18n returns the id when the key is absent. I confirmed this empirically:

```
AppError.Message="model.command_response.is_valid.response_type.app_error"
Error()="CommandResponse.IsValid: model.command_response.is_valid.response_type.app_error, invalid response type"
```

`Message` is the field serialized to API clients. On the `Client4.ExecuteCommand` path (`client4.go:5961`) the raw key is wrapped straight into `fmt.Errorf("failed to decode command response: %w", err)` and surfaces to the caller; on the server paths it lands in `detailed_error` and the logs. `tools/mmgotool/commands/i18n.go` walks `--model-dir` (default `../model`) for exactly this, and `mmgotool i18n check` reports source keys missing from `en.json`. Note the `server/Makefile:342` `i18n-check` target only runs `clean-empty --check` and `check-empty-src`, so CI will likely *not* catch this — it needs to be fixed by hand. Add both entries to `server/i18n/en.json` (English only — `.github/workflows/i18n-ci-template.yml` hard-fails PRs that touch other locales).

**2. The text-length check is a newly-invented limit that breaks ephemeral integration responses that work today.**
`server/public/model/command_response.go:85-88`

Before this change, `CommandResponseFromHTTPBody` accepted anything up to `MaxIntegrationResponseSize` = 1MB (`server/channels/app/webhook.go:31`, applied at `command.go:586`). For `response_type: ephemeral` (and the blank default — the *documented default*), the text is delivered via `SendEphemeralPost`, which performs no length validation at all (`server/channels/app/post.go:692-737`: no `Post.IsValid` call anywhere in that function). So a third-party slash command that dumps, say, 200KB of log output or a wide table ephemerally works today and will now fail the whole command with `api.command.execute_command.failed.app_error` (HTTP 500, since `command.go:597` discards the model's 400).

The docs page specifies no `text` length limit, so this is a new constraint on a public integration contract, arriving with no release note, no docs update, and no config gate. Either drop the length check or gate/announce it deliberately.

**3. The 65535 limit is byte-based, hardcoded, and doesn't correspond to any limit the product actually enforces.**
`server/public/model/command_response.go:85-86`

- `65535` silently duplicates `model.PostMessageMaxBytesV2` (`server/public/model/post.go:72`) — same package, so this should be that constant, or a named local const, not a bare literal in a local variable.
- The limit that is actually enforced on a resulting post is *runes*, not bytes, and it is `GetMaxPostSize()` → `PostMessageMaxRunesV2` = **16383** (`post.go:508`, `store/storetest/post_store.go:4676`, `app/platform/config.go:392`). So the new check is simultaneously too loose and misaligned. Verified both directions empirically:

```
20000 ascii in_channel:            err=<nil>  ok=true   (post rune cap=16383)  <- passes model check, fails downstream
21846 CJK runes (65538 bytes):     err=...text is too long ok=false            <- rejected at 21846 runes, well under the rune cap
```

A CJK-language integration gets rejected at ~21.8k characters while an English one sails through at 20k characters and then fails downstream anyway. If a length check belongs here, it should be `utf8.RuneCountInString` against the post rune limit — but note the post limit is a runtime/config value the `model` package can't see, which is itself an argument that this check belongs at the app layer (see issue 5).

**4. Validation is enforced on the consumer (`Client4`) but not on the producer, so the Go client can reject its own server's legitimate output.**
`server/public/model/client4.go:5961` and `:5982`

`Client4.ExecuteCommand` / `ExecuteCommandWithTeam` decode via `CommandResponseFromJSON`, so they now inherit the new strictness — but nothing validates on the way *out*. Plugin and built-in command responses never pass through `IsValid` at all: `tryExecutePluginCommand` and `tryExecuteBuiltInCommand` return `*model.CommandResponse` structs directly to `HandleCommandResponse` (`server/channels/app/command.go:233-253`). So a plugin that returns `response_type: "foo"`, or text over the byte cap, produces a response the server happily serializes and every `Client4` (mmctl, plugins, third-party Go tooling, the server's own api4 tests) now rejects with `nil, err` — losing the payload entirely rather than degrading.

This is also a forward-compatibility hazard for a *published* module: if Mattermost ever adds a third `response_type`, every pinned older `server/public` breaks hard on decode. Clients decoding a server response should generally be permissive. Consider restricting the new check to the inbound-integration paths and leaving the client decoder unchanged, or at minimum decide this consciously.

**5. Validation in the decoder deviates from the package convention.**
`server/public/model/command_response.go:72-74`

The sibling decoder for the closest-analogous type does decode + normalize and deliberately does *not* validate: `IncomingWebhookRequestFromJSON` (`server/public/model/incoming_webhook.go:193-211`) ends with `o.Attachments = StringifyMessageAttachmentFieldValue(o.Attachments); return o, nil`. Across `model`, `IsValid()` is a method the app/store layer calls at a trust boundary it chooses (`Command.IsValid` at `command.go:67`, `Post.IsValid(maxPostSize)` — which even takes the policy value as a parameter). Folding validation into the decoder makes the policy non-optional for every consumer of the public module and is why issues 2 and 4 exist. Adding `IsValid()` as a method is good; calling it from inside `CommandResponseFromJSON` is the part worth reconsidering.

**6. The plain-text branch bypasses all of it, so "strict validation" is only half-applied.**
`server/public/model/command_response.go:39-41`

An integration that responds `Content-Type: text/plain` goes through `CommandResponseFromPlainText`, which is untouched. A 900KB `text/plain` body is accepted; byte-for-byte the same content as `application/json` is rejected. That asymmetry is worse than either consistent choice: it makes the limit trivially bypassable and makes behavior depend on a header. `CommandResponseFromPlainText` is also exported public API with no validation. Whatever the limit ends up being, both branches of `CommandResponseFromHTTPBody` should agree.

**7. The new validation walks past a reachable nil-pointer panic instead of closing it.**
`server/public/model/command_response.go:90-93`

Pre-existing, but this diff is the function that was hardened, so it's in scope. I confirmed the model half empirically:

```
nil-extra: err=<nil> len=1 elem0nil=true
```

`{"text":"hi","extra_responses":[null]}` passes validation and yields `[]*CommandResponse{nil}`. Downstream, `HandleCommandResponse` (`server/channels/app/command.go:619-628`) iterates `response.ExtraResponses` and calls `HandleCommandResponsePost(rctx, command, args, resp, builtIn)`, whose first statements are `post.Type = response.Type` / `post.SetProps(response.Props)` (`command.go:638-644`) — a nil dereference. This is reachable from `commandWebhook` (`server/channels/web/webhook.go:114-121` → `HandleCommandWebhook` at `app/webhook.go:993`) and from any custom slash command's HTTP response. I found no `recover()` anywhere in the `server/channels/web` or `api4` handler chain (only in jobs, web_hub, plugin_api, and the outgoing-webhook goroutine at `app/webhook.go:131`), so this reaches net/http's per-connection recovery: panic logged, connection dropped, no response.

`continue` preserves that. Rejecting nil entries (or filtering them out, as `StringifyMessageAttachmentFieldValue` already does for attachments) would close it. Note the app layer only processes *one* level of `ExtraResponses`, while `IsValid` recurses arbitrarily deep and `CommandResponseFromJSON` normalizes attachments only one level deep — three different depths for the same structure. Worth a comment at minimum. [Inference] on the panic itself: it is a code trace, not something I executed, since it requires a running App and DB.

**8. Test gaps — the tests pass, but they don't pin the behavior tightly.**
`server/public/model/command_response_test.go:159-182`

- **No boundary case.** The test uses 65536 (fails). I verified 65535 currently passes; nothing pins that, so an off-by-one flip to `>=` would not be caught.
- **No error identity assertion.** `assert.Error(t, err)` doesn't distinguish "rejected by validation" from "rejected by the JSON parser." A case can pass for the wrong reason. Assert the `*AppError` `Id` (and the 400 `StatusCode`, which is otherwise entirely untested) via `errors.As`.
- **No green-path case for the new whitelist.** No test asserts that `response_type: "in_channel"` alone is *accepted*. The two existing in_channel cases (lines 167, 176) both expect errors. The existing coverage for `""` and `"ephemeral"` is incidental, predating this change.
- **`IsValid()` has no direct test.** It's new exported public API. Its `resp == nil { continue }` branch is uncovered — the existing "null array items" case at line 123 covers null *attachments*, not null `extra_responses`.
- **`TestCommandResponseFromHTTPBody` untouched**, so the `text/plain` bypass in issue 6 isn't pinned in either direction.

#### Minor (Nice to Have)

- `command_response.go:80` — `// check response type` restates the code. Per the repo's comment discipline, either explain *why* the whitelist exists (link the documented contract) or drop it.
- `command_response.go:79` — `IsValid()` is new exported API on a public module and has no doc comment stating what it validates or that it's advisory. Most `model` `IsValid` methods lack one, so this is consistency-neutral, but a new public method on a published package is a good place to start.
- `command_response.go:85` — `maxLength := 65535` is a local variable used once; make it a package-level `const` (see issue 3 for which value).
- `command_response.go:82,87` — the `DetailedError` strings ("invalid response type", "text is too long") don't say *what* the invalid value or actual length was. `Post.IsValid` sets `params` with `{"Length":…, "MaxLength":…}` (`post.go:510`); doing the same makes the error actionable for integration authors debugging a 500.
- For a change billed as "strict validation," the fields most worth validating are untouched: `Type` (an integration attempting a `system_` prefix is caught only later, at `CreateCommandPost`, `command.go:65-68`), `ChannelId` (not checked for a valid 26-char id before `GetChannelMember`), `Props` size, and `Attachments`. `GotoLocation` is fine — the webapp guards it with `isUrlSafe` (`webapp/channels/src/actions/command.ts:203`). Not a defect, but the scope is narrower than the commit message implies.

### Recommendations

1. **Split the two halves.** Adding `CommandResponse.IsValid()` as a method is a clean, backward-compatible addition. Wiring it into `CommandResponseFromJSON` is the part that changes behavior for every existing caller including `Client4`. Land the method, then call it deliberately at the app-layer trust boundary (`DoCommandRequest` at `command.go:595` and `HandleCommandWebhook`) where the app can supply `maxPostSize` and choose the status code — matching how `Post.IsValid(maxPostSize int)` already works.
2. **Decide the length question on evidence.** Either drop it (the real limit is enforced downstream and is config-driven) or make it rune-based against the actual post limit and announce it. The current byte-based magic number is the worst of both.
3. **Add the `en.json` entries in this PR** and, separately, consider whether `server/Makefile`'s `i18n-check` should also run `mmgotool i18n check` — the tool already implements exactly the check that would have caught this, and the target doesn't invoke it.
4. **Strengthen the tests to assert error identity, not just error presence.** Given the diff's own best change was fixing an assertion that could pass on `nil, nil`, the new cases deserve the same rigor: `errors.As` to `*model.AppError`, assert `Id` and `StatusCode`, and add the 65535 boundary.
5. Since this changes an integration-facing contract in a published Go module, the PR needs a release note and a docs PR against the slash-command reference — otherwise integration authors get an opaque 500.

### Assessment

**Ready to merge?** No.

**Reasoning:** The response-type whitelist is correct and well-matched to the documented contract, and the error-assertion fix in the tests is genuinely valuable — but the change ships two AppError IDs with no `en.json` entries (verified: the message renders as the raw key), and its text-length rule is an invented byte-based limit that rejects ephemeral integration responses working today while missing the 16383-*rune* limit the product actually enforces. Enforcing the new rules inside the decoder also makes `Client4.ExecuteCommand` reject output the server itself produces unvalidated via plugin and built-in commands. Fix the i18n entries, resolve the length rule (drop it or make it rune-based at the app layer), and align the `text/plain` branch; then it's a good change.

