✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-18_15-26-00.md`

**Verdict: ❌ NEEDS_CHANGES** — 2 High, 5 Medium, 2 Low, 5 Minor.

The change's intent is sound: an unrecognized `response_type` previously fell through `CreateCommandPost` with no post and no error, so surfacing it is a real improvement. The problems are *where* it enforces and *what it takes down with it*.

**The two blocking findings:**

1. **`command_response.go:90` — one invalid nested `extra_response` discards the valid main response and every sibling.** `IsValid()` returns on the first nested failure, so `CommandResponseFromJSON` returns `(nil, err)` for the whole payload. The consumer does the opposite: `HandleCommandResponse` (`app/command.go:605-631`) posts each entry independently and aggregates errors. The change's own new test demonstrates the loss. Result is a 500 instead of graceful degradation.

2. **`client4.go:5961` — the published Go client now rejects responses the server emits without validating.** `CommandResponseFromJSON` sits on both ends of a round trip, but validation was added to one. Plugin responses reach `api4/command.go:427` unvalidated, are encoded with HTTP 200, then rejected on re-parse. The validator narrowed the live path: `in_channel` is self-guarded by `Post.IsValid`, but `ephemeral` is not (`SendEphemeralPost` skips validation entirely).

**Notable Medium:** the hardcoded `len(o.Text) > 65535` contradicts the rune-based, DB-derived `maxPostSize`. I dropped this from High to Medium after validation separated two claims — the "too loose" symptom is a coherence defect, not a regression, and the genuine regression (enlarged `posts.message` column) needs a non-default deployment.

**Three things I want to flag about the process, not the code:**

- I ran the one nominated probe (neutralizing the nested check) — the test failed as predicted, confirming it's a genuine guard, and refuting two of three claimed masking scenarios in a test finding. Tree restored and verified byte-identical (sha256 + empty `git status`).
- Three reviewers independently suspected stack exhaustion via nested `extra_responses`; all three probed it empirically and all three found it bounded by `encoding/json`'s depth limit at 4999 levels. Not reported.
- One High finding was screened down to 10 and parked as pre-existing: the `ExtraResponses` post-amplification path is real but byte-for-byte unchanged by this diff. Worth filing separately.

I deviated from the skill's validation-selection rule — it nominated 9 findings; I spent validators on the 4 that could change the verdict. That's disclosed in the report header and rationale. Only the package tests were run, not the full suite.
