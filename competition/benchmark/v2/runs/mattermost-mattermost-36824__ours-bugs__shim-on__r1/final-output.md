No prior reviews exist, so the Recurring Findings step is skipped.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-17_16-08-20.md`

## Verdict: ❌ NEEDS_CHANGES — 2 High, 1 Medium, 1 Minor

All three primary findings were independently confirmed by a validation wave.

**#1 🟠 High — `server/public/model/command_response.go:72`**
Validation was placed *inside* `CommandResponseFromJSON`, but that deserializer is also how the Go SDK parses the **server's own** API response (`client4.go:5961`, `:5982`). There's no matching check on the write path — `api4/command.go:428` encodes whatever `App.ExecuteCommand` returned, and a plugin's `ExecuteCommand` hook crosses a gob/net-rpc boundary with an unconstrained `ResponseType`, while `CreateCommandPost` (`app/command.go:73-84`) falls through both branches and returns success for an unrecognized value. Result: the command runs, the post is created, the server returns 200, and `Client4.ExecuteCommand` returns `failed to decode command response`. The type can't round-trip its own output. No built-in command triggers it today; any plugin can.

**#2 🟠 High — `command_response.go:85`**
`maxLength := 65535` is an undeclared local that duplicates the exported `PostMessageMaxBytesV2` in the same package; it counts bytes via `len()` where every sibling validator counts runes via `utf8.RuneCountInString` (`post.go:508`, `terms_of_service.go:32`, `channel.go:324`); and it puts a hardcoded ceiling *upstream* of the configurable one computed from the DB column size (`post_store.go:2658`), with no admin override. Ephemeral responses — never length-checked before (`SendEphemeralPost` does no validation) — are now capped too. The validator argued for Medium since the regression needs an enlarged `Posts.Message` column to bite; I kept High per the highest-finder rule and recorded the dissent in the report.

**#3 🟡 Medium — `command_response.go:95`**
Recursing into `ExtraResponses` makes the parse all-or-nothing: one bad nested entry now discards a valid main message, yielding a 500 (`app/command.go:597`) or 400 (`webhook.go:113-116`) with no post. That contradicts `HandleCommandResponse` (`app/command.go:605-637`), which deliberately tolerates per-entry failures via `lastError` — a contract this diff doesn't touch but now runs ahead of. No diagnostic says which entry failed. The new test at `command_response_test.go:171-182` encodes the behavior.

**Minor** — both new `AppError` translation IDs are absent from `server/i18n/en.json`; tiered down because the raw ID only reaches logs and dev-mode `detailed_error`.

Two caveats on the run itself, both in the report: `test-reviewer` was **dropped by the `bugs` preset's roster cap of 4** even though its hard gate matched and half the diff is test code — `bugs roster=6` would restore it. And `adversarial-reviewer` died twice on transient API 529s before succeeding, so its three findings come from a single run at its self-declared "quick" depth tier.
