# Iteration 3 — Individual Reviewer Reports (as received in main context)

Scope reviewed: the round-2 fix output (charset gate, `normalizeIDQuery` extraction, uppercase test,
helper dedup, ordering-doc rewording, `DefaultSearchLimit`/`NoOpSearchIndex` doc corrections) across
10 files. Reviewers were instructed to focus on regressions/new issues from that round only.

Reports from **9 of 10** reviewers reached the main context (all except `rev-spec`). No consolidated
file exists for this iteration (orchestrator killed mid-write; main context triaged directly from
these reports). Several reviewers re-sent their reports in JSON when the stalled orchestrator asked
for resends — where both versions arrived, the fuller original is reproduced and the resend noted.

**Main-context triage outcome:** 12 fixes applied (1 TDD), 1 deferred (`nibs-es0b`), 3 skipped.
The headline finding (exact foreign-ID lookup broken by the charset gate) was found independently by
rev-broad, rev-design, rev-adversarial, and rev-knowledge — rev-broad and rev-adversarial with
executed repros; rev-design and rev-knowledge by independent hand-trace (as reproduced below).

---

## rev-perf (performance-reviewer)

> Reviewed the diff plus search_id_test.go. One in-scope regression, everything else in this round is clean.
>
> ## Finding 1 (regression, this round) — isIDFragment recomputed per nib instead of once per Search call
>
> **Location:** `internal/nibcore/core.go`, `matchesLoweredIDQuery` (line 396) called from `idMatchesLocked`'s loop (line 325).
>
> `idMatchesLocked` already hoists the two genuinely per-call values correctly — `normalizeIDQuery(query)` and `prefix := strings.ToLower(c.configPrefix())` are computed once before the `for id, b := range c.nibs` loop. But the new charset gate is not:
>
> ```go
> func matchesLoweredIDQuery(query, id, prefix string) bool {
> 	id = strings.ToLower(id)
> 	if prefix != "" && strings.HasPrefix(query, prefix) && len(query) > len(prefix) {
> 		return strings.HasPrefix(id, query)
> 	}
> 	shortID := strings.TrimPrefix(id, prefix)
> 	return len(query) >= minIDFragmentLen && isIDFragment(query) && strings.Contains(shortID, query)
> }
> ```
>
> `isIDFragment(query)` depends only on `query`, which is loop-invariant across all N nibs, yet it's called once per nib inside the hot loop (short-circuited only by the query-length check, which is O(1)). It does a full O(len(query)) byte scan every time. Since `Core.Search` runs on every keystroke of the web UI's keyword box, and there's no cap on query length before this path, this turns what should be O(len(query) + N) work into O(len(query) × N) for every single search — including plain multi-word full-text queries that were never going to match any ID (isIDFragment correctly returns false for those, but pays the scan cost N times instead of once).
>
> At repo sizes in scope (hundreds to low-thousands of nibs) and typical query lengths this is small in absolute terms, but it's a pure, free-to-fix regression on the hottest path in the system, so I'd still fix it rather than defer it.
>
> **Suggested fix:** hoist the fragment check out of the loop in `idMatchesLocked`, e.g.:
>
> ```go
> func (c *Core) idMatchesLocked(query string) []*nib.Nib {
> 	query = normalizeIDQuery(query)
> 	prefix := strings.ToLower(c.configPrefix())
> 	fragmentOK := len(query) >= minIDFragmentLen && isIDFragment(query)
> 	var matches []*nib.Nib
> 	for id, b := range c.nibs {
> 		if matchesLoweredIDQueryPrepared(query, id, prefix, fragmentOK) {
> 			matches = append(matches, b)
> 		}
> 	}
> 	...
> }
> ```
>
> with `matchesLoweredIDQuery` (used by the single-shot `matchesIDQuery` test seam) kept as-is or reimplemented in terms of the new helper by computing `fragmentOK` inline. Either way, `isIDFragment` should execute once per `Search` call, not once per nib.
>
> Not flagging: the `strings.HasPrefix(query, prefix) && len(query) > len(prefix)` condition inside the same function has the identical loop-invariant problem, but that branch predates this round (only the `isIDFragment` gate was added now) — mentioning it only because hoisting both together is basically free once you're restructuring this function; up to you whether to fold it in or leave it as a separate pre_existing item.
>
> ## Everything else checked, no issues
>
> - `normalizeIDQuery` extraction (item 2): pure refactor, called once per `Search`/`idMatchesLocked` invocation and once in the `matchesIDQuery` test seam — no new allocation or hot-path cost versus the prior inline form.
> - `strings.ToLower(id)` per nib in `matchesLoweredIDQuery`: necessary (id varies per nib, not hoistable), and Go's stdlib `ToLower` has an ASCII fast path that returns the original string with zero allocation when there's no uppercase — true for the vast majority of generated nib IDs. Pre-existing anyway, not part of this round.
> - `configPrefix()`: nil-check + field read, no lock, no I/O — confirmed cheap, and only called once per `Search`, not per nib.
> - Sort + cap in `idMatchesLocked`: unbounded `matches` slice is sorted before capping to `DefaultSearchLimit`, but its size is bounded by total nib count (accepted O(n) design from earlier iterations) — not new, not re-litigating.
> - `Search()`'s union/dedup logic (`seen` map, `idMatches` + `ids` merge): unchanged this round, falls under the accepted union design.
> - Doc-only changes (schema.graphqls, models_gen.go, cmd/list.go, cmd/prompt-full.tmpl, CHANGELOG.md, comment updates in search_index.go/reprefix.go): no runtime impact.
> - `search_id_test.go`: `TestIDMatchesLocked_CappedAtDefaultSearchLimit` correctly populates `core.nibs` directly instead of going through `Create` for 1005 entries, avoiding needless index/disk overhead in the test itself — no concerns.
>
> Net: one hoist to make, everything else in this round is performance-neutral.

*(A JSON-formatted resend of the same report arrived later during the orchestrator's resend request;
content identical, labeled PERF-1.)*

---

## rev-quick (quick-reviewer)

> Reviewed the round-3 diff (charset gate, normalizeIDQuery extraction, new tests, doc rewordings). Verified with build, `go vet`, `golangci-lint run` (0 issues), and `go test ./internal/nibcore/...` (all pass, including all new tests). No bugs or regressions found in the primary review target.
>
> Findings by item:
>
> 1. **isIDFragment charset gate** — correct. `internal/nib/id.go:11` confirms `idAlphabet = "0123456789abcdefghijklmnopqrstuvwxyz"`, exactly `[0-9a-z]` with no exclusions, matching the gate's charset check byte-for-byte. The gate only guards the substring branch of `matchesLoweredIDQuery`; the prefix branch (`HasPrefix(id, query)`) intentionally bypasses it, as documented, and can't be tricked into a false match since real IDs never contain the operator/whitespace characters the gate excludes.
>
> 2. **normalizeIDQuery extraction** — no asymmetry. Both the production path (`idMatchesLocked` → `matchesLoweredIDQuery`) and the test seam (`matchesIDQuery` → `matchesLoweredIDQuery`) funnel through the same underlying function, so drift between the two is structurally impossible now, not just coincidentally absent.
>
> 3. **TestSearch_IDMatch_UppercaseQuery** — valid, exercises case-insensitivity through the real `Core.Search` entrypoint rather than only the `matchesIDQuery` unit-test seam. Passes.
>
> 4. **Deduped test helpers** — `mustLoadPrefixedCore` (`mentions_test.go:17`, returns `(*Core, string)`) and `rawIDList` (`mentions_test.go:716`, `[]*nib.Nib -> []string`) match how `search_id_test.go` calls them exactly; compiles and runs clean, no redeclaration.
>
> 5. **Reworded ordering claims** (schema.graphqls / models_gen.go / cmd/list.go / prompt-full.tmpl / CHANGELOG) — verified against actual resolver code, not just consistency between docs. `schema.resolvers.go` runs `ApplySorting` unconditionally after `Core.Search`, and it does a global `slices.SortStableFunc` with no awareness of the ID-match/full-text grouping — so an explicit sort genuinely discards that grouping, confirming the "overrides" wording. `cmd/list.go`'s `buildNibSort` defaults to `NibSortFieldOrder` (never nil), so `nibs list` always resorts — confirming "interleaved by the list's sort order" is accurate, not just hedge-wording. Web UI (`queries.ts:145`) also hardcodes a default sort, same story.
>
> 6. **DefaultSearchLimit / NoOpSearchIndex doc corrections** — accurate: each leg (`idx.Search(query, DefaultSearchLimit)` and `idMatchesLocked`'s own cap) is capped independently, so a combined result can hold up to 2x the limit, and `NoOpSearchIndex` only silences the full-text leg since `idMatchesLocked` runs unconditionally against `c.nibs` regardless of which `SearchIndex` is injected.
>
> One incidental, out-of-scope note: `gofmt -l` flags `internal/nibcore/core.go` (import ordering: `nib` before `config`; `mu`/`nibs` field alignment) and `internal/nibcore/search_index.go` (method receiver alignment on the `NoOpSearchIndex` one-liners). I checked — both predate this round entirely; `git show HEAD:<file> | gofmt -l` flags the same files, so this isn't something introduced by the search-ID work and `golangci-lint run` doesn't catch it (gofmt/gofumpt isn't in the enabled linter set). Not blocking, but worth a cheap drive-by fix (`gofmt -w`) whenever someone's next in these two files, since they're already in scope this iteration.
>
> No other issues found.

*(A JSON resend with a fuller `considered_but_not_flagged` list also arrived; notable additions: the
prefix branch bypassing the gate is unexploitable; multi-hyphen custom prefixes traced safe; byte-wise
`isIDFragment` safe for UTF-8 input.)*

---

## rev-go (go-reviewer)

> Reviewed the diff plus search_id_test.go for Go idiom issues (goroutines, error discipline, typed nil, channels, context, defer, slice aliasing, byte-vs-rune, lock discipline). `go vet ./internal/nibcore/...` and `golangci-lint run ./internal/nibcore/...` both report 0 issues. Overall this is clean, idiomatic code. One real finding, everything else is either verified-safe or informational.
>
> **1. [Suggestion, low severity] Test-only lock bypass — search_id_test.go:198, 222-223**
> `core.nibs[id] = &nib.Nib{ID: id}` writes directly into the map with no `core.mu` held, in both `TestIDMatchesLocked_CappedAtDefaultSearchLimit` and `TestIDMatchesLocked_ForeignPrefixIDs`, before taking `core.mu.RLock()` for the `idMatchesLocked` call itself. Not a live race today — I checked `mustLoadPrefixedCore`/`Core.Load()`: `Load()` never starts a goroutine (only `Watch()` does, and these tests never call it), so nothing else touches `c.nibs` concurrently, and the repo's `Taskfile.yml` doesn't run tests with `-race` anyway. But it silently opts out of the mutex discipline the type documents everywhere else (e.g. `mentionIdx`'s "Guarded by c.mu" comment), with no note explaining why it's safe. Suggest either wrapping the population in `core.mu.Lock()/Unlock()` or adding a one-line comment ("single-goroutine test, no watcher started") so it doesn't get copy-pasted into a context where it would actually race.
>
> **2. [Verified safe — not a bug] byte-vs-rune in `isIDFragment` — core.go:362-370**
> You specifically flagged whether the byte-wise `[0-9a-z]` scan over a `strings.ToLower`'d query handles multi-byte expansions correctly (e.g. İ U+0130). I checked this empirically rather than assuming:
> - Go's `strings.ToLower("İ")` actually collapses U+0130 to plain ASCII `i` (single byte) — Go's simple case folding doesn't do the Turkish-locale two-codepoint expansion (that requires `golang.org/x/text/cases` with a language tag, not used here). Confirmed by running it.
> - Even hypothetically, it wouldn't matter: UTF-8 continuation bytes are always ≥0x80 and lead bytes for multi-byte sequences are always ≥0xC0 — neither can ever equal a byte in `'0'-'9'` (0x30-0x39) or `'a'-'z'` (0x61-0x7A). So a multi-byte rune can only ever cause `isIDFragment` to correctly return `false` (reject the whole query), never a false-accept. Byte-wise and rune-wise scanning are equivalent for this specific ASCII-allowlist check.
> No action needed here.
>
> **3. [Informational only, not a finding] `sort.Slice` vs `slices.SortFunc` — core.go:329**
> This mirrors the exact same pattern already at `internal/nibcore/mentions.go:111` (`sort.Slice(out, func(i, j int) bool { return out[i].ID < out[j].ID })`) for the same "sort nibs by ID" task — so it's consistent with this file's existing local convention, not a new regression. (Codebase overall is inconsistent — `internal/graph/sorting.go` and `internal/nib/sort.go` use `slices.SortStableFunc` — but that's pre_existing and outside this diff's blast radius.)
>
> **4. [Trivial, optional] Minor per-nib `strings.ToLower(id)` — core.go:390**
> `matchesLoweredIDQuery` lowercases `id` on every call inside `idMatchesLocked`'s per-nib loop, even though IDs from `nib.NewID` are always lowercase (`idAlphabet = "0123456789abcdefghijklmnopqrstuvwxyz"`, validated lowercase prefixes). This is deliberate defensive normalization for unvalidated/legacy filenames (covered by the `ForeignPrefixIDs` test), not a bug — just an O(N) ToLower per `Search()` call. Negligible at this project's scale (file-based local issue tracker), not worth optimizing.
>
> Other checks, all clean: map iteration in `idMatchesLocked` is nondeterministic but the subsequent `sort.Slice` on `.ID` makes output fully deterministic regardless (correctly documented as intentional — "cap after sorting"); slice aliasing on `matches = matches[:DefaultSearchLimit]` is safe (fresh local slice, no other holder of the backing array); `Search()`'s two-phase locking (`Lock`→lazy-init→`Unlock`→`idx.Search` outside lock→`RLock`) is unchanged from before this diff, so any TOCTOU characteristics there are pre_existing, not introduced now; no goroutines/channels/context touched anywhere in this round; error handling in the new helpers is a no-error design (pure in-memory match), consistent with sibling code.
>
> The `search_test.go` change (query `"NoOp"` → `"Bleve"` in `TestSearch_WithInjectedNoOpIndex`) is a correct, necessary fix, not just cosmetic — I traced it: the nib's ID there is `noop1`, and the old query `"NoOp"` lowercases to `"noop"`, which is a valid ≥2-char ID fragment and *would* now substring-match `noop1` via the new ID-match leg even with a no-op search index, silently breaking the test's intent. `"bleve"` doesn't collide with any test ID, so it isolates what the test is actually checking.

*(A JSON resend of the same report also arrived.)*

---

## rev-test (test-reviewer)

> Reviewed only the round-3 delta as instructed. Verdict: no false-positive or "cannot fail" defects in the new tests — I traced each new/changed assertion against the actual production logic (`idMatchesLocked`, `isIDFragment`, `matchesLoweredIDQuery`, `normalizeIDQuery`) and against `configPrefix()`/`setupTestCore`/`mustLoadPrefixedCore` to confirm the fixtures produce the claimed behavior, not an accidental pass. One accuracy nit in a test comment, plus one pre-existing flakiness risk worth flagging (not part of this round).
>
> ## New items in this round — all sound
>
> **TestSearch_IDMatch_UppercaseQuery** (search_id_test.go:141-164): Genuinely exercises case-folding through `Core.Search`, not just the `matchesIDQuery` unit seam. Verified it would actually fail without the `normalizeIDQuery` lowercasing: an unlowered query "5A8K" fails `isIDFragment` (uppercase letters are outside `[0-9a-z]`), so the test has real detection power, not a vacuous pass. Title/Body text don't contain "5a8k", so the full-text leg can't contribute a false match either.
>
> **TestIDMatchesLocked_ForeignPrefixIDs** (search_id_test.go:215-256) + the two new **TestMatchesIDQuery** rows: Traced all three subtests by hand against `matchesLoweredIDQuery` with prefix `"nibs-"`. Confirmed each assertion is load-bearing: e.g. the "-42" negation case only returns `nil` because `isIDFragment` rejects the hyphen — if that charset gate regressed to allow hyphens, `Contains("task-42", "-42")` is true and the test would correctly catch it (verified this by hand). Not vacuous.
>
> **Helper dedup** (reuse of `mustLoadPrefixedCore`/`rawIDList` from mentions_test.go): Confirmed semantically correct — `mustLoadPrefixedCore` uses `config.DefaultWithPrefix('nibs-')`, matching every fixture ID in search_id_test.go. No stray duplicate helper definitions left behind (would have been a compile error). Sound reuse.
>
> **"Bleve" query change in TestSearch_WithInjectedNoOpIndex** (search_test.go:403): This is a necessary fix, not a cosmetic rename. `setupTestCore` uses `config.Default()` → empty prefix. With the *old* query "NoOp", `normalizeIDQuery` lowers it to "noop", and since prefix is `""`, `idMatchesLocked` would substring-match the nib's own ID `"noop1"` — meaning the old query would have started returning 1 result post-feature, silently breaking the "NoOp index returns nothing" contract. Switching to "Bleve" avoids any ID collision. Correctly diagnosed and fixed by the same round.
>
> ## Findings
>
> **1. [Low / cosmetic-but-real] Misleading provenance comment on the foreign-prefix-ID test.**
> `search_id_test.go:219-221` (and the mirroring doc comment on `isIDFragment` in `core.go:353-361`) both justify the `task-42` fixture as arising from "legacy" filename parsing. I checked `nib.ParseFilename` (`internal/nib/id.go:28-49`) and its test fixtures (`internal/nib/id_test.go:71-72`, which pins `"nibs-z5r9.md"` → `id="nibs", slug="z5r9"`). A bare single-hyphen filename like `task-42.md` (no `--` separator) is actually **split at the first hyphen** by the legacy branch, giving `id="task", slug="42"` — not the whole string `"task-42"` as the test comment implies. The only realistic way `ParseFilename` yields the literal ID `"task-42"` is via the double-dash convention (e.g. `task-42--slug.md`), which is actually the *current* format (`BuildFilename` always emits `--`), not a legacy one.
> This doesn't make the test wrong — an ID like `"task-42"` genuinely can land in `c.nibs` (just via the `--` route, or a hand-edited file), and the charset-gate behavior being tested is real and correctly verified. But the comment's specific causal story is inaccurate and could mislead a future reader into thinking single-dash legacy filenames are the vector. Recommend tightening the wording rather than "legacy... unvalidated" framing. Not blocking.
>
> **2. [pre_existing, flagging per your ask about ordering/relevance flakiness] TestSearch_IDMatch_UnionWithTextHits** (search_id_test.go:81-114) — not in this round's added-tests list, so pre-existing, but it's exactly the flakiness shape you asked me to watch for: it asserts a specific relative order (`nibs-cc33` before `nibs-bb22`) between two *pure full-text* hits, based on Bleve's actual relevance/BM25-ish scoring (term frequency vs. document length) rather than any ordering contract the production code itself owns. The ID-match leg's position (first) is safe — that ordering is code-owned (`sort.Slice` by ID). But the tail ordering between two non-ID hits is coupled to the embedded search engine's internals. Not asserting anything wrong today, but it's more fragile than it needs to be. Worth a follow-up nib if you want to de-risk.
>
> No other issues found in the round-3 delta — no direct-map-population invariant violations that make a test lie (the `core.nibs[id] = ...` direct population in `TestIDMatchesLocked_ForeignPrefixIDs` only feeds `idMatchesLocked`, which is a pure function over the map + configPrefix, so bypassing `Create` doesn't hide any relevant invariant), no unstable ordering in the new assertions themselves, and no assertions that pass regardless of the behavior they name.

*(A JSON resend with the same content in structured form also arrived.)*

---

## rev-consistency (consistency-reviewer)

> Sibling-consistency review of the search-ID diff. Verified everything against sibling code (mentions.go/mentions_test.go, reprefix.go, cmd/list.go's own longer help text, config defaults, and gofmt on the base commit). 5 findings below, ordered by severity; 2 are pre_existing and don't block this round.
>
> ## 1. New cross-reference comments contradict each other on hyphens in short IDs (medium-high)
> File: internal/reprefix/reprefix.go:17-19 vs internal/nibcore/core.go:353-361 (both new this round).
>
> reprefix.go's new comment says:
> > "nibcore's search ID-match gate (isIDFragment in internal/nibcore/core.go) depends on this charset: it assumes hyphens appear only in prefixes, never in short-ID fragments — revisit that gate if this pattern loosens."
>
> But core.go's own new comment on `isIDFragment`, and the new test `TestIDMatchesLocked_ForeignPrefixIDs` (search_id_test.go:215-256), explicitly document and exercise the opposite: a foreign/legacy short ID like `task-42` (under prefix `nibs-`) *can* contain a hyphen — that's exactly why the gate excludes hyphens from fragment queries (to stop Bleve negation like `-42` from substring-matching it), not because hyphens can't occur there. The reprefix.go comment overstates the invariant it's protecting; a future maintainer reading only reprefix.go could reasonably conclude hyphenated short IDs never exist, which this same PR's test disproves. Since both comments were added in this round specifically to cross-reference each other, they should agree.
>
> ## 2. matchesLoweredIDQuery doc claims "prefix" is trimmed, but it never is (medium)
> internal/nibcore/core.go:386-388: "matchesLoweredIDQuery is matchesIDQuery with query and prefix already trimmed and lowercased". Actual normalization sites — core.go:322 (`prefix := strings.ToLower(c.configPrefix())`) and core.go:383 (`strings.ToLower(prefix)` inside matchesIDQuery) — only lowercase the prefix, never call strings.TrimSpace on it. Only `query` goes through the trim+lowercase `normalizeIDQuery`. Low real-world impact (config prefixes aren't expected to carry whitespace) but the comment overclaims what the code does.
>
> ## 3. `normalizeIDQuery` collides in name-family with unrelated existing helpers (medium)
> internal/nibcore/mentions.go already establishes a `normalizeID*` family with one specific meaning — "resolve a short/ambiguous ID to its canonical full ID via map + prefix lookup": `normalizeIDInMap` (mentions.go:32, explicitly documented as "the single source of truth for the exact-match → prefix-prepended ID resolution rule"), `Core.NormalizeID` (core.go:441), `normalizeIDForLookupLocked` (mentions.go:209). The new `normalizeIDQuery` (core.go:346-349) does something unrelated — TrimSpace+ToLower on raw query text — but its name reads as if it belongs to the same resolution family. A reader skimming for "what does ID normalization mean in this package" gets two different answers under near-identical names.
>
> ## 4. New `matchesIDQuery` test seam isn't flagged as such at its definition, unlike sibling convention (low-medium)
> mentions.go:1-8 sets the package's convention explicitly: the file-level comment states the pure functions "remain as oracles — they operate on a map without any index, so they can be used to differentially verify the indexed Core methods in tests." That's the established pattern for "this exists so tests can drive production logic without needing a full Core" duplication. `matchesIDQuery` (core.go:372-384) is exactly this shape — confirmed via grep it is called only from search_id_test.go — but its doc comment doesn't say so.
>
> ## 5. `seen` set for ID dedup uses `map[string]bool`, not the locally-established `map[string]struct{}` idiom (low, weak)
> core.go:297: `seen := make(map[string]bool, len(idMatches))` in the new `Search` dedup logic. The topically-closest sibling code — mentions.go's own "seen ID set" dedup — uses `map[string]struct{}` three times (mentions.go:63,135,177) and mention_index.go uses it twice more. However, the package isn't fully consistent either: link_queries.go, link_health.go, and migrate.go all use `map[string]bool` for similar visited/seen sets, so this isn't a clean-cut violation — just noting the new code picked the less-common-in-this-package idiom over the one used by its nearest neighbor.
>
> ## Pre-existing (not from this round, no action needed here)
> - **cmd/list.go:287** — the `-S`/`--search` flag's one-line help ("Full-text search in title and body...") omits "slug", while the Long help text 15 lines below it (line 67: "slug:auth Search only in slug field") and schema.graphqls/models_gen.go all confirm slug is indexed and searched (internal/search/index.go:46 adds a slug field mapping). This diff only appended the new "(nib IDs and ID fragments match directly)" suffix to the existing flag string — the slug omission predates it. Worth a follow-up nib since it now sits right next to freshly-edited text, but out of scope for this round.
> - **gofmt drift in internal/nibcore/core.go and internal/nibcore/search_index.go** — confirmed via `git stash` that both files fail `gofmt -l` on the base commit already (import-group ordering in core.go, single-line func alignment in search_index.go). Not introduced or worsened by this diff.
>
> ## Confirmed clean (checked, no drift)
> - Doc wording differs across schema.graphqls / models_gen.go / cmd/list.go / prompt-full.tmpl / CHANGELOG.md, but every claim (ID-first order for unsorted search, "interleaved by sort" for `nibs list`/web) checks out against schema.resolvers.go's `Nibs` resolver (search → ApplyFilter → ApplySorting, stable sort preserves ID-first relative order when sort is nil) and `buildNibSort` in cmd/list.go (always returns a non-nil sort, defaulting to `order` — so `nibs list` is correctly documented as always a "sorted surface").
> - `minIDFragmentLen`'s "~10%" comment is quantitatively accurate for the default id_length=4 over the 36-char alphabet (1-(35/36)^4 ≈ 10.3%).
> - search_id_test.go correctly reuses `mustLoadPrefixedCore`/`rawIDList` from mentions_test.go — no duplicate helpers.
> - `isIDFragment`'s charset cross-reference to `nib.idAlphabet` is accurate (`0123456789abcdefghijklmnopqrstuvwxyz`).
> - models_gen.go doc comment is byte-identical in content to schema.graphqls (properly regenerated).

*(This report was received twice — original plus a resend when the orchestrator asked; identical content.)*

---

## rev-broad (broad-reviewer)

> Reviewed the round-3 diff (charset gate, normalizeIDQuery extraction, uppercase test, dedup helpers, doc rewording, DefaultSearchLimit doc fixes) against internal/nibcore/core.go, search_id_test.go, search_index.go, search_test.go, reprefix.go, and the doc surfaces. Ran the new tests (all pass), go vet, golangci-lint (0 issues), and `task codegen` to check for generated-file drift (none). Also empirically verified one hypothesis by executing code directly rather than just reading it.
>
> ## Finding 1 — Regression: isIDFragment charset gate makes foreign/legacy-prefixed nibs unfindable by their own exact ID (confidence: high, severity: medium, new in this round)
>
> `internal/nibcore/core.go:389-397` (`matchesLoweredIDQuery`) + `362-370` (`isIDFragment`).
>
> The charset gate added this round (`[0-9a-z]` only, hyphens excluded) is applied to the *substring* branch, but a query equal to a foreign-prefixed nib's own literal full ID also falls into that branch and gets rejected, because such an ID's "short ID" (after stripping the *configured* prefix, which doesn't match) still contains the foreign prefix's hyphen.
>
> Verified directly:
> ```go
> matchesIDQuery("task-42", "task-42", "nibs-") // → false
> ```
> i.e. typing the exact ID `task-42` (a nib whose ID doesn't start with the project's configured `nibs-` prefix — e.g. a nib mid-reprefix-migration, which is exactly the scenario `internal/reprefix` exists for, and which core.go's own comment cross-references) into search will **not** find it, even though it's a perfect literal match. Before this round's gate, `strings.Contains(shortID, query)` had no charset restriction, so `Contains("task-42", "task-42")` → true; the gate is what broke this.
>
> This isn't a cosmetic gap: since Bleve's `id` field is an unanalyzed keyword field (confirmed in `internal/search/index.go:34-45`, no text fallback), there is now **no way at all** to find such a nib by its own ID string — a complete, silent loss of exactly the capability nibs-sn96 adds, for this one class of ID.
>
> It also directly contradicts the `isIDFragment` doc comment's own claim: *"Full-form prefixed queries are unaffected: they take the prefix branch of matchesLoweredIDQuery before this gate applies."* That's only true when the query is prefixed with the **configured** prefix — false for a query matching a foreign-prefixed ID. The `reprefix.go:17-19` cross-reference comment (*"assumes hyphens appear only in prefixes, never in short-ID fragments"*) makes the same overclaim that this round's own `TestIDMatchesLocked_ForeignPrefixIDs` test disproves (it explicitly creates `task-42` as a foreign short ID containing a hyphen).
>
> Suggested fix: allow exact equality to bypass the charset gate, e.g. in `matchesLoweredIDQuery`:
> ```go
> shortID := strings.TrimPrefix(id, prefix)
> if query == shortID || query == id {
>     return true
> }
> return len(query) >= minIDFragmentLen && isIDFragment(query) && strings.Contains(shortID, query)
> ```
> This still blocks `"-42"` from partial-matching `"task-42"` (not an exact match), so the original Bleve-negation-collision bug this gate fixes stays fixed — it only restores exact-match lookups.
>
> ## Finding 2 — Minor: per-nib recomputation of query-only checks (confidence: high, severity: low/optional)
>
> `idMatchesLocked` (`core.go:320-336`) calls `matchesLoweredIDQuery` once per nib in `c.nibs`, which recomputes `isIDFragment(query)` and the length checks on every iteration even though they depend only on `query`, not on the per-nib id. For a query that can never match (e.g. any multi-word query), this is still a full O(n) scan with redundant per-call work, run on every `Search()` invocation. Not a correctness issue.
>
> ## Verified clean (no action needed, sharing so it isn't re-checked)
>
> - The reworded ordering docs are accurate. Traced end-to-end: `cmd/list.go`'s `buildNibSort` always returns a non-nil `NibSort` (defaults to `ORDER`) even with no `--sort` flag; the web UI's `TREE_TABLE_QUERY` hardcodes `sort: { field: ORDER, direction: ASC }` as a query-document literal, not an omittable variable; `ApplySorting` (`internal/graph/sorting.go:32-35`) no-ops on `nil` sort, preserving `Core.Search`'s ID-matches-first/relevance order untouched.
> - `task codegen` reproduces `internal/graph/model/models_gen.go` byte-for-byte — the doc-comment edit isn't stale/hand-drifted. `generated.go` uses `//go:embed "schema.graphqls"` so it reads the schema live, not baked at codegen time — no separate staleness risk there.
> - `normalizeIDQuery` extraction is correctly shared by both the production path and the test seam with no asymmetry.
> - `DefaultSearchLimit`/`NoOpSearchIndex`/`SetSearchIndex` doc corrections are all factually accurate against the code.
> - All new/changed tests pass; `go vet` and `golangci-lint` are clean on the touched packages.
>
> ## Trivial nit (not worth a fix cycle, mentioning for completeness)
>
> The sentence "Core unions direct ID matches... on top of index results" is repeated near-verbatim in three doc comments (`SetSearchIndex`, `SearchIndex` interface, `NoOpSearchIndex`). Harmless, just means a future behavior change needs updating in three places instead of one.

*(A JSON resend also arrived, adding: verification list including a standalone executed repro test, and
extra considered-but-not-flagged entries — empty-query guard traced to the resolver, byte-wise UTF-8
safety, "single-token" doc phrasing operationally true.)*

---

## rev-design (design-reviewer) — received only as JSON resend

> ```json
> [
>   {
>     "id": "DESIGN-1",
>     "title": "Charset gate makes the exact full ID of a legacy/foreign-prefix nib unsearchable",
>     "category": "api_contract",
>     "severity": "medium",
>     "confidence": "high",
>     "pre_existing": false,
>     "location": "internal/nibcore/core.go:392-397 (matchesLoweredIDQuery); gate at internal/nibcore/core.go:362 (isIDFragment)",
>     "description": "The isIDFragment doc comment claims 'Full-form prefixed queries are unaffected: they take the prefix branch', but the prefix branch only fires for the CONFIGURED prefix. For the exact data population this round's own code comment and test introduce (foreign-prefix nib task-42 under prefix nibs-): query 'task-42' (the exact full ID) fails HasPrefix against 'nibs-', falls to the substring branch, and the hyphen fails isIDFragment — no match. Bleve cannot rescue it (id is an unanalyzed keyword field — the original nibs-sn96 bug). Meanwhile queries 'task' and '42' DO match, per TestIDMatchesLocked_ForeignPrefixIDs, whose comment declares fragment lookup of legacy nibs desirable. Specificity is inverted: every fragment of task-42 finds it except its complete identifier. This is a regression relative to the pre-gate substring branch (which matched 'task-42' exactly), introduced this round as collateral of excluding '-42'. Two contract contradictions follow: (a) all four doc surfaces say a query matching 'a prefix of the full ID' matches — for foreign-prefix IDs no prefix of the full ID now matches, including the whole ID. (b) System asymmetry: normalizeIDInMap (internal/nibcore/mentions.go:32) resolves 'task-42' by exact map-key match, so `nibs show task-42` and #task-42 mentions work — search is now the only ID-resolution surface where the exact full ID fails. Notably, TestMatchesIDQuery pins '-42' -> false and 'task' -> true but has no case for query 'task-42'; the gap sits precisely between the two pinned cases.",
>     "recommendation": "Add an exact-full-ID equality check before the fragment gate — `if query == id { return true }` (both already lowered). This restores the realistic case (pasting a complete legacy ID) with zero Bleve-operator collision risk: an operator query can only equal a full ID if that ID literally exists, in which case matching it is correct. Avoid generalizing the prefix branch to arbitrary hyphenated prefixes ('task-' matching all task-*), which would sit awkwardly next to the deliberate bare-configured-prefix rejection. Add {\"foreign full id exact\", \"task-42\", \"task-42\", \"nibs-\", true} to TestMatchesIDQuery and a corresponding case to TestIDMatchesLocked_ForeignPrefixIDs."
>   },
>   {
>     "id": "DESIGN-2",
>     "title": "Charset knowledge hand-duplicated in nibcore; comment-only invariant coupling across three packages",
>     "category": "evolution_readiness",
>     "severity": "low",
>     "confidence": "high",
>     "pre_existing": false,
>     "location": "internal/nibcore/core.go:362-370 (isIDFragment); internal/reprefix/reprefix.go:17-19",
>     "description": "isIDFragment re-encodes nib.idAlphabet (internal/nib/id.go:11) as hand-rolled byte ranges, held in sync only by a comment pair — including a new upward reference from reprefix (a leaf utility package) to a specific UNEXPORTED function in nibcore, which will silently rot on rename. No test can pin the equivalence since both sides are unexported in different packages. Comment-only invariant coupling is a legitimate technique, but here it is avoidable: nibcore already imports internal/nib, so the alphabet's owner could export the predicate.",
>     "recommendation": "Export the predicate from internal/nib (e.g. nib.IsIDChar(c byte) bool, or export the alphabet constant) so the gate derives from the source of truth; the reprefix comment then shrinks to 'short-ID charset is defined in internal/nib'. Fine to defer as a follow-up nib rather than fix in this iteration."
>   }
> ]
> ```
>
> Considered-but-not-flagged (abridged): ordering claims verified accurate end-to-end on all surfaces;
> charset gate exactly equals nib.idAlphabet; non-ASCII queries safely fail the byte-level gate;
> normalizeIDQuery symmetry confirmed; prefix needs no TrimSpace (ValidatePrefix excludes whitespace);
> DefaultSearchLimit "up to twice" arithmetically correct; concurrency of the union unchanged;
> test helper reuse clean; lock-safe single-goroutine test population; minIDFragmentLen doc-quote
> inventory complete enough. Verdict: DESIGN-1 addressed before commit; DESIGN-2 as follow-up nib.

*(DESIGN-2 became follow-up nib `nibs-es0b`.)*

---

## rev-adversarial (adversarial-reviewer) — received only as JSON resend

> DEPTH TIER: FULL adversarial pass — ~120 changed executable lines in the search path plus a new ~300-line test file; the changed code serves every search surface (CLI `nibs list -S`, web keyword box, GraphQL `search:`).
>
> ```json
> {
>   "findings": [
>     {
>       "id": "F1",
>       "title": "Charset gate makes exact full-ID queries for hyphenated foreign/legacy IDs unmatchable",
>       "severity": "medium",
>       "confidence": "high (confirmed by executing the code under review)",
>       "category": "assumption_violation",
>       "scenario": "The prefix branch only handles the CONFIGURED prefix. Any other full ID falls through to the substring branch, where its own hyphen trips the new isIDFragment gate. Verified: matchesIDQuery(\"task-42\", \"task-42\", \"nibs-\") = false (pasting the exact ID of a foreign-prefix nib finds nothing); matchesIDQuery(\"task-42\", \"task-42\", \"\") = false (empty-prefix repo: EVERY hyphenated or underscored legacy ID is unfindable by its exact ID — no prefix-branch escape exists at all); matchesIDQuery(\"nibs-old-42\", \"nibs-old-42\", \"nibs-\") = true (own-prefix nibs keep a full-form escape; foreign/empty-prefix nibs have none). The Bleve leg cannot rescue this: the id field is keyword-unanalyzed — the entire motivation for nibs-sn96. So search: \"task-42\" returns empty while nib task-42 exists.",
>       "why_it_matters": "Regression vs iteration 2 (pre-gate, the substring branch matched these). Internally inconsistent with this round's own TestIDMatchesLocked_ForeignPrefixIDs, which asserts the fragments \"task\" and \"42\" match task-42 because 'fragment lookup of legacy nibs is desirable' — yet the single most natural query, the whole ID copied from `nibs list` output, silently fails. The failure mode is the exact bug shape nibs-sn96 fixed, re-opened for the legacy population the gate's comment declares in scope.",
>       "suggested_fix": "Add an exact-equality escape before the fragment gate in matchesLoweredIDQuery: `if query == id { return true }` (id is already lowered). This cannot re-open the `-42` Bleve-negation collision: a query exactly equal to a full ID only matches a nib literally named \"-42\", in which case matching is correct."
>     },
>     {
>       "id": "F2",
>       "title": "Union test encodes Bleve inter-document relevance ranking",
>       "severity": "low",
>       "category": "test_fragility",
>       "scenario": "Asserts nibs-cc33 outranks nibs-bb22, which depends on Bleve's tf/field-length scoring for two specific documents. Deterministic today, but a bleve upgrade can flip it and the failure will masquerade as a search regression rather than a scoring shift.",
>       "suggested_fix": "Assert set membership plus 'nibs-5a8k first' — that pins the actual contract (ID matches lead, dedup works) without the scoring dependency."
>     },
>     {
>       "id": "P1",
>       "title": "Bleve text-leg parse error aborts entire Search, including the ID leg",
>       "severity": "info",
>       "pre_existing": true,
>       "scenario": "Plumbing from iteration 1/2, not this round. Currently has NO reachable ID-match casualty: probed the real internal/search index — every query that parse-errors (`title:`, unclosed quote) requires characters the charset gate rejects, and lone OR/AND/NOT/TO parse cleanly (no error, empty result). So only queries that could never ID-match anyway can trigger the abort. The gate actually closed this interaction; noting it only so the coupling is known if the gate ever loosens."
>     },
>     {
>       "id": "P2",
>       "title": "Cap-before-filter starvation on both search legs",
>       "severity": "info",
>       "pre_existing": true,
>       "scenario": "Both legs cap at 1000 before the resolver's ApplyFilter, so in repos with >1000 ID matches a filtered search silently drops matching nibs with larger IDs. The new ID leg replicates the text leg's existing shape; the per-leg cap itself is an accepted decision, so this is inherited, not new."
>     }
>   ]
> }
> ```
>
> CONSIDERED BUT NOT FLAGGED (attacks run and verified clean): gate-passing queries that are live Bleve
> syntax (lone OR/AND/NOT/TO parse cleanly); non-ASCII input to the byte-wise loop (Kelvin sign U+212A
> lowers to ASCII 'k' and can ID-match — harmless quirk); empty-prefix repos with charset-clean IDs;
> prefix-of-prefix and mixed-prefix maps; unvalidated hand-edited config prefixes; ordering docs verified;
> lock-free test map population safe (no watcher); archived-nib leg symmetry; dedup correctness;
> short common-word fragments ("or", "go", "db") — consequence of accepted min-length-2 decision.
> All probes run via temporary test files, since removed; no working-tree changes remain from the review.

---

## rev-knowledge (knowledge-reviewer) — received only as JSON resend

> ```json
> {
>   "findings": [
>     {
>       "id": "KR-1",
>       "title": "\"Full-form prefixed queries are unaffected\" overclaims; four doc surfaces now contradict the code for foreign full-ID queries",
>       "severity": "medium",
>       "confidence": 0.9,
>       "category": "KNOWLEDGE_MISLEADING_COMMENT / DOC_CODE_CONTRADICTION",
>       "description": "The isIDFragment comment says 'Full-form prefixed queries are unaffected: they take the prefix branch of matchesLoweredIDQuery before this gate applies.' That is only true for queries bearing the CONFIGURED prefix. Applied to the comment's own worked example — foreign nib `task-42` under prefix `nibs-` — the full-ID query `task-42` does NOT start with `nibs-`, falls to the substring branch, and is rejected by the new charset gate for its hyphen. So pasting a foreign/legacy nib's complete ID finds nothing via ID match, while the partial fragments `task` and `42` DO match it. Tests pin `-42` -> false and `task` -> true against `task-42`, but not the full-ID query `task-42` -> false, so nothing stops a future maintainer from silently 'fixing' either direction.",
>       "recommendation": "(a) Reword core.go to 'Full-form queries bearing the configured prefix are unaffected…'. (b) Add test row for the foreign full-id query. (c) Either qualify 'a prefix of the full ID' on the user-facing surfaces or accept the simplification deliberately and note it."
>     },
>     {
>       "id": "KR-2",
>       "title": "minIDFragmentLen's doc-surface enumeration omits the CHANGELOG",
>       "severity": "low",
>       "confidence": 0.85,
>       "description": "The comment enumerates surfaces quoting the value, but the Unreleased CHANGELOG entry also quotes 'min 2 characters'. Until the next release ships, that entry is live text needing the same update. Incomplete enumerations are how the third copy drifts.",
>       "recommendation": "Add 'and the Unreleased CHANGELOG entry' to the enumeration, or drop the number from the CHANGELOG line."
>     },
>     {
>       "id": "KR-3",
>       "title": "Comment names the wrapper (matchesIDQuery) instead of the function holding the branch (matchesLoweredIDQuery)",
>       "severity": "nit",
>       "confidence": 0.9,
>       "description": "'the short-ID substring branch of matchesIDQuery' — the branch lives in matchesLoweredIDQuery (core.go:389)."
>     },
>     {
>       "id": "KR-4",
>       "title": "Union test also pins Bleve's relative scoring of the two text hits",
>       "severity": "nit",
>       "confidence": 0.6,
>       "description": "[Inference] A Bleve upgrade could flip that relative order and produce a confusing failure in a test named for the union. The comment at lines 85-87 preserves the reasoning, which mitigates this.",
>       "recommendation": "Acceptable as-is; asserting only 'ID match first, both text hits present after it' would decouple the test from scoring internals."
>     }
>   ]
> }
> ```
>
> Considered-but-not-flagged (abridged): nib.idAlphabet cross-reference precisely correct; reprefix
> back-reference names the right symbols; DefaultSearchLimit doc verified on both legs; NoOp query
> change necessary and correctly explained; sorted-surface claims verified; no stale-codegen risk
> (go:embed); test-helper reuse safe (no watcher goroutine); foreign-ID provenance claim loose but
> the coexistence claim true; matchesIDQuery doc covers the charset requirement one sentence later.
> "No pre-existing issues surfaced that this round made worse, other than as absorbed into KR-1."

---

## rev-spec (spec-compliance-reviewer)

Report **not received** in the main context (idle notifications only). Its iteration-2 counterpart
confirmed full semantics coverage against the nibs-sn96 spec; no iteration-3 content available.
