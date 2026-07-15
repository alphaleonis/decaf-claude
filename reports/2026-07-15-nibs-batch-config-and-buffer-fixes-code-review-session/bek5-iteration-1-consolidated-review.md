# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, go, test, spec-compliance, knowledge, consistency, design, security, adversarial | **Date**: 2026-07-15
**Source**: local uncommitted changes — branch `batch/config-and-buffer-fixes`, based on `develop` @ `0516fe1`
**Scope**: 2 files changed, +177/-31 lines (`cmd/root.go`, `cmd/root_test.go`)
**Spec**: nib `nibs-bek5` — "Config discovery ignores --nibs-path, silently loading a foreign .nibs.yml" (inferred → severities capped at Medium)
**Validation**: 9 confirmed, 2 refuted, 0 uncertain, 0 waived, 0 unvalidated (11 dispatched, budget 15)

## Agent Selection Rationale

Mode was **explicit** (`mid`), so no mode recommendation was computed. Changeset classified as: Go-only, substantive, ~94 changed executable lines in `cmd/root.go` plus 114 test lines; touches file I/O, config trust boundaries, and a process-wide `(root, cfg)` contract.

- **quick-reviewer** — always (review floor)
- **broad-reviewer** — always (review floor)
- **go-reviewer** — Go files in changeset (hard gate)
- **test-reviewer** — test files in changeset (hard gate)
- **spec-compliance-reviewer** — a spec was discovered (hard gate); see Spec Discovery below
- **knowledge-reviewer** — substantive change; the new `loadConfig` docblock makes several verifiable precedence claims
- **consistency-reviewer** — substantive change with sibling `cmd/` and `internal/config/` code to compare against
- **design-reviewer** — changes the config↔data-dir pairing contract and precedence for every command, the TUI, GraphQL, and `nibs serve`
- **security-reviewer** — config discovery now walks upward from a caller-named path to the filesystem root, reading and honoring `.nibs.yml`; foreign-config trust boundary
- **adversarial-reviewer** — >50 changed executable lines
- **performance-reviewer: skipped** — bounded directory walk at CLI startup; no DB, hot path, or scale surface
- **data-migration / dotnet / typescript / cpp / rust: skipped** — domains absent from the changeset (hard gates)
- **prior-feedback-reviewer: skipped** — local changes, not a PR (hard gate)

**Model tiering (mid)**: judgment agents (knowledge, design, security, spec-compliance, adversarial) inherited the session model; volume agents (quick, broad, consistency, test, go) and all 11 validators ran mid-tier (`sonnet`).

**Spec discovery**: no `--spec` was passed and no `plans/` directory exists. A repo-document search of the project's own nib tracker returned exactly one match for the branch's subject matter — `.nibs/nibs-bek5--config-discovery-ignores-nibs-path-silently-loadin.md` (status `in-progress`, type `bug`), which describes this changeset unambiguously (same file, same symptom, same repro). Source recorded as **inferred** because the requester did not name it; the spec-compliance-reviewer therefore capped its severities at Medium.

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 0 |
| 🟡 Medium | 5 |
| 🟢 Low | 2 |
| 🔵 Minor | 2 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings. Pre-existing issues are listed separately and excluded from both.

**Verdict**: ❌ NEEDS_CHANGES

The fix is correct for the case it targets — multiple reviewers independently reproduced the original bug and confirmed this change resolves it. It is blocked by one confirmed Critical: the change trades the cwd-mispairing bug for a **new, narrower mispairing** that is worse in kind, because its failure mode is *writing* rather than merely *reading* wrong.

---

## Findings

### #1 🔴 Critical: A data directory outside the project subtree loses its own config and mints unprefixed IDs

| | |
|---|---|
| **File** | `cmd/root.go:115-124` |
| **Category** | correctness / design |
| **Confidence** | 100 |
| **Found by** | design-reviewer (Critical), adversarial-reviewer (Critical) — independently, both with executed A/B binaries |
| **Validation** | CONFIRMED — validator independently reproduced all three claimed scenarios |

**Issue:** `loadConfig` anchors the `.nibs.yml` search at the explicitly-named data directory, which assumes `.nibs.yml` is an **ancestor** of it. But `Config.ResolveNibsPath()` (`internal/config/config.go:242-252`) explicitly supports `nibs.path` being an **absolute path** (or `../sibling`) — a deliberately tested feature, with a dedicated unit test at `internal/config/config_test.go:703-715` ("returns absolute path unchanged"). For such a project, naming its own data directory via `--nibs-path`/`NIBS_PATH` finds no config above it, falls back to system defaults, and silently drops `prefix`, `id_length`, `default_status`, `default_type`, and `require_if_match` — for the project's **own** data directory.

Because `applySystemDefaults` never defaults `Prefix` (it stays `""`) and `UserNibsConfig` has no `Prefix` field, `nibs create` then mints **unprefixed IDs into a prefixed project's data directory** — permanently, since the ID is baked into the filename and into `parent`/`blocked_by` cross-references.

This is a **regression**. Reproduced by three independent agents with HEAD-vs-working-tree binaries:

| scenario | HEAD | working tree |
|---|---|---|
| out-of-tree `nibs.path`, `--nibs-path` naming that dir | `proj-l6j7` ✅ | `9hia` ❌ prefix lost |
| conventional layout (the targeted bug) | `cwd-3d8z` ❌ | `data-vu8b` ✅ fixed |

Three invocations against one data directory produce a **split ID space** (`proj-wj6a` no-flag, `63rj` via `--nibs-path`, `3b85` via `NIBS_PATH`), and the tool's own repair path then refuses from **both** routes:
```
$ nibs config set-prefix newp --dry-run
Error: snapshot contains nib "3b85" which does not have the expected prefix "proj-"
$ nibs --nibs-path ... config set-prefix newp --dry-run
Error: old prefix: must not be empty
```
`reprefix.BuildPlan`'s two guards are individually correct but together make the split state unreachable by the designated repair tool — recovery means hand-renaming files plus cross-references. `require_if_match: true` is silently dropped to `false` on the same path, disabling optimistic concurrency for `nibs serve`.

**Validator nuance (recorded, does not refute):** HEAD is *also* wrong here when cwd is outside the project — so HEAD's correctness is contingent on cwd being inside the project, not a universal guarantee. Both finders implicitly assumed cwd = project root. That is the dominant, realistic usage, so this remains a genuine regression in the common case; it is simply not evidence that the old behavior was robust.

**Fix:** The data-dir walk finding nothing is not evidence that defaults are correct — it is evidence that the config is **unknown**. Encode the real invariant (the config must *own* the root) instead of inferring it from directory nesting:

```go
// Build candidates, then select the one that actually owns the root.
// Rejects a foreign project's config (the bug being fixed) while still
// accepting a project whose nibs.path points outside its own subtree.
for _, cand := range []*config.Config{walkUpFrom(dataDir), walkUpFrom(cwd)} {
    if cand != nil && sameDir(cand.ResolveNibsPath(), root) {
        return cand, nil
    }
}
return nil, fmt.Errorf("no config found that owns %s; pass --config explicitly", root)
```
Failing loudly is the only non-silent option when the tool is about to mint permanent IDs. This ownership check also subsumes findings #2 and #3. Alternatively, at minimum guard `Core.Create` against minting when `cfg.Nibs.Prefix == ""` but existing nibs on disk carry a common prefix.

---

### #2 🟡 Medium: A `.nibs.yml` inside the data directory shadows the project root's config

| | |
|---|---|
| **File** | `cmd/root.go:115-124` (mechanism at `internal/config/config.go:158`) |
| **Category** | security / design |
| **Confidence** | 100 |
| **Found by** | security-reviewer (Medium), adversarial-reviewer (High), design-reviewer (Low, marked pre-existing) |
| **Validation** | CONFIRMED — severity corrected to Medium; `pre_existing: no` upheld |

**Issue:** `FindConfig(startDir)` checks `startDir/.nibs.yml` **first**, before walking upward. Since `loadConfig` now passes the data directory as `startDir`, a `.nibs.yml` inside the data dir silently shadows the project root's. Before this change a file inside the data directory was never consulted at all — the walk began at cwd and found the project's config without ever descending.

**This is live in this very repository.** I verified independently: `/home/decaf/code/nibs/.nibs/.nibs.yml` exists, is **tracked** in the separate `.nibs` git repo, and carries `path: .` + `prefix: nibs-`, while the outer `/home/decaf/code/nibs/.nibs.yml` also says `nibs-`. They agree today, so nothing misbehaves — but this change makes that hand-agreement **load-bearing**, with nothing enforcing it. CLAUDE.md documents `.nibs/` as a separate repo whose contents arrive over the network via `git -C .nibs pull`, and this project's own tooling (`task demo`, the `cmd/` test suite) uses `--nibs-path` pervasively — exactly the trigger this change opens.

Reproduced (validator, scratchpad copy): outer `prefix: real-`, planted inner `prefix: PLANTED-` → no flag yields `real-r3gg`, `--nibs-path .nibs` yields `PLANTED-hk0bq8knn`.

Drift proof (adversarial-reviewer):
```
$ nibs config set-prefix proj --force      # from repo root, no flag
  outer .nibs.yml → proj-    # written
  inner .nibs/.nibs.yml → nibs-    # untouched, now STALE
$ nibs --nibs-path .nibs create "after drift"  → "id": "nibs-nch4"   # stale prefix
$ nibs config set-prefix fixed --force
Error: snapshot contains nib "nibs-nch4" which does not have the expected prefix "proj-"
```

**Severity dissent resolved:** the validator confirmed the blast radius is bounded — `resolveNibsPath` short-circuits to the explicit path, so a shadowing config's `nibs.path` is **never honored** (verified: the created file landed in the caller-specified directory, not redirected). This is a config-integrity/availability bug, not a data-redirect or code-execution primitive → Medium over adversarial's High. But the demonstrated `set-prefix` breakage is a real availability hit, so design-reviewer's Low is not defensible either. **That short-circuit is load-bearing security logic** — a future "simplification" resolving the path uniformly through the config would turn this into a genuine data-redirect primitive.

**Fix:** Start the data-dir-anchored walk at `filepath.Dir(dataDir)` so the data dir can never self-describe — `loadConfig`'s own docblock already asserts `.nibs.yml` lives at the project root with `.nibs` inside it. **Caveat to weigh first:** the inner `.nibs/.nibs.yml` with `path: .` appears deliberate (for standalone use of the `.nibs` repo), so this fix may break that use case. The ownership check in #1 resolves this correctly without that trade-off, since an inner config resolves to `<datadir>/.nibs != root`.

---

### #3 🟡 Medium: Unbounded ancestor walk; docblock presents a heuristic as a guarantee

| | |
|---|---|
| **File** | `cmd/root.go:98-100` |
| **Category** | comment-code mismatch / design |
| **Confidence** | 75 (promoted from 50 on 4-finder agreement) |
| **Found by** | broad-reviewer (Medium), spec-compliance-reviewer (Medium), security-reviewer (Low), knowledge-reviewer (SHOULD) |
| **Validation** | CONFIRMED — "likely fully subsumed" by #1's fix |

**Issue — two coupled halves:**

**(a) The mechanism.** `FindConfig` walks upward to the filesystem root with no bound. A `.nibs.yml` at *any* ancestor of the named data dir is silently adopted — e.g. `nibs get --nibs-path ~/scratch/unrelated/.nibs` picks up `~/.nibs.yml` if the user ever ran `nibs init` in `$HOME`.

**(b) The docblock overclaim.** Clause 2 asserts the search "pairs the data with **its own project's** config — `.nibs.yml` sits at the project root with `.nibs` inside it". That is a project *convention*, not an invariant the mechanism enforces; `FindConfig` returns the nearest ancestor, whatever it is. The docblock's next clause covers only the *no match* case, never the *wrong match* case — while explicitly flagging that identical risk class one sentence later when justifying the cwd rejection. That internal inconsistency is what makes this an overclaim rather than a mere omission, and it is precisely the recurring defect class this codebase tracks.

**Validator A/B (scratchpad binaries)** — this is a *trade*, not a pure regression:

| scenario | OLD | NEW |
|---|---|---|
| stray `.nibs.yml` above the **named data dir** | `hyc5` (defaults — no capture) | `ANCESTOR-iyivzqn4` ❌ newly broken |
| stray `.nibs.yml` above **cwd**, data dir configless | `CWDPROJ-8c5saf` ❌ | `c5r7` ✅ newly fixed |

**Fix:** Fully mooted by #1's ownership check — a `candidate.ResolveNibsPath() == root` test rejects the stray ancestor *and* makes the docblock's claim true. If #1 is deferred, at minimum rewrite clause 2 to describe the mechanism and its limit:
> "search upward from it for the nearest `.nibs.yml`, which **by convention** sits at the project root with `.nibs` inside it. The walk is unbounded — it reaches the filesystem root — so a data directory with no project config of its own can match a stray ancestor config (e.g. one in `$HOME`)."

---

### #4 🟡 Medium: `configDir` overloaded to mean "the data directory"; `GetProjectName()` reads `.nibs`

| | |
|---|---|
| **File** | `internal/config/userconfig.go:118-121` (reached via `cmd/root.go:115-124`) |
| **Category** | data-model / API contract |
| **Confidence** | 100 |
| **Found by** | design-reviewer (Medium), broad-reviewer (Low), knowledge-reviewer (SHOULD), adversarial-reviewer (Low) |
| **Validation** | CONFIRMED |

**Issue:** Passing the data directory as `FindConfig`'s `startDir` overloads `Config.configDir` to mean either "the directory the config was found in" (its meaning everywhere else) or "the data directory" (when the walk finds nothing). Consumers assume the former. `GetProjectName()` returns `filepath.Base(configDir)` → literally `.nibs`, surfacing in the TUI border title (`internal/tui/list.go:1076`) and GraphQL `ProjectName` (`internal/graph/schema.resolvers.go:848`). Its existing `"Nibs"` fallback is **bypassed** precisely because `configDir` is non-empty.

Validator reproduced it directly:
```
$ nibs --nibs-path <orphan-datadir> query '{ config { projectName } }'
{"projectName": ".nibs"}
```

**On the implementer's "display-only, deliberately left" call — it is accurate, and the validator confirmed why:**
- `Config.Save("")` → `targetDir = configDir` = the data dir *looked* like it would write a `.nibs.yml` inside the data directory via `config set-prefix`. **Refuted by three agents:** the chain dies at `reprefix.BuildPlan`'s empty-prefix guard (`internal/reprefix/reprefix.go:114-116`) before any write, and this block is **structural, not incidental** — the orphan branch always yields `Prefix == ""`, guaranteeing the guard fires. Both `Save()` call sites in the repo (`cmd/init.go:107`, `cmd/config.go:130`) are accounted for.
- `cfg.ResolveNibsPath()` would return `<datadir>/.nibs` on this path — wrong, but **dead**: grep confirms exactly one caller (`cmd/root.go:137`), reached only when `!explicit`.

So the accepted trade is real and correctly characterized. It is still worth recording that the *only* barrier against writing a config into the data directory is an unrelated prefix validation — a robust-by-accident boundary, one refactor from breaking.

**Fix:** Keep `configDir` meaning only "where a config file was actually found". When the walk finds nothing, leave it unset (or carry a distinct anchor field) so `GetProjectName`'s `"Nibs"` fallback works as designed and consumers requiring a real project root can detect the condition.

---

### #5 🟡 Medium: `CLAUDE.md:89` now contradicts the code

| | |
|---|---|
| **File** | `CLAUDE.md:89` |
| **Category** | doc-vs-code contradiction |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (SHOULD) |
| **Validation** | CONFIRMED |

**Issue:** The line reads:
> "Project config lives in `.nibs.yml` at project root **(searched upward from cwd)**. Key settings: ... Nibs path can also be set via `--nibs-path` flag or `NIBS_PATH` env var."

The validator confirmed via `git show HEAD:cmd/root.go` that this was a **true and complete** description of the non-`--config` branch before the diff (cwd was the only possible anchor), and is **now false** for any invocation setting `--nibs-path`/`NIBS_PATH` without `--config`. Worse, the sentence goes on to present `--nibs-path`/`NIBS_PATH` as a *data-path* override only — reinforcing exactly the model this change exists to correct. `grep` confirms no other text in CLAUDE.md qualifies it.

This matters more than a typical doc nit: CLAUDE.md is this repo's authoritative onboarding document that agents read *instead of* `cmd/root.go`. The changeset is what invalidated it, and nothing else will catch it.

**Severity note:** knowledge-reviewer rated this SHOULD (→ High under strict normalization). I normalized to Medium — it is a one-line documentation fix with no runtime consequence. Dissent recorded.

**Fix:** Replace the parenthetical:
> "(`.nibs.yml` is located by `--config` if given; otherwise by searching upward from the data directory named by `--nibs-path`/`NIBS_PATH`, or from cwd when neither is set)"

---

### #6 🟡 Medium: `t.Skipf` gates all 7 subtests on a precondition only one of them needs

| | |
|---|---|
| **File** | `cmd/root_test.go:178-182` |
| **Category** | test-quality / silent coverage loss |
| **Confidence** | 75 |
| **Found by** | test-reviewer (Medium) |
| **Validation** | CONFIRMED — reproduced, and **worse** than claimed |

**Issue:** The stray-ancestor guard sits before the table loop, but exists only to protect the `orphanData` case. Cases 1–4 terminate their `FindConfig` walk inside `cwdProj`/`dataProj` (each has its own `.nibs.yml`); cases 5–6 bypass `FindConfig` entirely via `--config`. Only case 7 depends on the guard.

The validator **empirically reproduced it** by pointing `TMPDIR` at a subdirectory of this repo (which has its own `.nibs.yml` at the root — this project dogfoods itself, so "a checkout with an ancestor `.nibs.yml`" is not hypothetical). Result: **not one of the 7 subtests appears in `-v` output** — only `--- SKIP: TestPersistentPreRunEConfigDiscovery`. The entire regression net vanishes as a unit, silently.

The project's actual CI (`.github/workflows/ci.yml`, stock `ubuntu-latest`/`windows-latest`, no `TMPDIR` override) would not hit this today — the finding claims general plausibility, not that current CI is affected.

**Fix:** Move the `FindConfig`/`Skipf` check inside the `orphanData` subtest. Consider `t.Fatalf` over `t.Skipf`: a skip silently drops coverage, while a failure surfaces the environment problem. (Skip is a defensible philosophy choice for an environment fault — but the misplacement is a defect either way, and moving the guard resolves it regardless.)

---

### #7 🟢 Low: The 7-case table has no out-of-tree `nibs.path` row — which is how #1 escaped

| | |
|---|---|
| **File** | `cmd/root_test.go:149`, `:244-247` |
| **Category** | test-coverage |
| **Confidence** | 100 |
| **Found by** | test-reviewer (Medium) — corroborated in prose by design-reviewer and adversarial-reviewer |
| **Validation** | CONFIRMED — **severity corrected Medium → Low; finding reframed** |

**Issue as filed:** the test asserts only `Nibs.Prefix`, and `newConfigDiscoveryProject` writes `id_length: 4` for every fixture — exactly `config.Default().Nibs.IDLength` (`config.go:128`) and exactly what `applySystemDefaults` fills in (`config.go:213`). So `IDLength` could never discriminate "correct config loaded" from "wrong config leaked" from "no config, defaults applied". `default_status`, `default_type`, `require_if_match` are never set in any fixture, so asserting them would be tautological. The docblock names all five fields as corrupted.

**Validator's reframing (adopted):** the proposed fix — give fixtures distinct `id_length` values — **would not have caught the Critical**. In that regression, prefix reverts `proj-` → `""`, so `Prefix` alone would already fail on a new out-of-tree row. The regression escaped because **no such row exists**, not because `Prefix` is too narrow a discriminator. `Prefix` is in fact a good discriminator: distinct per project, and it is what caught the targeted bug. Since `Config` loads atomically from one YAML file, asserting one distinctive field largely proves the pairing.

**Fix:** Add a table row for a project whose `nibs.path` points outside its own subtree (absolute or `../sibling`), named via `--nibs-path` — i.e. a regression test for finding #1. Widening assertions on the existing rows is optional polish, not the gap.

---

### #8 🟢 Low: Nib `nibs-bek5` still reads "Decision needed" and has 5 unticked checkboxes

| | |
|---|---|
| **File** | `.nibs/nibs-bek5--config-discovery-ignores-nibs-path-silently-loadin.md` |
| **Category** | spec-vs-implementation drift |
| **Confidence** | 75 |
| **Found by** | spec-compliance-reviewer (Low) |
| **Validation** | CONFIRMED |

**Issue:** The implementation contradicts the literal text of the nib's option 1 — "walking up from the resolved nibs path, **falling back to cwd when that finds nothing**" — by falling back to system defaults instead. The nib still presents the decision as open and all 5 Verification items unticked.

**This is not a compliance failure, and the deviation is correct.** The nib's "Decision needed" section explicitly delegates the choice ("Precedence between `--nibs-path`, `NIBS_PATH`, `--config`, and discovery needs settling as part of this"). Deviating from one bullet of an explicitly-open decision list is *exercising* the decision, not violating the spec. Moreover, both the spec-compliance-reviewer and its validator independently established that **option 1 as literally written is circular**: `Config.ResolveNibsPath()` is a method on `*Config`, so "walk up from the resolved nibs path" has no path to walk up from until a config already exists. The `explicitNibsPath` split is the coherent resolution of that circularity.

What survives is only that the decision was made but never recorded where this project records decisions — the reasoning currently lives solely in a Go docblock.

**Fix:** Update `nibs-bek5` at commit time — replace "Decision needed" with the decision as made (`--config` > data-dir walk > cwd; no cwd fallback) and tick the checklist. **No code change.** Per CLAUDE.md this is a separate commit in the separate `.nibs/` repo.

---

## Pre-existing Issues

Informational only — excluded from the verdict and Summary counts.

### P1 🟡 Medium: `--config` naming a nonexistent file silently yields defaults and mints unprefixed nibs

| | |
|---|---|
| **File** | `internal/config/config.go:185-193` (`loadRaw`), reached via `cmd/root.go:107-113` |
| **Category** | correctness / silent failure |
| **Confidence** | 100 |
| **Found by** | knowledge-reviewer (MUST) — broad-reviewer independently identified it as pre-existing and declined to flag |
| **Validation** | CONFIRMED — **reattributed to `pre_existing: true`, severity corrected High → Medium** |

**Issue:** `loadRaw` swallows `os.IsNotExist` and returns an empty `Config` with no error, so a typo'd `--config` path silently produces defaults. Reproduced end-to-end:
```
$ nibs --nibs-path realproj/.nibs --config realproj/.nibs.TYPO.yml create "typo config nib" --json
{ "nib": { "id": "oy2x" } }        # exit 0 — unprefixed, permanent
$ ls realproj/.nibs/
oy2x--typo-config-nib.md           # wrong ID
real-zhot--baseline-nib.md         # correct baseline
```

**Why pre-existing:** the validator established via `git diff` that the old `cmd/root.go` called `LoadFromExplicitPathWithUserConfig` with byte-identical error wrapping — a pure extract-function refactor. `internal/config/` is untouched by this diff, and `git log -p --follow` shows the ENOENT swallow in `loadRaw` dates to the initial commit (`6319331`) and has never been modified. The runtime defect is 100% pre-existing.

The validator also weakened the "new false claim" half: clause 1 ("`--config`: that exact file, whatever else is set") sits under the heading **"Precedence for locating .nibs.yml"** and reads as a *precedence* statement, not an existence guarantee. The real gap is that the missing-file tolerance is simply **undocumented** — unlike clause 2, which explicitly documents its own not-found fallback.

**Fix (defer to a follow-up nib per CLAUDE.md):** `os.Stat(explicitConfigPath)` in `loadConfig` and error when missing — matching `resolveNibsPath`'s existing "explicit means it must exist" convention (`cmd/root.go:141-146`), an asymmetry worth closing. Or document the tolerance in clause 1.

---

### P2 🟡 Medium: `resolveNibsPath` discards `statErr`, so `isIOError` can never route to `ExitIO`

| | |
|---|---|
| **File** | `cmd/root.go:143` |
| **Category** | error-handling |
| **Confidence** | 75 |
| **Found by** | go-reviewer (Medium) |
| **Validation** | not validated (pre-existing findings are not sent to the validation wave) |

**Issue:** Both return branches build a fresh `fmt.Errorf` with `%s` (the path string), never `%w`-wrapping the underlying `*fs.PathError`/`fs.ErrNotExist`/`fs.ErrPermission`. `isIOError` (`cmd/root.go:192`) exists specifically to route these to `ExitIO` via `errors.As`/`errors.Is`, and its own doc comment claims to cover exactly this case ("plain errors bubbling up from os/fs calls ... in PersistentPreRunE") — but since nothing is wrapped, a permission-denied or missing data directory always reports the generic `ExitError` (1) instead of `ExitIO` (5).

**Fix:** `fmt.Errorf("nibs path does not exist or is not a directory: %s: %w", root, statErr)` (and similarly for the other branch).

---

## Minor Findings

### Testing Gaps

- `cmd/root_test.go:244` — the test never asserts the resolved *data directory* (`getApp(cmd).Core.Root()`), only the config, though the bug was a **mispairing** of the two. No live blind spot (`resolveNibsPath` doesn't depend on `cfg` when an explicit path is given), but a cheap strengthening of the docblock's "pairing" claim (test-reviewer, anchor 50)
- `cmd/root_test.go:222` — `wantPrefix: ""` cannot distinguish "defaults correctly applied" from other failure modes that also yield an empty prefix; it happens to catch this regression (pre-fix returns `"cwd-"`) but is a fragile boundary (test-reviewer, anchor 50)

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 0 | 0 |
| broad-reviewer | 2 | 0 |
| go-reviewer | 1 | 1 |
| test-reviewer | 4 | 4 |
| spec-compliance-reviewer | 2 | 1 |
| knowledge-reviewer | 4 | 2 |
| consistency-reviewer | 0 | 0 |
| design-reviewer | 3 | 0 |
| security-reviewer | 2 | 0 |
| adversarial-reviewer | 3 | 0 |
| **Total** | **12** | |

Counts cover primary + pre-existing + minor findings, refuted findings excluded. Each finding counts once toward every agent that found it; **Total** counts each finding once.

**Roster observations for tuning:**
- The Critical was found **only** by the two agents that built and ran comparison binaries (design, adversarial). Every static-reasoning reviewer missed it, and `quick` and `consistency` returned zero findings despite `quick` explicitly examining and dismissing the ancestor-walk hazard at confidence 25. Empirical probing, not additional readers, is what found the blocking defect.
- `test-reviewer` produced the most unique findings (4), all on a 114-line test addition.
- The 4-finder clusters (#3, #4) produced no unique findings from any single member — broad, security, spec-compliance, and knowledge converged on the same two issues from different angles, which is corroboration rather than coverage.

---

## Specialist Notes

### Requirement Coverage Matrix (spec-compliance-reviewer)

| Req | Description | Status | Evidence |
|-----|-------------|--------|----------|
| R1 | Decide the config-location rule and its precedence | **Covered** (code) / spec stale | `cmd/root.go:102-114`, `:89-94` document the full precedence; 7-case table pins all branches. Nib still says "Decision needed" → finding #8 |
| R2 | `nibs get f003 --nibs-path <other>/.nibs` resolves short IDs via that project's prefix | **Covered — empirically verified** | Ran the spec's repro against a probe binary from the nibs repo (`prefix: nibs-`) targeting a `tnib-` fixture copy: returns `tnib-f003`. Works via both `--nibs-path` and `NIBS_PATH` |
| R3 | `task demo` serves the fixture with `prefix: tnib-` | **Covered — no Taskfile change needed** (claim verified) | `Taskfile.yml` copies `.nibs` *and* `.nibs.yml` into `{{.TMP}}/`; `FindConfig(TMP/.nibs)` walks to `TMP/.nibs.yml` → `tnib-`. Reproduced; short-ID resolution succeeds. Not pinned by a test |
| R4 | Test: a data dir outside cwd does not silently inherit cwd's config | **Covered** | `cmd/root_test.go` — "data directory without a config falls back to defaults, not cwd" and "nibs-path flag discovers config from the data directory" |
| R5 | `task test` green | **Covered** | Pre-flight PASS; re-ran `go test ./cmd/ -run 'TestPersistentPreRunEConfigDiscovery\|TestResolveNibsPath' -v` — 15 subtests PASS, zero skips |
| R6 | *(implied by title)* Config discovery must not silently pair a foreign `.nibs.yml` with the data dir | **Partial** | Fixed for the cwd case (R2/R4). Residual: findings #1, #2, #3 |

### Threat Model Notes (security-reviewer)

**Trust boundaries.** Correctly calibrated, this is a local-first, single-user developer CLI — the operator already controls cwd, argv, env, and the binary, so most "attacker controls the input" framings collapse. Two boundaries survive that calibration: (1) `.nibs/` as a separately-cloned git repo whose contents arrive from a network remote — this is what makes #2 worth acting on rather than theoretical, and it is specific to this repo's own documented setup; (2) directories with ancestors the operator does not exclusively own (`/tmp`, shared mounts).

**What the change widens.** It converts config discovery from *one* fixed start point (cwd) into *two* (cwd, or any caller-named data dir), against a walk that has always run unchecked to `/`. The fix's core insight — identify the data dir first, then anchor config to it — is sound. The `resolveNibsPath` short-circuit is doing real security work by keeping `nibs.path` unreachable from a discovered config.

**Explicitly checked and cleared:**
- **Planted config redirecting the data dir via absolute `nibs.path`** — not reachable, verified empirically. Probe: planted `.nibs/.nibs.yml` with `path: <scratch>/evil-dest` still wrote to the named data dir; `evil-dest` stayed empty. The prefix was honored, the path was not.
- **`nibs serve` exposure** — non-issue. Bind host is hardcoded `127.0.0.1` in `cmd/serve.go`, overridable only by `--host`; not a config field. `resolveServeOptions` reads only `port`/`open_browser` from config.
- **`NIBS_PATH` as env-var escalation** — real in the literal sense, but not separately actionable: anyone who can set `NIBS_PATH` can equally set `--config`, change cwd, or replace the binary via `PATH`.
- **Error-path disclosure** — non-issue. Produced in `PersistentPreRunE` before any HTTP server exists; reaches only the invoking user's stderr.
- **`..` segments** — non-issue. `filepath.Abs` cleans lexically; no privilege boundary crossed.

**Symlink observation (correctness, not security):** `FindConfig` walks the *lexical* path via `filepath.Dir`, not the resolved target. If `/tmp/link` symlinks to `/real/project/.nibs`, `--nibs-path /tmp/link` searches `/tmp/.nibs.yml`, not `/real/project/.nibs.yml` — pairing data with the symlink's location rather than "its OWN project's config". `filepath.EvalSymlinks` before the walk would close this and tighten #3.

### Considered But Not Flagged (all agents)

**Refuted by validators (2):**
- **`(root, cfg)` pairing invariant implicit / `explicitNibsPath` re-derived twice / `resolveNibsPath` ignores `cfg`** (design-reviewer, Medium) — **refuted**. The validator found the premise factually wrong about the code's own branches: in the implicit branch `root` is *definitionally derived from* `cfg`, so there is no independent signal to cross-check; in the explicit branch `root` deliberately overrides `cfg`'s `nibs.path` (the documented precedence), so comparing them would flag intended behavior as a defect. `resolveNibsPath` is therefore not "positioned" to detect anything. The precedence matrix is also *not* scattered — `loadConfig`'s docblock centralizes it and `explicitNibsPath` is a single shared pure function. Four reviewers (quick, go, adversarial, broad) had already independently refuted the divergence half as unconstructible.
- **"2 of 7 subtests pass pre-fix; docblock overclaims"** (test-reviewer, Medium) — **refuted**. The validator's revert-probe reproduced **3 of 7** passing (not 2 — the finding's own evidence block contradicted its headline), and found the docblock never uses "regression" or claims each case fails pre-fix; it states the invariant, the hazard, and the full precedence chain. Documenting all branches of a precedence rule — including ones the bug never touched — is standard test design. The validator noted the task brief's warning about comment-overclaiming may have primed a false positive.

**Suppressed by the confidence gate:** 2 findings at anchor 25 (quick-reviewer's ancestor-walk note and its double-`os.Getenv` note) — both later surfaced independently by other agents at reportable confidence and appear above as #3 and in the refuted set respectively.

**Examined and cleared:**
- **Comment rules (CLAUDE.md)** — verified compliant by knowledge, consistency, and quick. No British spellings; no nib/issue IDs (the `nibs-[0-9a-z]{4}` grep hits were false positives matching `--nibs-path`); no change-history narration. `explicitNibsPath`'s "rather than the other way around" reads as change-history at a glance but states a live design constraint a future edit must respect — legitimate WHY.
- **Docblock claims 3–8** — knowledge-reviewer verified each against the code and found them accurate: the `resolveNibsPath` docblock still matches its rewritten body; the inline `PersistentPreRunE` comment holds in both halves; the test's skip-list comment is correct (`show` is absent from `cmd/root.go:34-36`). Claim 3's "system defaults apply" elides the user-config layer but the docblock's first line already establishes it — elision, not contradiction. Claim 4's five-field list is accurate: all five exist in `NibsConfig` and none is a `UserNibsConfig` field, so all are genuinely wrong-able.
- **Sibling-consistency** (consistency-reviewer, 0 findings after a ~15-file sweep) — the hand-rolled `newConfigDiscoveryProject` matches the norm (every per-file test helper in `cmd/` lives in its own test file; `testhelpers_test.go` holds only package-wide utilities). Hardcoded `".nibs"` matches every sibling test. Using `config.ConfigFileName` is a deviation *toward* more correct symbolic reference. `"explicit"` and `"data directory"` vocabulary are both pre-established (`cmd/init.go:38`, `cmd/config.go:28`, `internal/config/userconfig.go:80`).
- **Test hermeticity against a real user config** — sound: `UserNibsConfig` has no `Prefix` field, so `~/.config/nibs/nibs.yml` cannot perturb `wantPrefix: ""`.
- **Test isolation** — no test in `cmd/*_test.go` calls `t.Parallel()`; `t.Cleanup` always fires after the subtest body. No race. `resetRootPersistentFlags` has its own regression test.
- **`--config A` + `--nibs-path B` cross-project mutation** — verified that `set-prefix` refuses before mutating either project. This is the nib's option 2 ("treat the mismatch as operator error"), a deliberate escape hatch.
- **`loadConfig` running before the data dir is validated** — a bogus `--nibs-path` walks from a nonexistent path first, but `resolveNibsPath` still surfaces the right error and no `Core` is built. Wasted work, no bad outcome.
- **`default_type` divergence** — `config.Default()` says `"task"` while `applySystemDefaults` says `DefaultTypes[0].Name` = `"milestone"`; two sources of truth that disagree. Confirmed by three agents that both the cwd project and the orphan mint `type: milestone`. Pre-existing, untouched by this diff, real `nibs init` projects unaffected (init writes `default_type: task` explicitly). **Worth a separate nib.**
- **Out of scope per brief** (not evaluated): `Archive`/`Unarchive`/`LoadAndUnarchive` mention-index maintenance; `Core.FindMentions` vs `FindMentionsInMap`; the `(?!-)` regex divergence; the Taskfile demo command.

---

## Session Metrics (--report)

**Wave timing**: review wave dispatched 2026-07-15 ~10:37Z (9 agents in one parallel message); `adversarial-reviewer` dispatched separately ~10:50Z after an orchestrator omission (see anomalies). Validation wave (11 agents) dispatched ~11:00Z in one parallel message. All calls `run_in_background: false`.

**Pre-flight gates** (run once, shared to all agents): build PASS (`task build`, zero warnings) · lint PASS (`task lint` / golangci-lint, `0 issues.`) · test PASS (`go test ./...` all packages ok; `go test -count=1 ./cmd/ ./internal/config/` ok). Web tests not re-run — diff touches no web files (requester reported svelte-check 0/0, 1222 passed).

### Reviewers

| Agent | Kind | Tier | Tokens | Tool calls | Duration | Findings submitted |
|---|---|---|---:|---:|---:|---:|
| quick-reviewer | reviewer | mid (sonnet) | 83,331 | 13 | 136,411 ms | 0 |
| broad-reviewer | reviewer | mid (sonnet) | 109,953 | 21 | 322,283 ms | 2 |
| go-reviewer | reviewer | mid (sonnet) | 105,169 | 13 | 338,332 ms | 1 |
| test-reviewer | reviewer | mid (sonnet) | 109,678 | 19 | 311,828 ms | 5 |
| spec-compliance-reviewer | reviewer | session | 85,882 | 20 | 309,589 ms | 2 |
| knowledge-reviewer | reviewer | session | 96,580 | 14 | 263,387 ms | 4 |
| consistency-reviewer | reviewer | mid (sonnet) | 101,462 | 23 | 294,239 ms | 0 |
| design-reviewer | reviewer | session | 100,546 | 19 | 390,399 ms | 5 |
| security-reviewer | reviewer | session | 84,266 | 11 | 183,104 ms | 2 |
| adversarial-reviewer | reviewer | session | 105,285 | 25 | 378,142 ms | 3 |
| **Reviewer subtotal** | | | **982,152** | **178** | | **24** |

### Validators

| Finding | Kind | Tier | Tokens | Tool calls | Duration | Verdict |
|---|---|---|---:|---:|---:|---|
| #1 out-of-tree regression | validator | mid (sonnet) | 86,400 | 32 | 230,124 ms | confirmed |
| #2 inner-config shadowing | validator | mid (sonnet) | 83,240 | 19 | 194,716 ms | confirmed (severity → Medium) |
| #3 `--config` typo | validator | mid (sonnet) | 69,865 | 17 | 280,079 ms | confirmed (→ pre-existing, Medium) |
| #4 unbounded walk | validator | mid (sonnet) | 89,217 | 29 | 307,653 ms | confirmed |
| #5 configDir overload | validator | mid (sonnet) | 94,638 | 23 | 185,458 ms | confirmed |
| #6 pairing invariant | validator | mid (sonnet) | 60,784 | 4 | 113,852 ms | **refuted** |
| #7 CLAUDE.md stale | validator | mid (sonnet) | 65,895 | 8 | 95,355 ms | confirmed |
| #8 t.Skipf gate | validator | mid (sonnet) | 70,060 | 17 | 134,803 ms | confirmed |
| #9 2-of-7 pass pre-fix | validator | mid (sonnet) | 64,791 | 9 | 118,925 ms | **refuted** |
| #10 weak assertions | validator | mid (sonnet) | 64,095 | 5 | 96,893 ms | confirmed (severity → Low) |
| #11 nib stale | validator | mid (sonnet) | 64,785 | 10 | 145,418 ms | confirmed |
| **Validator subtotal** | | | **813,770** | **173** | | **9 confirmed, 2 refuted** |

**Grand total**: 1,795,922 tokens · 351 tool calls · 21 agents.

All figures are the harness-reported `subagent_tokens` / `tool_uses` / `duration_ms` from each agent's tool result, verbatim. No figure is estimated. Durations are per-agent wall clock; agents within a wave ran concurrently, so wave elapsed time is far less than the sum.

### Anomalies

**3 anomalies.**

1. **Concurrent revert-probe race (significant — process defect, not a model defect).** `test-reviewer` performed its revert-probe by editing the **live** `cmd/root.go` inline (reverting `PersistentPreRunE` to pre-fix logic, then restoring byte-for-byte). `knowledge-reviewer`, running concurrently, read the file **inside that window** and received content showing the pre-fix logic under a `// PROBE: temporarily reinstated pre-fix logic for revert-probe verification.` comment. It correctly refused to trust the anomalous read, verified against `git diff`/`sed`/`grep`, found no `PROBE` marker on disk, and reported the tool result as fabricated — reasoning that was sound given its information, but the true cause was the concurrent probe, not fabrication. Had it trusted the read, it would have reported the fix as unimplemented, or "helpfully" restored it and clobbered the diff. Both agents left the tree byte-identical and both verified so. **Tree integrity confirmed by the orchestrator after the wave** (`git status --porcelain`: 2 modified files; diffstat 177/31 unchanged; no `PROBE` markers; fix present at `cmd/root.go:45`). The `adversarial-reviewer` prompt was subsequently amended to require scratchpad-copy probing, and all 11 validator prompts carried the same instruction — no further collisions occurred. **This is a real hazard of combining parallel dispatch with inline mutation probes and warrants a standing prompt rule.**
2. **Orchestrator dispatch omission.** `adversarial-reviewer` was announced in the review team but omitted from the parallel dispatch message (9 of 10 launched). It was dispatched separately once noticed and returned a Critical corroborating design-reviewer's — so no coverage was lost, but the wave was not fully parallel and the second dispatch benefited from knowing about the first wave's probe race.
3. **Untracked build artifact.** Validator #3 produced a `./nibs` binary in the repo root. It is gitignored and is the same artifact `task build` produces; no tracked file was affected.
