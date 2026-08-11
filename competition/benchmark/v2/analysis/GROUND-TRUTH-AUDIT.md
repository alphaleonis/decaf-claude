# Ground-truth audit — all 12 subjects (nib dcc-5xad)

Audited 2026-08-10 against METHODOLOGY-v2 §4. Evidence per subject in
`subject-NN/audit/` (`fix.diff`, `fix-pr.txt`, `pr-context.json`, `overlap.txt`), regenerable with
`v2/audit_subject.sh <id>`.

**Result: 5 of 12 subjects are unusable. The entire TypeScript row is gone.**

## Verdicts

| # | Subject | Lang/size | Verdict | Entries | Basis |
|---|---|---|---|---|---|
| 1 | efcore#32770 | C# / small | **usable** | ~2 | Issue #32944's stack trace lands on `Debug.Assert(rowIdForOrdinal!=null)`. The PR replaced a `-1` sentinel with a dict populated only when a rowid is found, so a table without one trips the assert. |
| 2 | aspnetcore#67075 | C# / medium | **usable** | 1 | Built in a prior session. Defect transformed by review; one provisional silent-fix. |
| 3 | runtime#127146 | C# / large | **replace** | 0–1 | Regression issue is a bare CI test-failure list, no mechanism. Total 13-file revert gives no localization. jkotas's only thread is a `.csproj` include question, not the cast failure. |
| 4 | TypeScript#61928 | TS / small | **replace** | 0 | Escaped defect is a downstream `Maximum call stack size exceeded` in eslint; never stated in TS's own terms. Revert author: "I'm not sure if it's worth the crashing… Some things have been fixed, but not everything." DanielRosenwasser's `languageVariant` point was *applied* during review — the merged code already has it optional. |
| 5 | vscode#308517 | TS / medium | **replace** | 0 | **Ground truth invalid** — see below. |
| 6 | vscode#320685 | TS / large | **replace** | 1* | No named bug: reverted because "TPI indicated more than normal regressions"; the linked item is a *test plan*, not a defect. mjbvz's unresolved temp-file thread is salvageable (*), but the escaped-defect metric is unavailable. |
| 7 | prometheus#13777 | Go / small | **usable** | 1 | Crispest in the corpus. The whole PR is the defect: `getChunkSeriesSet` defers `querier.Close()`, so the querier closes on helper return while the caller still iterates the returned set → use-after-close on mmap'd chunks. Root-caused by #14422. |
| 8 | k8s#129768 | Go / medium | **usable** | ~2 | Salvaged — see below. |
| 9 | k8s#130837 | Go / large | **usable** | 2 | Built in a prior session. Defects introduced at push #2; merged head is the better checkpoint (3 entries). |
| 10 | ripgrep#3185 | Rust / small | **usable** | 1 | Fix deletes the `while !free_buffer().is_empty() { read }` loop the PR added; body root-causes it precisely ("it ended up regressing `--line-buffered`"). |
| 11 | tokio#7757 | Rust / medium | **replace** | 0 | Prior session. Indicted ordering bug was fixed during review; the hang was never root-caused. **Verdict applies to the MERGED HEAD only** — see below. |
| 12 | rust#153540 | Rust / large | **usable** | ~3 | Richest key available. Fix undoes *one named commit* (`29e9273`), and issue #157107 states the user-visible regression exactly. 12 real threads. |

## Subject 5 — how ground truth goes invalid

The fixture's `bug_summary` says the idle timer "starts before yielding each chunk and leaves it
running during consumer processing." That sentence is copied nearly verbatim from a Copilot review
comment. The merged code does the opposite:

```js
startTimer(isFirstChunk ? SSE_FIRST_CHUNK_TIMEOUT_MS : SSE_IDLE_TIMEOUT_MS);
const result = await iterator.next();
clearTimer();                       // cleared BEFORE the yield
…
// Consumer processing time is NOT timed — the timer is cleared above
yield result.value;
```

All three bot findings were fixed before merge — the unhandled `destroy()` promise became
`void stream.destroy().catch(() => { })`, and the missing early-termination forwarding became
`await iterator.return?.()`. The fixture indicts a defect that is **absent from the reviewed diff**.

The actual revert reason (#308627) is a user-visible symptom, "Sorry, the response hit the length
limit," with no mechanism. So the escaped defect is unscorable and the stated one is false.

**This is the same failure as subject 11, and it has the same cause: the key was written from what
reviewers said, not from what the merged code does.** Any candidate drawn from a review comment must
be re-read against the checkpoint before admission — a bot or human comment is evidence that
something was *once* true, never that it shipped.

## Subject 11 — "replace" is a verdict on the merged head, not on the subject

The table's `replace / 0 entries` for subject 11 is about the **escaped** defect at the **merged
head**, and reading it as "subject 11 has no key" is wrong. `v2/analysis/subject-11/answer-key.json`
is a deliberate, current artifact: 2 entries at the **as-opened** checkpoint
`8d216da8281b` (2025-12-04), which `v2/subjects/11-rust-medium.json` pins to the same SHA. Both
entries are reviewer-flagged defects present in that diff and removed before merge.

Subject 11 is in fact the single case where the checkpoint machinery changed the answer
(METHODOLOGY-v2 §"Whether an earlier checkpoint helps"): the merged head has nothing scorable, the
as-opened head has the only scorable defect. Deleting the key would delete the evidence for that.

Two things follow, and both are load-bearing:

- Subject 11's 2 entries are **not** part of the anchor's 12-entry projection, which counts this
  subject as 0. Do not add them to it.
- Any scoring run must take a checkpoint from the fixture rather than assuming one. A key built at
  the as-opened head is invalid against the merged head — which is precisely what made the *v1*
  ground truth for this subject wrong.

Recorded 2026-08-11 by `dcc-3cm6`, which set out to delete this key as stale and found it was not.

## Subject 8 — root cause found in a source the methodology does not list

The revert body only speculates ("I *suspect* there were existing races… that the unconditional
delete masked") and the linked issue is a flake report. On that evidence subject 8 looks like subject
11 and would have been dropped.

The re-land attempt (#133995, still open) states both defects precisely:

1. On the retry path, "the Get we do on the reattempt should also react to a NotFound error in the
   same way" the original `Delete` tolerated it — otherwise a concurrently-deleted object surfaces as
   `not found` instead of the last-known state.
2. "The RV from the updated object must be used as the internal RV precondition" — the precondition
   used the pre-update resource version and so could never match.

Both are in `store.go`, inside the reviewed diff, and both yield a `must_flag`.

**Methodology gap: Step 5's candidate sources omit re-land / reattempt PRs.** They are frequently the
only place the mechanism is written down, because the revert is written in a hurry and the issue is
written by whoever saw the symptom. Add `cross-refs whose title reattempts the PR` to Step 5.
✅ **Actioned** — METHODOLOGY-v2 §4d Step A4 now covers re-lands, citing this subject.

## Two cross-cutting corrections

**The fixtures' `human_threads.count` counts comments, not threads.** Verified: subject 1 claims 4 →
2 threads / 4 comments; subject 8 claims 2 → 1 thread / 2 comments; subject 12 claims 27 → 12 threads
/ **exactly 27** comments (counted while building the key, `dcc-9ncz`; this section first estimated
"24+", and the exact figure makes the identity exact rather than approximate). This retroactively
explains the subject-2 discrepancy recorded earlier as "fixture
claims 9 human threads; API returns 4" — that was a mislabel, **not** evidence of fixture
unreliability, and the earlier note overstated the problem.

**Revert-body confidence language is a reliable triage signal.** Every subject whose revert names a
mechanism survived the audit (7, 10, 12, and 8 via its re-land). Every subject whose revert says
"suspect", "not sure", "more than normal regressions", or just links a CI failure failed it (3, 4, 5,
6, 11). This is cheap to check first and would have saved most of the audit cost — worth making Step
0 of the procedure.

## What the corpus looks like now

| Lang | Small | Medium | Large |
|---|---|---|---|
| **C#** | 1 ✅ | 2 ✅ | 3 ❌ |
| **TypeScript** | 4 ❌ | 5 ❌ | 6 ❌ |
| **Go** | 7 ✅ | 8 ✅ | 9 ✅ |
| **Rust** | 10 ✅ | 11 ❌ | 12 ✅ |

Seven survive. **TypeScript is eliminated entirely**, so the language×size grid no longer holds and no
claim about TypeScript review quality is available from this corpus.

### The ≥2-entry rule is the wrong test

Three survivors yield exactly one entry: subject 2 (built, 1 entry after an invalid one was
withdrawn), and subjects 7 and 10 by projection. The methodology's replacement criterion ("fewer than
~2 admissible entries… too thin to discriminate") would drop all three — including subject 7, the
single most valid subject in the corpus.

The rule conflates *thin key* with *small subject*. **The right test is whether the key is complete
for its diff, not how many entries it has.** Subject 7 is a 78-line single-file PR whose entire
content is the defect: one entry is a *complete* key, and a second would have to be invented. Subject
12 is a 383-line change across 18 files; one entry there would mean the key is unfinished. Judge
entry count against diff size and against what the PR actually does, and record that judgment.

What one-entry subjects genuinely cost is **per-subject precision**: with a single true positive you
cannot separate signal from noise within that subject, and each tool's result is one coin flip.
Recall pools across subjects fine, because it is computed over the union of entries. So one-entry
subjects are sound for the primary caught/missed metric and should be **excluded from per-subject
precision ranking** — not from the corpus. Settled in `dcc-595v`.

## Only two of the seven survivors are actually built

Surviving the audit is not the same as being usable. v2 fixtures and answer keys exist for subjects
**2 and 9 only**. Subjects 1, 7, 8, 10 and 12 have been validated but have no checkpoint, no fixture
and no key — each still needs the full §4 procedure. That work is `dcc-9ncz` and it, not the
replacements, is what gates the pilot.

## Vintage

> ⚠️ **Superseded cutoff.** This section was written against the roster's Jan 2026 cutoff. `dcc-f2nf`
> subsequently made the binding cutoff **Opus 5's 2026-05**, since `BENCH_MODEL` and the judge are
> both Opus 5 (METHODOLOGY-v2 §5). Read the figures below as a record of the audit, not as the rule.
> "Merged after 2026-01" under *What replacements must satisfy* is likewise superseded.

Only three subjects postdate the roster's Jan 2026 training cutoff — 3, 6 and 12 by their fix dates,
though 3 and 6 are being replaced. Subjects 1 (2024-01), 7 (2024-03), 8 (2025-09) and 10 (2025-10)
all predate it, so memorization is unbounded for most of the surviving corpus. Replacements should be
sourced from PRs merged after the cutoff wherever possible (`dcc-f2nf`).

## What replacements must satisfy

Sourcing 5 replacements (3 of them TypeScript) is its own task — filed separately rather than
attempted here. Screening order, cheapest first:

1. The revert/fix body **names a mechanism**, not just a symptom or a CI link.
2. The indicted defect is **present in the merged diff** — read the code, do not trust the comment.
3. A `must_flag` sentence can be written for at least two entries.
4. Merged after 2026-01 for vintage safety, and lightly force-pushed.
