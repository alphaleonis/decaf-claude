I'll run the code-review skill as requested.
Pre-flight gates pass (`go vet ./model/` clean; `go test ./model/ -run TestCommandResponse` ok). Dispatching the wave.

```
Review team (preset `bugs` — wave (roster=4 explicit) · models=low · evidence=norm · reach=narrow):
- quick-reviewer (always — review floor) — mid tier
- broad-reviewer (always — review floor) — mid tier
- adversarial-reviewer — validation newly applied to externally-supplied slash-command payloads (external integration boundary) — session model
- test-reviewer — test files present in changeset (hard gate) — mid tier
- go-reviewer: dropped — roster N=4 (explicit): ranked below the 2 specialists kept. Hard-gate coverage traded: this is a pure-Go diff and its Go-idiom surface (the `*AppError`-vs-`error` return, typed-nil hazard for callers) goes unreviewed by a stack specialist.
- design-reviewer: dropped — roster N=4 (explicit): ranked below the 2 specialists kept (public API surface changed: new exported `IsValid`, behavior change to exported `CommandResponseFromJSON`)
- security-reviewer: dropped — roster N=4 (explicit): gate matched (parsing data crossing a network boundary), ranked below the 2 specialists kept
- knowledge-reviewer, consistency-reviewer: dropped — roster N=4 (explicit): ranked last under `bugs`
```
All four reviewers returned. Running nominated probes (Step 4.5) — I'm now the only actor on the tree.
Probes confirm all three new test cases fail when their guard is removed (tree restored byte-identical, suite green again). Now screening the clusters (Step 4.95).
Screen complete. Dispatching the validation wave on the four primaries the screen left open (Step 5.6).
All four validators confirm. Writing the report.
✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_09-34-42.md`

**Verdict: ❌ NEEDS_CHANGES** — 3 High, 2 Medium, 1 Minor. All four validated findings confirmed; none refuted. Working tree left clean (only the untracked `.decaf/` output dir).

The change adds validation `CommandResponse` genuinely lacked, but enforces the new contract at one boundary out of four, with a limit that's the wrong value in the wrong unit.

**High**

1. **Parse-time rejection breaks working integrations** (`command_response.go:72-74`). An unrecognized `response_type` previously parsed fine and fell through `CreateCommandPost` — success, no post. Now `doCommandRequest` (`app/command.go:595-597`) turns it into HTTP 500 *after* the integration's side effect ran. Separately, `SendEphemeralPost` has no length gate at all, so ephemeral responses up to `MaxIntegrationResponseSize` (1 MB) worked before and are now capped at 65535 bytes. The validator found no precedent for this: the project's own outgoing-webhook response parser still decodes leniently.

2. **Strict validation applied to the server's own unvalidated response** (`client4.go:5961`, `:5982`). A plugin's `ExecuteCommand` hook response is encoded by `api4/command.go:428` with no validation, then re-parsed by `Client4.ExecuteCommand` through the new strict path — so a non-canonical `ResponseType` fails the client decode for a command that already succeeded and whose post already exists. Webhook-backed commands are *not* affected (they already pass this same gate server-side); the exposure is out-of-tree plugins. Severity is contested — two of three assessments argued Medium.

3. **Both new i18n ids unregistered** (`command_response.go:82`, `:87`). `grep model.command_response server/i18n/en.json` → 0, while the sibling `Command.IsValid` registers all 14 of its ids. The two webhook callers wrap the error under a registered outer id, so there it leaks only to logs and `DetailedError` — but `Client4.ExecuteCommand` propagates the `*AppError` unwrapped, so a Go SDK consumer sees the literal id string. No CI gate in this repo catches it.

**Medium** — the 65535/`len()` limit is three defects in three lines: it duplicates `PostMessageMaxBytesV2` as a bare literal, counts bytes where every sibling message-body check counts runes, and doesn't match the real downstream gate (`maxPostSize` = 16383 **runes**), so a 40,000-char response passes here and still fails at post creation. And `IsValid` runs only on the JSON branch of `CommandResponseFromHTTPBody`, so the length rule is bypassable by sending `text/plain` — a header the validated party controls.

**On the tests** — I ran four revert probes: each new case fails when and only when its own guard is removed, so none is tautological, and the added `assert.Error(t, err)` is a real strengthening (the error branch previously never checked `err`). One gap recorded but not reported as a finding under `reach=narrow`: the new `if resp == nil { continue }` branch has no covering test.

Two process notes: I skipped Step 4.9's separate clustering agent and clustered the 12 findings inline (recorded in the report), and the `roster=4` cap dropped `go-reviewer` on a pure-Go diff — three reviewers independently checked the typed-nil hazard it would have owned and all found it safe.

