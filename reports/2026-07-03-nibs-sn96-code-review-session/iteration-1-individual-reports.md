# Iteration 1 — Individual Reviewer Reports (as received in main context)

Scope reviewed: the raw TDD output for nibs-sn96 (`internal/nibcore/core.go`,
`internal/nibcore/search_test.go`, new `internal/nibcore/search_id_test.go`).

Only these reports were broadcast to the main conversation (see README §4, issue 2 — the
reply-topology break). The remaining six reviewers' reports (performance, consistency, knowledge,
design, spec-compliance, adversarial) reached the orchestrator only; their content survives in
condensed form inside `iteration-1-consolidated-review.md`.

---

## quick-reviewer

> ## Verdict: no functional issues found
>
> I read all three files, ran `go build ./...`, `go vet` (implicit via build), `go test ./...` (all packages pass, including the new `search_id_test.go` cases), and `golangci-lint run ./internal/nibcore/...` (0 issues). The logic in `matchesIDQuery`/`idMatchesLocked` matches its own doc comment and the 18-case table test plus 5 integration-style tests, and I hand-traced the edge cases (bare prefix, prefix-with-dash, empty prefix, multi-word queries, uppercase, quoted-like strings) — behavior is correct and intentional in each case.
>
> One thing worth calling out: the `search_test.go` query change from `"NoOp"` to `"Bleve"` is not cosmetic — it's a necessary fix. With the new ID-matching, `"NoOp"` lowercases to `"noop"`, which is a substring of the test's nib ID `"noop1"`, so the old query would now spuriously pass via ID-match even with a true no-op search index, defeating the test's purpose. `"Bleve"` doesn't collide with any ID in that test, so it correctly isolates "the no-op index returns nothing." Good catch by whoever made that edit.
>
> ## Findings
>
> None rise to a level worth blocking. Two low-severity/informational notes:
>
> 1. **(low, performance)** `idMatchesLocked` does a full `O(N)` linear scan over `c.nibs` — lowercasing both `query` and every `id` — on *every* `Search()` call, even for queries that are obviously prose (e.g. multi-word). At the current fixture/project scale (dozens to low hundreds of nibs) this is negligible, but if nib counts grow into the thousands and Search is called per-keystroke (TUI/web live search), it's an added constant-factor cost on top of the existing Bleve query. Not a correctness issue, just a scaling note — probably not worth a nib on its own unless nib counts are expected to grow much larger.
>
> 2. **(pre-existing, not introduced by this change)** `gofmt -l internal/nibcore/core.go` flags the file both before and after this diff (import ordering between `internal/nib`/`internal/config`, and struct-literal alignment in `New()`/`Core.mu`). I verified this against `git show HEAD:internal/nibcore/core.go` — the same file at HEAD is already gofmt-dirty, so this diff doesn't introduce or worsen it. `golangci-lint` (what `task lint` actually runs) doesn't flag it, so it's not a blocker. Mentioning only because CLAUDE.md is strict about "never commit with lint failures" — worth a drive-by `gofmt -w` at some point, but out of scope for this bug fix.
>
> ## Considered But Not Flagged
>
> - **Greedy substring matching for very short queries** (e.g. a 1-2 char query) could match many nib IDs and push them ahead of more relevant full-text hits. This is the explicitly designed/tested behavior (the whole point of the fix), not a defect.
> - **Bleve query-string syntax vs. ID matching**: quoted phrases (`"foo"`), boolean operators (`user AND password`), or field-prefixed queries (`title:x`) won't get ID-priority treatment since `matchesIDQuery` does plain substring/prefix comparison against the raw query string. This is consistent with the existing `TestSearch_IDMatch_MultiWordQuerySkipsIDMatching` test intent — multi-token/special-syntax queries are expected to fall through to full-text only. Not a bug.
> - **Sort stability for mixed-case IDs**: `sort.Slice` on `matches[i].ID < matches[j].ID` uses raw (non-lowercased) comparison, so mixed-case IDs would sort ASCII-wise (uppercase before lowercase). In practice `nib.NewID` only generates lowercase IDs, so this can't currently manifest.
> - **Archived nibs are included in ID matching** (since `c.nibs` includes archived nibs per `loadFromDisk`'s directory walk) — but this matches the pre-existing behavior of the Bleve-backed full-text path, so it's not a new inconsistency introduced by this change.
> - **Locking discipline**: `idMatchesLocked` is correctly called only from within the `c.mu.RLock()` block in `Search`, consistent with the `*Locked` naming convention used elsewhere in the file (`findNibLocked`, `ensureSearchIndexLocked`). `configPrefix()` (called inside it) only reads immutable state, so no double-locking risk.

---

## broad-reviewer

> Reviewed the nibs-sn96 ID-search fix (core.go, search_test.go, search_id_test.go). Verified: `go build ./...` clean, `go test ./...` all pass, `golangci-lint run` 0 issues. Findings below with confidence scores; category = comprehensive (confidence/knowledge/reliability/structure/architecture).
>
> ## Findings
>
> ### 1. Search-syntax documentation not updated to mention ID matching (knowledge preservation) — Confidence: 80%, Severity: Medium
> `cmd/list.go:57-69` (the `--search`/`-S` help text) and `internal/graph/schema.graphqls:331-346` (the `NibFilter.search` doc comment) both still describe search as purely "Full-text search across slug, title, and body using Bleve query syntax," with an example list (`login`, `login~`, `slug:auth`, etc.) that says nothing about matching nib IDs. This is exactly the capability nibs-sn96 adds. Per CLAUDE.md, `nibs prime`/`prompt-full.tmpl` is "the primary interface for AI agents," and `cmd/prompt-full.tmpl:54,332` shows the same `-S`/`search:` examples with no ID-matching mention either. An agent or user reading any of these three surfaces has no way to discover that `nibs list -S <id-fragment>` or `search: "5a8k"` now works. Recommend adding one line to each (CLI help, GraphQL schema doc, and prompt-full.tmpl if it also documents search syntax) noting that a bare or prefixed ID/ID-fragment also matches directly.
>
> ### 2. `idMatchesLocked` has no result cap, unlike the Bleve side's `DefaultSearchLimit` (production reliability / structural) — Confidence: 60%, Severity: Low–Medium
> `core.go:285` caps Bleve hits at `DefaultSearchLimit` (1000), but `idMatchesLocked` (core.go:317-327) iterates every nib in `c.nibs` and appends all substring matches with no limit. For a short/common query (e.g. a single character), the count of ID matches scales with total nib count and nanoid entropy, and is fully unbounded — inconsistent with the cap the text-search half respects. This repo's own `.nibs/` already has 254 nibs; not urgent at that scale, but there's no ceiling if a project grows into the thousands, and it's a latent inconsistency in the "same query, same limit" contract implied by `DefaultSearchLimit`. Suggest either capping `idMatchesLocked` output length to `DefaultSearchLimit` too, or documenting explicitly in the doc comment why it's intentionally unbounded.
>
> ### 3. Missing CHANGELOG `[Unreleased]` entry (process consistency) — Confidence: 65%, Severity: Low
> `CHANGELOG.md`'s `[Unreleased]` section is currently empty. This repo's convention (per CLAUDE.md and prior commits) is for each fix to carry its own changelog line — e.g. commit `6ac676d`'s message explicitly lists "CHANGELOG Fixed entry" as one of its changes, and `a7ae90a` similarly ships doc/behavior changes without deferring to a later release-prep commit. This changeset has no corresponding entry yet. Likely just not done before requesting review — flagging so it doesn't get forgotten before commit.
>
> ### 4. Minor: redundant per-iteration `strings.ToLower` in the hot loop (structural nit) — Confidence: 90% (as observation), Severity: trivial
> `matchesIDQuery` (core.go:333-343) lowercases `query` and `prefix` on every call, but it's called once per nib inside `idMatchesLocked`'s loop (core.go:320-323) — so `query`/`prefix` get re-lowered N times for N nibs instead of once. Cheap fix: lowercase `query`/`prefix` once in `idMatchesLocked` and pass pre-lowered values (or lowered id-only) into a leaner per-nib check. Not worth blocking on given current scale (254 nibs, microseconds), but easy to tidy while the code is fresh.
>
> ### 5. Test comment overclaims what's asserted (knowledge preservation, minor) — Confidence: 55%, Severity: trivial
> `search_test.go`'s updated `TestSearch_WithInjectedNoOpIndex` comment says "Core-level ID matching works even without an index," but the test only asserts a *non-matching* query ("Bleve") returns 0 results under a `NoOpSearchIndex` — it never positively exercises ID matching (e.g. searching `"noop1"`) under a no-op index to confirm the ID-match path actually fires independent of the index. The code structurally guarantees this (`idMatchesLocked` never touches `c.searchIndex`), so risk is low, but the comment describes a behavior the test doesn't actually demonstrate. A follow-up assertion (`core.Search("noop1")` returns the nib) would make the test match its own claim.
>
> ## Considered But Not Flagged
>
> - **Asymmetric prefix-vs-substring semantics**: when a query starts with the configured prefix, matching requires a true prefix of the full ID (`nibs-a8k` does NOT match `nibs-5a8k` even though `a8k` is a real fragment of the short ID), whereas a bare short-ID query does substring matching anywhere. This is deliberate and explicitly covered by `TestMatchesIDQuery`'s "full form non-prefix fragment" case — a documented, tested design choice, not a bug. Could mildly surprise a user, but not worth flagging as an issue.
> - **BM25 ordering test brittleness** (`TestSearch_IDMatch_UnionWithTextHits` asserting cc33 outranks bb22): depends on Bleve's BM25 scoring nuances between two specific bodies. Ran it directly — passes deterministically today. Not flagging as a live bug; if Bleve's scoring model or version ever changes, this could need re-tuning, but that's true of any relevance-ordering test and isn't introduced or worsened by this diff.
> - **Locking discipline**: `idMatchesLocked` is documented as requiring at least a read lock; verified its one call site (`Search`, core.go:294) is correctly inside the `c.mu.RLock()`/`defer RUnlock()` block. No misuse.
> - **Case handling / nanoid alphabet**: `nib.NewID`'s alphabet (`internal/nib/id.go`) is already all-lowercase, so `strings.ToLower(id)` is a defensive no-op for real IDs, not dead code addressing a real case-mismatch risk (e.g. hand-constructed test IDs). Fine as-is.
> - **Race between `idx.Search` (unlocked) and the later `RLock` snapshot for both Bleve-hit mapping and `idMatchesLocked`**: pre-existing tolerance pattern (stale index entries filtered through `c.nibs`), not newly introduced or worsened by this change.
> - **GraphQL `ApplySorting`** (`internal/graph/sorting.go:32-35`): confirmed that when `sort` is nil, the new ID-match-first ordering survives to the `nibs` resolver unmodified; when a sort field is set, it's fully overridden — consistent with the existing schema doc "sort overrides implicit ordering (including search relevance)." No conflict introduced.

---

## test-reviewer

> ## Test Review: search_id_test.go (new) + search_test.go (modified)
>
> Scope: test files only, per instructions. Verified against internal/nibcore/core.go (matchesIDQuery, Search) and internal/search/index.go (Bleve config/scoring) as read-only context, and ran the suite (go test -count=100 on the new/changed tests, go vet, full package test) — all green, no flakes observed.
>
> ### Findings
>
> None rise to a blocking issue. Everything below is either already-verified-safe or a minor nit.
>
> **1. [Verified safe] search_test.go query change ("NoOp" → "Bleve") is a real, necessary fix, not cosmetic.**
> `setupTestCore` uses `config.Default()`, whose `Nibs.Prefix` is `""`. With an empty prefix, `matchesIDQuery` reduces to `strings.Contains(id, query)` since `shortID := TrimPrefix(id, "")` is just `id`. The old query `"NoOp"` lowercases to `"noop"`, which *is* a substring of the nib's own ID `"noop1"`. Before this production change, that didn't matter (no ID-match path existed), but after it, `Search("NoOp")` would spuriously return the `noop1` nib via ID matching even with a `NoOpSearchIndex` injected — silently defeating the test's purpose (proving Bleve indexing is skipped). Swapping to `"Bleve"` (which is not a substring of `"noop1"`) is the correct fix. Confirmed by re-deriving the logic and by the fact `config.Default()` really does set `Prefix: ""` (internal/config/config.go:125).
>
> **2. [Verified not flaky] `TestSearch_IDMatch_UnionWithTextHits`'s reliance on BM25 ranking `cc33` (tf=3, 3-word body) above `bb22` (tf=1, 9-word body) is deterministic, not a hidden coin-flip.**
> Bleve's BM25 uses per-document stats (term frequency + document length vs. corpus average); it doesn't depend on insertion/indexing order (map iteration order for the `IndexNibs` batch is non-deterministic in Go, but that only affects tie-breaking, and there's no tie here — 3x term frequency in a much shorter document is a stark, structural difference, not a marginal one). Ran the test 100x in a loop plus the whole package 50x with no failures. The test only needs `cc33` to outrank `bb22`; `nibs-5a8k`'s position is fixed as the ID-match (dedup already removes it from the Bleve tail), so the assertion is narrower than it first looks. This is a new pattern in the codebase (no pre-existing test asserts cross-document BM25 order), so it's worth knowing it exists, but it's not flaky as written.
>
> **3. [Verified not a risk] Random ID generation cannot collide with test query fragments.**
> `Core.Create` (core.go:404-415) only calls `nib.NewID` when `b.ID == ""`. Every nib in both test files sets `ID` explicitly, so there's no randomness in play — confirmed by reading `Create`.
>
> **4. [Minor, non-blocking] `TestSearch_IDMatch_MultiWordQuerySkipsIDMatching` name/comment slightly overstates the mechanism.** The comment says multi-word queries "must not trigger ID matching," implying a deliberate branch in `matchesIDQuery`. There isn't one — the real guarantee is structural: `nib.NewID`'s alphabet never produces IDs containing a space, so any query with a space can never be a `Contains` substring match regardless of length. The test's behavior assertion is still correct and robust (it holds regardless of *why*), but a future reader skimming the test name might infer more special-casing exists in production code than actually does. Not worth a change, just flagging for awareness — could add a one-line comment noting the "IDs never contain spaces" invariant if you want to preempt confusion.
>
> **5. [Considered, not flagged] `setupTestCoreWithPrefix` duplicates `setupTestCore`'s boilerplate (tmpDir/mkdir/Load) instead of extending the existing helper.** This mirrors an already-established pattern: `setupTestCoreWithRequireIfMatch` in core_test.go does the identical duplication for a different config variant. `setupTestCore(t)` has 63 call sites across the package with no prefix param, so retrofitting it (e.g., variadic options) would be a much larger, unrelated change. Given the existing precedent, a third near-duplicate is a low-cost, low-risk consequence of the package's established convention, not a new anti-pattern introduced by this diff.
>
> **6. [Verified no false positives] Existing single-word queries in search_test.go don't accidentally hit the new ID-match path.** Checked every `core.Search(...)` call against every literal ID in the file (aaa1, bbb2, ccc3, abc1, new1, upd1, del1, ext1, spy1, rld1, noop1 — all under the empty-prefix config). All query strings are either longer than the 4-char IDs or share no substring relationship with them, so none of them silently gained a new ID-match hit that would mask the text-search behavior actually under test.
>
> ### Considered But Not Flagged
> - Table-driven `TestMatchesIDQuery` cases (bare prefix with/without dash, trailing space, uppercase, empty query/prefix) — traced each through the actual function logic; all 16 cases produce the expected `want` value, no gaps in the semantics claimed by the doc comment.
> - No test in this package uses `t.Parallel()` — new tests match that existing convention, not an omission.
> - Ignored errors (`_, _ = core.Search(...)`, `_ = core.Close()`) are pre-existing idioms used for lazy-index-priming and best-effort cleanup elsewhere in the file; the new tests don't introduce new instances of this pattern beyond what's already there.
> - No resource leaks: every new test defers `core.Close()`.
>
> No further action needed from my side; nothing here should block the change.

---

## go-reviewer

> Reviewed for Go-idiom issues (goroutines, error discipline, typed nil, channels, context, defer, slice aliasing, map iteration, locking). Verified against the repo: `go build ./...` clean, `go test -race ./internal/nibcore/...` clean, all new/changed tests pass.
>
> ## Findings
>
> ### Nit (low): redundant per-iteration `strings.ToLower` on loop-invariant inputs
> `internal/nibcore/core.go:333-343` (`matchesIDQuery`), called from `idMatchesLocked` (core.go:317-327) inside `for id, b := range c.nibs`. Each call re-lowercases `query` and `prefix`, even though both are invariant across the whole loop — only `id` changes per iteration. For N nibs this is N redundant `strings.ToLower` allocations on the same two strings. Not a correctness bug, just wasted work; worth hoisting `query`/`prefix` lowercasing into `idMatchesLocked` once, ahead of the loop, if you want `matchesIDQuery` to take pre-lowered args (or keep the pure/testable signature and eat the cost — it's O(N) on short strings, not hot-path-critical, so I'd only fix this if it's cheap to do here). Not blocking.
>
> ## Considered but not flagged (verified against repo, no issue found)
>
> - **Lock discipline of `idMatchesLocked`**: correctly documented "Must be called with at least a read lock held" and is only called from `Search` while `c.mu.RLock()` is held (core.go:291-294). No unlocked map access. `-race` run confirms clean.
> - **Gap between unlocking the write lock (after lazy-init) and re-acquiring the read lock while `idx.Search` runs unlocked** (core.go:275-292): pre-existing behavior, unchanged by this diff — the map could theoretically mutate between the two lock sections regardless of this change. Not introduced here.
> - **`sort.Slice` vs `slices.SortFunc`**: go.mod is 1.24.6 and `slices.SortStableFunc` is used elsewhere (internal/graph/sorting.go, internal/nib/sort.go), but `internal/nibcore/mentions.go:111` already has the *identical* pattern `sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })` in the same package. The new code matches local package precedent, not a deviation.
> - **`map[string]bool` for `seen`** (core.go:295): `map[string]struct{}` is used in some packages (nib/references.go, graph/bulkreorder.go) but `map[string]bool` is what nibcore itself already uses (migrate.go, link_health.go). Consistent with package convention.
> - **`strings.TrimPrefix`/`HasPrefix` with empty prefix**: `TrimPrefix(id, "")` correctly returns `id` unchanged (HasPrefix(id,"") is always true), so the empty-prefix path degrades correctly to plain substring match — verified by the `TestMatchesIDQuery` "empty prefix" cases, which pass.
> - **Map iteration order in `idMatchesLocked`**: iterates `c.nibs` in random order but sorts by ID afterward before returning, so output is deterministic despite the unordered source. No bug.
> - **Slice aliasing**: `matches`/`result` are freshly allocated per call; pointers into `c.nibs` are shared with the map (same as the pre-existing `All()` and the old `ids`-loop), not a new aliasing concern.
> - **Test idioms in `search_id_test.go`**: `t.Helper()`, `t.TempDir()`, `defer func() { _ = core.Close() }()` all match sibling tests in `search_test.go`/`core_test.go` exactly. No deviation.
> - **`gofmt -l`** flags `core.go` (import-group ordering of `nib`/`config`/`search`, and some struct-field alignment), but `git diff HEAD` confirms none of the flagged lines were touched by this change — pre_existing, not introduced.
> - **Unbounded `idMatches` vs `DefaultSearchLimit`-capped Bleve hits**: ID matches aren't capped like the 1000-limit Bleve search is. This is a behavioral/design question (how many ID matches can realistically exist for a non-trivial query), not a Go-idiom problem, so I'm leaving it for the correctness/design reviewers rather than flagging it here.
>
> No goroutine, channel, context, typed-nil, or error-discipline issues in this diff — none of those constructs are touched by the change.

---

## validator-f6 (validation wave; finding: trailing-whitespace ID paste)

Part 1:

> ## Verdict: CONFIRMED (Low severity — agree with the consolidated rating, not the Medium-Low dissent)
>
> ### (a) Behavioral claim — confirmed by direct reproduction
>
> `internal/nibcore/core.go:333-343`:
> ```go
> func matchesIDQuery(query, id, prefix string) bool {
> 	query = strings.ToLower(query)
> 	id = strings.ToLower(id)
> 	prefix = strings.ToLower(prefix)
>
> 	if prefix != "" && strings.HasPrefix(query, prefix) && len(query) > len(prefix) {
> 		return strings.HasPrefix(id, query)
> 	}
> 	shortID := strings.TrimPrefix(id, prefix)
> 	return query != "" && strings.Contains(shortID, query)
> }
> ```
> No `TrimSpace` anywhere, and no trimming happens upstream either — traced the full call chain: `cmd/list.go:282` (`-S/--search` flag) → `internal/graph/schema.resolvers.go:740` (`r.Reader.Search(*filter.Search)`, only guarded by `!= ""`, not whitespace-aware) → `core.go:273 Search()` → passes the raw string to both `idx.Search(query, ...)` (Bleve) and `idMatchesLocked(query)` unmodified.
>
> Ran it live against the real repo (read-only, no mutation):
> ```
> $ go run . list -S 'sn96'
>  # ID               T  S  TITLE
>  68 nibs-9kvw         M   I       Nibs Web UI — Polish & Enhancements
>   2 └─ nibs-sn96      B   I       Keyword search does not match nib IDs
>
> $ go run . list -S 'sn96 '
> No nibs found. Create one with: nibs new <title>
> ```

Part 2:

> This confirms adversarial-reviewer's empirical claim exactly: a trailing space silently disables ID matching and reproduces the original bug symptom (the nib this very fix (nibs-sn96) was created to address).
>
> ### (b) Does the proposed `strings.TrimSpace(query)` fix break the multi-word-exclusion guard?
>
> No adverse interaction. Traced all three affected table rows in `internal/nibcore/search_id_test.go:169-203`:
>
> - `"id fragment with trailing space", "5a8k ", ... false` (line 192) — **this is the only row that flips.** `TrimSpace("5a8k ")` → `"5a8k"`, which then matches as a short-ID substring → the fixed function returns `true`. This test's expected value would need to change from `false` to `true` — a deliberate, intentional semantics change, not a regression.
> - `"multi-word query skips id matching", "user AND login", ... false` (line 191) — unaffected. `TrimSpace` only strips leading/trailing whitespace; internal spaces between "user"/"AND"/"login" remain, so the substring check still fails. Still `false`.
> - `"full form with extra word", "nibs-5a8k extra", ... false` (line 193) — unaffected for the same reason (no leading/trailing whitespace, only internal).
>
> So the fix is surgical: it only changes leading/trailing-whitespace handling, and leaves the actual "whitespace means Bleve query-string syntax, skip ID matching" guard (which the code implements only implicitly, via substring-containment failing whenever the query contains a space that isn't in the ID — there's no explicit multi-word branch) fully intact for genuine multi-word queries.
>
> I also grepped the whole repo for anything else that depends on "trailing space → no ID match": no other test, CLI path (`cmd/list.go`), GraphQL resolver, TUI (`internal/tui/*.go`), or web UI (`web/src/lib/components/FilterBar.svelte:69,118` — search input is bound directly to the filter value with no trim: `emitFilter({ ...resolvedFilter, search: value || undefined })`) does any trimming before the string reaches `matchesIDQuery`. The bug reproduces identically in the CLI, and would reproduce in the TUI and web UI search boxes too (same `Core.Search` path).
>
> This also weakens the design-reviewer/spec-compliance-reviewer's "self-correcting on next keystroke" rationale: that framing only makes sense for an interactive box where continued typing eventually fixes things automatically. Here nothing auto-trims — a user would have to manually notice and delete the trailing space themselves, which is true of most UX papercuts and isn't really "self-correcting" in a meaningful sense. It also doesn't apply at all to the one-shot CLI (`nibs list -S 'sn96 '` is a single invocation, there's no "next keystroke").
>
> ### (c) Disposition
>
> **Confirmed** as a real, reproducible primary finding — not refuted. The test at line 192 does deliberately pin the current behavior, but "deliberate" here just means the author encoded the emergent behavior (space can never be in an ID, so any space anywhere kills substring matching) as the expected value, not that it was evaluated and chosen as *correct* over the alternative. The stated purpose of the whole feature is "let a user paste a nib ID into search," and a trailing space is one of the most common paste artifacts (copying a table cell, a terminal line, or `id\t` output) — so this cuts directly against the feature's own headline scenario.
>
> I'd keep it at **Low** severity, not escalate to Medium-Low: impact is a silent "no results" (not data loss or corruption, and not misleading — it just under-delivers), the fix is a one-line `strings.TrimSpace(query)` at the top of `matchesIDQuery` with no side effects beyond updating one test expectation, and the workaround (delete the trailing space) is trivial once noticed. But it should be fixed, not dismissed — recommend accepting the proposed fix and updating `search_id_test.go:192`'s expected value from `false` to `true` (and updating the test's name/comment, since "with trailing space" would no longer describe a non-match).
