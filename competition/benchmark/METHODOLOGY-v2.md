# Benchmark v2 — methodology

**Status: DRAFT.** Design under discussion; nothing here is implemented. Tracking nib: `dcc-ho2w`.
The v1 grading methodology is `analysis/METHODOLOGY.md` and still describes how findings are
extracted, clustered, and graded — v2 changes *what is reviewed* and *what the reviewer may see*,
not the grading machinery.

---

## 1. Why v2

v1 measured one thing: did the reviewer find the defect that escaped human review and forced a
follow-up fix. Three independent leak channels invalidated it, all confirmed by measurement:

| Channel | Evidence |
|---|---|
| GitHub cross-references | 11 of 12 subjects have the fixing/reverting PR auto-linked on the original's timeline. Subject 9's linked item is titled *"proxy: node-manager ignores timeouts to get NodeIPs"* — the bug, in a title. Only subject 5 has zero. |
| Review threads / revert bodies | The answer key's human issues are drawn verbatim from unresolved threads. `anthropic-code-review`'s finders cite the revert PR in **both** repeats; decaf's consolidated reports name the human reviewers 2–12×. |
| Training-data memorization | 6 of 10 dated subjects predate the benchmark model's Jan 2026 training cutoff. The judge's cutoff is May 2026. Unfalsifiable, worsens with every release. |

Plus two problems with the metric itself: reviewing the **merged head** means every in-review fix is
already folded in (44 of subject 9's 46 threads are unfindable by construction), and subjects carry
0–30 human threads, so any thread-derived metric is unavailable on a third of the corpus.

---

## 2. What v2 reviews: the review checkpoint

A **checkpoint** is a head SHA at a chosen point in the PR's life — most usefully the as-opened head.
This is the unit of review, replacing v1's "merged head". The reviewer sees the diff at that SHA and
nothing else.

The threads written against a checkpoint are *one* input to its answer key, not the key itself; §3
covers how the key is actually built.

Reconstruction is possible because **GitHub preserves force-pushed commits**. Every force-push is
recorded as a `HeadRefForcePushedEvent` carrying `beforeCommit`/`afterCommit` oids, and those commits
stay fetchable from the repo network indefinitely.

Verified on subject 9 (`kubernetes/kubernetes#130837`, opened 2025-03-15, force-pushed 13×): the
as-opened head `be7da1315a3c` — force-pushed away the same day, 15 months ago — fetches cleanly, and
diffs against merge-base `18e5a4d585f6` to 11 files, +342/−426 (vs 18 files, +757/−803 as merged).

**Every checkpoint has its own merge base.** Compute it per head
(`compare/<target-branch>...<head>` → `merge_base_commit`); do not reuse the as-opened base. Long-
lived branches absorb the target branch as it advances, so comparing a later head to the original
base drags in every unrelated change merged in between — on subject 9 that inflates push #3 from
18 files to **240 files, +12663/−5081**. That is a wrong diff, not a large one.

### Choosing the checkpoint

**Pick the earliest head at which the defect under study is already present.** That maximizes how
much of the PR's remaining lifecycle is admissible to the key (§3) while keeping the defect in scope.
The as-opened head is the right choice only when the defect was there from the start.

Where a PR was lightly rewritten (0–3 force-pushes), the earliest head is usually as-opened and every
thread attaches to it. Where it was heavily rewritten, locate the introducing push by walking the
force-push heads and testing for the defect's signature — cheaply, via
`repos/<owner>/<repo>/contents/<path>?ref=<sha>`, one file per head, no tree fetches.

Threads target whichever head existed when they were written, so a thread may name a file absent from
an earlier checkpoint (on subject 9: `pkg/proxy/topology.go`, `pkg/proxy/kubemark/hollow_proxy.go`).
Those are excluded by the §3 admission rule, not by hand.

---

## 3. What v2 measures: three instruments

**Decided 2026-08-10 (`dcc-595v`), replacing the key-only framing.** The retrospective key is one
instrument of three, and it is not the one that ranks tools.

The forcing fact is arithmetic. After the ground-truth audit the key-based corpus carries **12
scoreable entries across 7 subjects**. Five tools x 2 repeats against 12 binary items cannot separate
a 50%-recall tool from a 70%-recall one — that is structural, not imprecision. Meanwhile a single v1
subject produced **800 findings collapsing to 98 distinct clusters**, of which the blind judge called
1 `TP-primary`, 2 `TP-human`, 31 `valid-other`, 58 `nitpick` and 6 `false-positive`.

Read that distribution carefully: only 6 of 98 findings were *wrong*, and 58 were *trivial*. **Review
tools do not fail by being incorrect; they fail by being immaterial.** Per-tool volume ranged 38 to
180 findings. A key-based metric is blind to all of it, while answering only "did you find the bug" —
when the question that decides adoption is "did you find it, and how much noise came with it."

| Instrument | Scored against | Measures | Ranks tools? |
|---|---|---|---|
| **Pooled adjudication** | the union of what the tools said | precision, nitpick ratio, unique real findings, noise per cell | **yes — this is the ranking instrument** |
| **Human review threads** | what expert reviewers said | **recall against expert human review — the miss detector** | contributes |
| **Retrospective key (the anchor)** | what production found later | whether a defect class is missed by *every* tool, humans included | no — n is too small |
| **Null arm** | nothing — no known defect | absolute noise floor | no — calibrates the others |

Each covers another's blind spot, and the middle two are the reason this is not circular.

Pooled adjudication is **bounded by the union of tool output**: if every tool shares a blind spot,
they all score full recall against a pool missing the same thing. It cannot, by construction, tell
you what was missed.

**Human review threads fix most of that, and they are the reason to insist on review-disciplined
repos.** A thread is an independent statement that something was worth raising, written by an expert,
and *not derived from tool output*. So "expert reviewers flagged X and no tool flagged X" is a
detectable miss — the thing pooled adjudication is blind to. This is dense signal: it exists on every
well-reviewed PR, unlike the escaped defect, which needs a revert.

Thread density therefore becomes a **corpus selection criterion**, not an accident. The v1 corpus
averaged badly (15 threads across five subjects, 12 of them on one) because it was selected for
reverts; selecting for review discipline means requiring substantive threads up front.

The anchor still earns its place above both: it catches what expert reviewers *also* missed, which is
a different and rarer question. And pooled precision is relative to the pool rather than to truth,
which is what the null arm fixes.

Two honest limits on thread-based scoring:

- **Threads need the admission rule.** A thread written against a later push may not apply at the
  checkpoint, and threads carry plenty of non-defects — style preferences, questions, renames,
  approvals. Both are handled by the existing machinery (in-diff check, then the `must_flag` test),
  and it is far cheaper here than for escaped defects: a thread is concrete text with a file:line
  anchor, so the mechanical pre-filter does real work. What is *not* needed is the expensive part —
  researching the revert, the re-land, the regression issue and the root cause, which is what made 5
  of 12 subjects fail.
- **Human review is itself biased.** OSS reviewers weight API design, naming and project convention
  heavily and often delegate correctness to CI. So thread recall measures agreement with expert
  review, which is *related to* but not identical with finding real bugs. Report it as its own axis;
  never merge it into a single "recall" number with the anchor.

Threads must be unreachable from inside a cell — the `gh` shim already denies `--comments` and the
review-thread fields, and that denial is now load-bearing for scoring, not just for leak hygiene.

### Pooled adjudication

Run every tool on the same checkpoint. Pool all findings, cluster them into distinct claims, and have
a judge — blind to tool identity — adjudicate each cluster. **No answer key is involved**, which is
the point: it removes the failure mode that invalidated 5 of 12 subjects, and with it the revert
requirement, Steps 5-7 of section 4, and most of the leak and vintage exposure.

Consequences for subject selection: a subject no longer needs a revert, a regression issue, or a
named mechanism. It needs to be a **substantive change in a repository with genuine review
discipline, carrying real human review threads**, merged after the roster's training cutoff. The
threads are not a bonus — they are the miss detector described above, and they double as a
calibration check on the judge, since an adjudicator that systematically dismisses what expert
reviewers raised is visibly miscalibrated.

Known weaknesses, to be mitigated rather than assumed away:

- **The judge becomes the ground truth**, and it shares a model family with the tools, so shared
  false beliefs go undetected. Require a code citation for every verdict, use adversarial
  verification (several judges prompted to *refute*), and spot-check the `valid-other` / `nitpick`
  boundary by hand — that is where the subjectivity concentrates.
- **Volume is rewarded**: more findings means more chances at a unique real one. Precision is the
  primary metric; recall-against-pool is secondary; findings-per-cell is always reported alongside.
- **"Real" is not binary.** v1's precision was severity-unweighted, so four minor findings outscored
  one revert-forcing defect. Severity weighting is required, not optional.

### The anchor: one retrospective key

The 7 audited subjects keep their keys and their value, with a narrowed job: detecting a defect class
that *every* tool misses. That is a yes/no about the whole field, for which 12 entries is adequate.
It is not used to rank.

### The key question

Not *"what did reviewers say against this head?"* but:

> **Given everything the world eventually learned about this PR, which of those findings were already
> true of the code as it stood at checkpoint T?**

This subsumes what earlier drafts split into "replication" and "escape" tracks. A thread written in
June describing a problem already present in March belongs in the key — the reviewers simply didn't
notice it until June. A post-merge defect whose root cause existed at T belongs in it. A thread about
code introduced *after* T is excluded, however substantive it is.

The escaped bug is therefore not a separate category. It is one entry among others, distinguished
only by its provenance tag: discovered by production rather than by review.

### Candidate sources (all of them)

Everything in the PR's lifecycle and its aftermath is a candidate:

- review threads from every round, resolved and unresolved alike
- changes made between pushes that fixed something nobody commented on
- the PR description and any linked issue
- follow-up PRs that fixed defects this PR introduced (subject 9's revert + take-2)
- post-merge issue reports attributing a regression to this PR

### The admission rule: presence at T

**Every candidate entry must be shown present in the code at checkpoint T.** This is the single
admission rule, applied uniformly — not a special gate for post-merge defects.

**For a change-shaped finding ("X was dropped", "Y was replaced"), presence in the tree is not
enough — it must be visible in the `base..checkpoint` DIFF.** The reviewer sees that diff and nothing
else. A finding derived from comparing two *heads* to each other can describe a change that never
appears in the reviewed diff, and is therefore unflaggable. This is not hypothetical: subject 2's
original e2 claimed the restructure dropped `BindingFlags.IgnoreCase`, but the base had no
BindingFlags at all — IgnoreCase lived only in an intermediate head. It was withdrawn after the
first review cell reported everything else and correctly ignored it.

Mechanical pre-filters narrow the candidate set before human judgment is needed:

- does the thread's file exist in the checkpoint diff?
- does its line range fall inside the checkpoint's changed hunks?
- does `git blame` on the fix's deleted lines trace to a commit reachable from the checkpoint head?

**Measured effectiveness: much weaker than expected.** On subject 9 at push #2 the file filter
rejected **0 of 46** threads, because that push already touches all 18 files the merged PR touches.
Only 13 of 46 threads carry a live line number (33 are marked outdated), so the line filter is
inapplicable to most. Do not plan on the mechanical filters carrying the work — on a mid-PR
checkpoint they may reject nothing at all.

What actually collapses the set is the `must_flag` test applied as triage (below): on subject 9 it
removed ~35 naming, wording, refactor-preference and test-ergonomics threads as a class, leaving ~9
to verify individually against the checkpoint code.

**The residual judgment is irreducible and must be done by hand** (human, or human-supervised LLM).
Deciding whether a June comment describes a March defect requires reading the code at both points.
This is the expensive artifact of the whole design — and it is one-time per checkpoint, reused across
every tool, repeat, and future run, so it amortizes well.

It is safe to build with total access to the fix PR, the threads, and the post-merge issues,
**because the reviewer never sees it.** Only the judge does.

### Whether an earlier checkpoint helps is subject-dependent — measured, not assumed

The plausible theory was: at T = merged head only post-merge discoveries apply, so an earlier
checkpoint admits more of the lifecycle. **Building two keys showed the theory is wrong as a general
rule.** It depends entirely on whether the subject's defects were *introduced* or *removed* during
review, and that is knowable only by building the key.

Three subjects, three patterns:

| | Subject 9 (k8s #130837) | Subject 11 (tokio #7757) | Subject 2 (aspnetcore #67075) |
|---|---|---|---|
| What review did to the defect | **introduced** it (push #2) | **removed** it | **transformed** it |
| Entries at an early checkpoint | 2 | ≥1 (the only scorable defect) | different, weaker shape |
| Entries at the merged head | 3 | **0 scorable** | the indicted defect |
| Better checkpoint | **merged head** | **as-opened** | **final head ≈ merged** |

So there is no default. Locate the defect first (Step 2), then let its presence decide the
checkpoint.

**Sobering count: the checkpoint machinery changed the answer in 1 of 3 subjects** — and in that one
(subject 11) only because the merged head turned out to be unscorable. On this evidence the
checkpoint idea is not v2's main value. What earned its keep across all three was the leak-proofing
in §5 and the key-building discipline in §4 Step 6, which caught **two invalid v1 ground truths**
(subjects 11 and 2) before either cost a review cell.

### A subject can turn out to be unscorable

Subject 11's *escaped* defect — `spawn_blocking` hangs, which forced a revert and a point release —
**was never diagnosed**. The reporter bisected to the merge commit but had no minimum reproducer, and
the maintainer records that the hang persisted with `NUM_SHARDS` set to 1. There is no defect
statement, so no `must_flag` can be written, so it cannot be scored.

This is not a gap in the method; it is the method refusing to grade reviewers against a defect nobody
has identified. **Expect to discover it only while building the key** — and treat "the subject is
unscorable" as a valid, publishable outcome of Step 6 rather than a failure.

It also caught a **misattributed v1 ground truth**: subject 11's fixture states the ordering bug as
the escaped defect, fusing a real reviewer finding (fixed during review — the code is absent from the
merged diff) with a real but undiagnosed production hang. Scoring against that key on the merged head
would have graded tools against a defect not present in the diff they reviewed.

### Worked check: subject 9

Walking the 13 force-push heads and reading `pkg/proxy/node.go` at each (one API call per head, no
tree fetches) locates both defects precisely:

| Push | Date | Head | `node.go` | `NewNodeManager` | Exit path |
|---|---|---|---|---|---|
| #0 opened | 2025-03-15 | `be7da1315a3c` | 91 | no error return | 2× `FlushAndExit` |
| #1 | 2025-03-15 | `a0c5cb55f9c9` | 91 | no error return | 2× `FlushAndExit` |
| **#2** | **2025-03-18** | **`2ccd845497ee`** | **167** | **returns error** | **3× `Flush()`** |
| #3–#8 | to 2025-06-08 | … | ~190 | returns error | 3× `Flush()` |
| #9 | 2025-06-22 | `7841a3e74d14` | 235 | returns error | 2× `FlushAndExit`, 2× `Flush()` |
| #10 | 2025-06-23 | `26a42d63228d` | 190 | returns error | 3× `Flush()` |
| #13 merged | 2025-07-11 | `46e2c22fd766` | 189 | returns error | 3× `Flush()` |

**Both defects entered in a single push, three days after the PR opened**, and survived eleven more
pushes and four months of review. Push #9 is worth noting on its own: `FlushAndExit` was restored on
2025-06-22 and gone again the next day — the h1 fix existed briefly and was lost.

The PR also reached its final shape at push #2. Diffs against each head's own merge base:

| Checkpoint | Base | Diff |
|---|---|---|
| #0 as-opened | `18e5a4d585f6` | 11 files, +342/−426 |
| **#2** | `8559194e118f` | **18 files, +745/−727** |
| merged | (merge^1) | 18 files, +757/−803 |

So **push #2 is the checkpoint to use for subject 9**: the defect is present, the diff is a full-size
realistic review (745 lines vs 757 at merge), and 29 of the 46 threads — 10 of them unresolved — are
still ahead of it and admissible, plus the escaped bug and h1 from post-merge. That is roughly **31
candidate key entries, against 2 at the merged head.**

One review run, not two. The earlier worry that split-defect subjects need a second run was wrong:
the right checkpoint is the earliest head containing the defect, and that single point serves both
purposes.

Subject 9 remains awkward as a *routine* subject — locating push #2 took a deliberate walk of 13
heads — but it is no longer disqualified, and the walk is cheap and scriptable.

---

---

## 4. Subject construction: from PR to checkpoint + key

**This section is a checklist, not an explanation.** Subjects must be built identically across
sessions and across whoever (or whatever) builds them — a checkpoint chosen by one rule and a key
admitted by another produce scores that cannot be compared. Follow the steps in order and record the
evidence each one produces; where a step needs judgment, it says so explicitly and the judgment gets
written down rather than made silently.

The procedure turns a candidate PR into two artifacts:

- **the review fixture** — what the reviewer is given (a commit + a diff range)
- **the answer document** — what the judge scores against (the retrospective key)

Every command shown has been run against subject 9. `O`/`R`/`N` are owner, repo, PR number.

### Step 0 — Triage on the fix's confidence language

Before spending anything, read the revert/fix PR body and ask one question: **does it name a
mechanism, or only a symptom?**

This predicted every outcome in the 12-subject audit (`v2/analysis/GROUND-TRUTH-AUDIT.md`). Subjects
whose fix named a mechanism all survived; every subject whose fix said "I suspect", "not sure if it's
worth", "more than normal regressions", or merely linked a CI failure turned out to have an
unscorable defect. A symptom-only fix means nobody ever wrote down what the reviewer should have
caught, and Step 6 will not be able to invent it.

A symptom-only body is not an automatic rejection — subject 8's mechanism turned up in the re-land
PR (see Step 5) — but it means: go looking for the mechanism *now*, and drop the subject if no source
states one.

### Step 1 — Inventory the PR's heads

```sh
gh api graphql -f query='
{ repository(owner:"O", name:"R") { pullRequest(number:N) {
  createdAt
  timelineItems(first:100, itemTypes:[HEAD_REF_FORCE_PUSHED_EVENT]) {
    nodes { ... on HeadRefForcePushedEvent { createdAt beforeCommit{oid} afterCommit{oid} } } } } } }'
```

The candidate heads are: the **as-opened head** (the first event's `beforeCommit`, or the PR head if
there were no force-pushes), then each event's `afterCommit` in order.

> ⚠️ **Force-pushes do not enumerate all heads.** Ordinary pushes move the head without emitting a
> timeline event, so the chain has gaps — a later event's `beforeCommit` will not match the previous
> event's `afterCommit`. On subject 11, four such gaps appear among 18 force-pushes. Treat the
> force-push heads as *samples*, and fall back to the PR's commit list when the introducing push must
> be located precisely.

> ⚠️ Do **not** read `timelineItems.totalCount` as the force-push count — it counts all timeline item
> types regardless of the `itemTypes` filter. Subject 9 reports 113 there and has 13 force-pushes.
> Count the returned nodes.

### Step 2 — Locate the defect-introducing push

Read the file the defect lives in at each head, cheaply — one file per head, no tree fetches:

```sh
gh api "repos/O/R/contents/<path>?ref=<sha>" --jq '.content' | base64 -d
```

Grep each for the defect's signature (a changed function signature, a swapped call, an added
timeout). The checkpoint is the **earliest head where the signature is present**.

> ⚠️ **A full revert gives no line-level localization.** Where the follow-up "fix" simply reverts the
> whole PR (subject 11: `rt: revert #7757`, −340 lines, deleting the added file), blame tells you
> nothing — every line was deleted. Derive the signature from the review discussion or the linked
> issue instead. If neither states a mechanism, see Step 6: the subject may not be scorable at all.

If the defect is present at the as-opened head, stop — that is the checkpoint, and it is the ideal
case. Record the walk either way; it is the evidence for the checkpoint choice.

### Step 3 — Compute the checkpoint's own merge base

```sh
gh api "repos/O/R/compare/<target-branch>...<checkpoint-sha>" --jq '.merge_base_commit.sha'
```

**Per checkpoint, never reused.** A long-lived branch absorbs the target branch as it advances;
reusing an earlier base drags in every unrelated change merged between (subject 9: 18 files → 240).

Sanity-check the resulting diff against the merged PR's size. A checkpoint diff wildly larger than
the merged diff means the wrong base.

### Step 4 — Build the review fixture

```sh
git init -q "$REPO_DIR" && git -C "$REPO_DIR" remote add origin "https://github.com/O/R"
git -C "$REPO_DIR" fetch -q --depth 500 origin <checkpoint-sha>   # ONE fetch only
git -C "$REPO_DIR" checkout -q -f <checkpoint-sha>
git -C "$REPO_DIR" clean -qxfd
git -C "$REPO_DIR" remote remove origin
```

Depth 500 (not 2) so history exploration works offline — see §5 Tier 0. Ancestry guarantees nothing
later is reachable at any depth. Dropping the remote prevents a later fetch from pulling newer state.

> ⚠️ **Fetch the checkpoint and nothing else.** The merge base is an ancestor of the checkpoint, so it
> arrives with it. A second `fetch --depth 1` of the base **re-shallows the repository** and discards
> the deep history you just fetched — observed on subject 9: 129,013 commits collapsed to 7. Verify
> with `git rev-list --count HEAD` after building; a three-figure result means the history was
> truncated.

Fixture fields, extending the v1 schema:

```json
{
  "id": 9, "lang": "go", "size": "large", "repo": "kubernetes/kubernetes", "pr": 130837,
  "checkpoint": {
    "sha": "2ccd845497ee...", "base": "8559194e118f...",
    "date": "2025-03-18T15:12:04Z",
    "push_index": 2, "push_count": 13,
    "selection": "earliest head containing the defect",
    "diff_stat": { "files": 18, "additions": 745, "deletions": 727 }
  }
}
```

### Step 5 — Gather candidates for the key

```sh
gh api graphql -f query='
{ repository(owner:"O", name:"R") { pullRequest(number:N) {
  reviewThreads(first:100) { nodes {
    isResolved isOutdated path line
    comments(first:10){nodes{author{login} createdAt bodyText}} } }
  timelineItems(first:100, itemTypes:[CROSS_REFERENCED_EVENT]) {
    nodes { ... on CrossReferencedEvent { source {
      ... on PullRequest { number title url } ... on Issue { number title url } } } } } } } }'
```

Candidate sources are listed in §3. **Also check the cross-references for a re-land** — a PR whose
title reattempts this one ("Reattempt of #N", "WIP - <original title>", "Reland: …"). The re-land is
often the *only* place the defect is stated precisely, because the revert was written in a hurry and
the issue was written by whoever saw the symptom. Subject 8's two key entries exist only because
#133995 enumerated the gaps; on the revert body alone ("I suspect there were existing races") it
would have been dropped as unscorable.

Also diff consecutive heads (`compare/<head_i>...<head_i+1>`) to
surface **silent fixes** — changes the author made that corrected something nobody commented on.
These leave no thread, so a thread-driven key misses them entirely.

**Silent fixes are the least certain candidate class and need a higher bar than the rest.** Most
inter-push change is not a fix: rebases, renames, feature work, CI-driven churn, and the author
changing direction all look similar in a diff. Admitting those inflates the key with entries no
reviewer should have raised, which depresses every tool's recall equally — unbiased, but noise.

Admit a silent fix only when **all** of these hold:

- it is small and localized, not a rewrite or a change of approach
- it has a defect-fix shape — an added nil/bounds check, a corrected comparison or off-by-one, a
  an added cleanup or release, a repaired error path — or a commit message that says so
- no existing thread already covers it (otherwise it is that thread's entry, not a new one)
- **you can write the `must_flag` sentence**: what a reviewer would have had to say to catch it

That last one is the decisive test, because it is decidable where "was this a fix?" is not. If the
finding cannot be stated as something a reviewer should have said, it cannot be scored, and it does
not belong in the key regardless of how clearly the author fixed something.

Tag admitted silent fixes `provenance: "silent-fix"` and **report their contribution separately in
the first few runs**. If they prove noisy, they can be dropped from scoring without rebuilding any
key.

### Step 6 — Apply the admission rule mechanically, then by hand

Mechanical pre-filters first (§3): file present in the checkpoint diff, line inside a changed hunk,
`git blame` on the fix's deleted lines reaching the checkpoint head. These reject the clearly
inapplicable without judgment.

Then adjudicate what survives **by hand**. For each candidate, the question is not "is this a real
finding" but *"was this already true of the code at the checkpoint?"* — which requires reading the
code at the checkpoint and at the point the finding was made. This step is irreducible; see §3.

> ⚠️ **A review comment proves something was once true, never that it shipped.** Subjects 5 and 11
> both had keys written from what reviewers said, and in both cases the merged code did the opposite
> — subject 5's fixture indicts an idle timer that "leaves the timer running during consumer
> processing" when the merged code clears it before `yield` and says so in a comment. Every candidate
> drawn from a thread, a bot comment or a linked issue must be re-read **against the code at the
> checkpoint** before admission. This is the single most common way a key goes invalid.

**The `must_flag` test applies to every entry, not just silent fixes.** If a candidate cannot be
stated as a specific thing a reviewer would have had to say, it cannot be scored — drop it. This is
what keeps a key from accumulating vague entries ("the error handling here is weak") that no verdict
can be reached against.

Record rejections as well as admissions. A key that shows what was considered and excluded is
auditable; one that shows only survivors is not.

### Step 7 — Write the answer document

`analysis/subject-NN/answer-key.json`:

```json
{
  "subject_id": 9,
  "checkpoint": { "sha": "2ccd845497ee...", "date": "2025-03-18T15:12:04Z" },
  "built_at": "2026-08-10", "built_by": "operator",
  "entries": [
    {
      "id": "e1",
      "statement": "NewNodeManager returns a fatal error when NodeIPs cannot be fetched; newProxyServer propagates it, aborting kube-proxy startup where the previous code degraded to a localhost fallback.",
      "file": "pkg/proxy/node.go", "locus": "newNodeManager poll → `return nil, err`",
      "provenance": "post-merge-fix",
      "source_ref": "https://github.com/kubernetes/kubernetes/pull/133059",
      "discovered_at": "2025-07-24",
      "admission_evidence": "present at checkpoint: error return introduced at push #2, which IS the checkpoint",
      "must_flag": "flags that NodeIP-fetch failure now aborts startup where it was previously non-fatal",
      "severity_hint": "critical"
    }
  ],
  "rejected": [
    {
      "candidate": "thread: pkg/proxy/topology.go naming",
      "source_ref": "<thread url>",
      "reason": "file absent from the checkpoint diff — introduced after push #2"
    }
  ],
  "notes": "13 force-pushes; both the escaped defect and h1 entered at push #2, 3 days after opening."
}
```

`provenance` ∈ `review-thread` · `silent-fix` · `linked-issue` · `post-merge-fix` ·
`post-merge-issue`. It is metadata for analysis — **not** a scoring weight. A finding is not worth
more because production found it rather than a reviewer.

### Step 8 — Verify the fixture is airtight before spending on cells

```sh
git -C "$REPO_DIR" log --oneline --all | head          # must not reach the fix/revert
git -C "$REPO_DIR" status --porcelain                  # must be empty
git -C "$REPO_DIR" remote -v                           # must be empty
grep -rlE '<fix-pr-number>|<revert-pr-number>' "$REPO_DIR"   # must find nothing
```

Then run one cell and audit its access log (§5 Tier 3) before authorizing the rest.

## 5. How review agents run: time-boxing, not blanket denial

The requirement is **"nothing dated after the checkpoint"** — not "nothing external". Blanket-denying
`gh` and `WebFetch` also denies legitimate reference lookup (library APIs, prior related PRs), which
is part of competent review and part of what these tools are being measured on.

Four tiers, by whether access can be date-bounded.

### Tier 0 — free, safe by construction: local git

Git ancestry **is** a time boundary. A checkout at the checkpoint SHA cannot reach anything merged
later — descendants are unreachable, verified on `repos/9` (no refs, 3 reachable commits, revert
absent). So `git log`, `git blame`, `git show` of prior merge commits are all safe, and they cover
"look at the prior related PRs" legitimately.

**This requires deepening the clone.** v1's `--depth 2` leaves 3 commits — no history to explore,
which is very likely *why* tools reach for the network. Fetch `--depth 500` (or `--shallow-since`)
from the checkpoint SHA; depth is measured backwards, so nothing later can appear at any depth. Then
`git remote remove origin` so no later fetch can pull newer state.

### Tier 1 — time-boxed: a `gh` shim

Replace `gh` with a PATH shim that:

- allowlists read-only subcommands (`pr view`, `pr diff`, `issue view`, `pr list`)
- resolves the target's `createdAt` and **refuses if newer than the checkpoint date**
- strips timeline items, comments, and cross-references newer than the checkpoint from its output
- denies `gh api`, `gh api graphql`, and `gh search` outright — arbitrary queries cannot be
  date-bounded generically, and graphql is exactly how the cross-reference leak was demonstrated
- logs every invocation with subcommand, target, resolved date, and allow/deny

This preserves the legitimate case (reading the issue a PR closes, which predates it) while making
the leak mechanically impossible.

### Tier 2 — date-pinned: `docs-at` replaces WebFetch

`WebFetch` and `WebSearch` are harness built-ins, **not PATH-shimmable**. They can only be allowed
wholesale or disallowed via CLI flag. So: disallow both, and provide a `docs-at <url>` script that
fetches through the Wayback Machine pinned to the checkpoint date
(`https://web.archive.org/web/<YYYYMMDD>/<url>`), falling back to a curated allowlist of
version-stable documentation domains when no snapshot exists.

The agent keeps documentation lookup — time-accurate to the PR, which is arguably *better* than
current docs for reviewing historical code. Coverage is imperfect (not everything is archived, and
rate limits apply), and that limitation should be reported rather than hidden.

MCP documentation servers (context7 and similar) serve *current* docs with no date parameter. Deny by
default; if enabled for a run, record it in `meta.json` so affected cells are identifiable.

### Build and test capability

Decided 2026-08-10 (`dcc-fhp1`). Cells get a working toolchain, because a review that cannot execute
anything is biased against exactly the defects that need execution to confirm — races, ordering,
lifetime, hangs. Every subject-2 cell in the earlier runs reported "no dotnet SDK", and one claimed
sub-agents had verified reflection behaviour empirically, which was neither reproducible nor true.

**Restore must be frozen, or it is a time-boxing hole.** A package restore reaches the network, and
an unpinned restore resolves *latest* — which can pull a version published after the checkpoint,
opening through the back door what the `gh` shim closes at the front. Every subject in the corpus
carries a pinned dependency set (`pnpm-lock.yaml`, `yarn.lock`, `go.sum`, `uv.lock`, or .NET central
package management), so the frozen variant is always available: `pnpm install --frozen-lockfile`,
`yarn install --immutable`, `GOFLAGS=-mod=readonly go mod download`, `uv sync --frozen`,
`cargo fetch --locked`. `v2/detect_build.sh` reports `date_neutral: false` rather than building a
subject without a lockfile.

**The toolchain must be put on PATH deliberately.** Tools installed via a per-shell version manager
are absent from the non-interactive shell a cell inherits — observed: `go` and `dotnet` both
installed yet unreachable, with a stale empty `/usr/local/go/bin` on PATH masking the real one. Left
unfixed every cell silently degrades to static analysis. `v2/toolchain.sh` fixes this and is sourced
**before** the shim directory, so the time-boxed `gh` still wins.

**Node is pinned across the corpus**, like the model and the effort. Version managers do not honour a
project's `.nvmrc` through their shims, so a checkout resolves to the manager's default — and most
subjects declare `engines` excluding it. One version satisfying every subject is chosen and held
constant.

**Having the runtime is not the same as being able to build.** A project may pin an SDK its
`rollForward` policy forbids a newer one from serving: in this corpus one subject pins .NET 8.0.0
with `latestMinor` and cannot build under SDK 10, while another pins a 9.0 preview with
`latestMajor` and can. Detection resolves this up front rather than letting a cell discover it.

Each cell records `build-capability.json`, so a run without a toolchain is **identifiable rather than
quietly weaker**. Never compare a cell that could execute against one that could not without saying
so.

⚠️ Full test suites are expensive — one .NET unit-test project here ran past nine minutes without
finishing. Cells are told the capability exists and to prefer the tests covering the changed code.
There is no universal "run the tests" command: invocation is per subject, and treating it as uniform
will silently produce cells that ran nothing.

### Tier 3 — audit, not only prevention

Every channel is **logged, denied at the harness level, or explicitly named as unmeasured**. Decided
2026-08-10 (`dcc-wzbe`); `v2/leak_audit.sh` prints this per cell, including the unmeasured rows,
because a channel without its own log has exactly the blind spot that made output-grepping undercount
leaks.

| Channel | Treatment |
|---|---|
| `gh` | shimmed and time-boxed; every call logged with its verdict |
| `curl` / `wget` | **shimmed**: GitHub hosts denied, everything else permitted and logged |
| `docs-at` | shimmed; the snapshot date is now **enforced**, not merely printed |
| WebFetch / WebSearch | denied via `--disallowedTools` (harness built-ins, not PATH-shimmable) |
| MCP servers | denied via `--strict-mcp-config` with an empty config |
| package registries | permitted and logged; the frozen-lockfile rule keeps versions date-neutral |
| memorization | **unmeasured** — unfalsifiable by construction, bounded only by vintage (section 6) |
| other HTTP clients | **unmeasured** — a language HTTP library or a package manager's own transport |

Three of these were live holes, found by testing rather than reasoning:

- **`curl` bypassed the entire `gh` shim.** `curl https://api.github.com/repos/O/R/pulls/N/comments`
  returns the same review threads the shim exists to withhold. Cells need real network for package
  restore, so the shim denies GitHub hosts and logs the rest rather than denying wholesale.
- **`docs-at` did not enforce its own pin.** Wayback's `/web/<stamp>/` returns the *closest* snapshot,
  which is usually a later one — a request for 2015 returned a 2021 capture, and a request for
  2026-05-01 returned 2026-05-21. The date was printed but never checked. It now bounds the query
  through the CDX index (`to=<stamp>&limit=-1`), taking the most recent capture **at or before** the
  checkpoint, and still refuses if a later snapshot somehow arrives.
- **MCP servers were inherited.** This machine has `context7` (current library docs), `playwright`
  (a full browser, so any URL including the PR page) and `erinra` (a memory store, i.e. a cross-cell
  contamination path) connected. Verified by invocation, not by asking: without the flag the tool
  exists and is stopped only by a *permission* prompt — so a permissive `PERM_FLAGS` would have let
  it through — and with the flag the tool does not exist at all.

The last two rows are stated rather than implied. Cells need network, so a language HTTP client
cannot be denied without also breaking restore; neither is a plausible route to *this* PR's review
threads, but neither is measured, and a leak audit that silently omitted them would be claiming more
coverage than it has.

### On the LLM-approval idea

An in-loop LLM gate — a sidecar that fetches, judges whether content reveals post-checkpoint
information, and returns content or a refusal — is implementable but poorly suited as the *primary*
control. It adds latency and cost to every call, and an LLM asked "is this page dated after T" is
unreliable because most pages carry no usable date. Mechanical date-bounding (Wayback pinning, `gh`
`createdAt` filtering, git ancestry) is deterministic and auditable where it applies.

The LLM's place is Tier 3, where it is cheap, blocks nothing, and is reviewing *evidence of what
happened* rather than guessing at page provenance.

---

## 6. What v2 still cannot fix

**Training-data memorization.** Unaffected by any of the above — it is a calendar problem. Vintage
*bounds* it; nothing available to us removes it. You can prove a tool did not call `gh`; you cannot
prove it did not recall. Policy decided 2026-08-10 (`dcc-f2nf`):

**Vintage is a property of a (subject, model) pair — never of a subject alone.** A subject is
in-window for a model if it merged before that model's training cutoff. Store the subject's merge
date in the fixture and compute the status at analysis time; a boolean "vintage-safe" flag baked into
a fixture is wrong the day a model ships. Current state of the surviving corpus:

| Model | Cutoff | Subjects out-of-window (usable) |
|---|---|---|
| Haiku 4.5 — `anthropic-code-review` helpers | 2025-07 | 2, 8, 9, 10, 12 |
| Sonnet 5 — `anthropic-code-review` review agents | 2026-01 | 2, 12 |
| **Opus 5 — `BENCH_MODEL` and the judge** | 2026-05 | 2 |

⚠️ **The perverse consequence: weaker models have older cutoffs, so more of the corpus is clean for
them.** Haiku 4.5 gets five usable subjects where Opus 4.8 gets two. Any comparison that pools across
models — and `anthropic-code-review` pins Sonnet and Haiku regardless of `BENCH_MODEL` — is
confounded by this, in the direction of *flattering the weaker model*. Per-cell results must carry
both the reviewer's cutoff and the subject's merge date, and a headline number must never pool
in-window and out-of-window cells without showing the split.

**New subjects must be out-of-window for the newest roster model *and* the judge** — currently
merged after 2026-05, since `BENCH_MODEL` is Opus 5 and the judge is Opus 5. Verified 2026-08-10 that
this costs nothing: ~19,000 review-approved PRs merged after that date across the candidate repos
alone. Hard admission rule for `dcc-ixyy`.

⚠️ **The anchor cannot satisfy this rule, and that is structural.** An anchor subject needs a revert
whose mechanism was named, and defects take time to surface and be root-caused — so anchor subjects
will always sit inside the roster's training window. Read the anchor accordingly: it answers "did
every tool miss this defect class", and a *negative* there (everyone missed it) stays informative
under memorization, while a positive (everyone caught it) is weak evidence because recall may explain
it. This asymmetry is a reason the anchor never ranks.

⚠️ **`BENCH_MODEL` and the judge are now the same model.** That maximizes shared-blind-spot risk:
findings an Opus 5 reviewer believes are likely to be validated by an Opus 5 judge. It is still the
right call — a weaker judge misgrades, which is worse — but it makes the **human review threads
load-bearing**, because they are the only scoring signal in the design not produced by an Opus 5.
Weight the thread axis accordingly when reading results, and keep the hand spot-check of the
`valid-other`/`nitpick` boundary.

**Pre-cutoff subjects are retained as a probe, not deleted.** Memorization is unfalsifiable in the
abstract but its *effect size* is measurable: build **matched vintage pairs** — same repo, same size
bucket, same application type, one either side of the cutoff — and the performance difference between
them is attributable to vintage rather than difficulty. Unmatched pre/post comparisons across
different subjects confound vintage with difficulty and should not be read as evidence either way.
Until such pairs exist, treat memorization as disclosed, not measured.

**Retirement is a change of role, not a deletion.** When a model release moves a cutoff past a
subject's merge date, that subject stops being scored for that model and becomes probe material.
Graceful degradation; the corpus does not fall off a cliff on release day.

**The judge is also contaminated, and currently worst of all** — Opus 5's May-2026 cutoff leaves
exactly one of seven subjects out of window. Blind grading hides which *tool* produced a cluster; it
does nothing about the judge knowing the answer. Under pooled adjudication this biases toward rating
the *famous* defect valid while judging equally-valid unfamous findings more harshly, which inflates
whichever tool happened to name it. Mitigations already decided: a code citation is required for
every verdict, and adversarial re-judging applies. Disclose the judge's cutoff alongside results.

**Fast-confirmation bias.** If subject selection requires a confirmed follow-up fix, the corpus skews
toward defects with obvious symptoms (crashes, leaks, regressions). Subtle design problems confirm
too slowly to harvest. The retrospective key partially offsets this: a PR needs review threads, not a
confirmed follow-up fix, to be usable — so well-reviewed PRs that never broke are still valid
subjects, and their keys carry no fast-confirmation bias at all.

---

## 7. Open questions

- Key-building is the cost centre and is not scriptable. How many hours per checkpoint is
  acceptable, and does an LLM-assisted first pass (human-adjudicated) bring it down enough?
- The key mixes nits, style, and real defects. Do those get scored separately, weighted, or filtered
  at admission time?
- Checkpoint-walking cost: locating the introducing push is cheap per subject, but does it need to be
  automated (defect-signature matching across heads) or is it fine as a manual step during curation?
- Force-push count as a selection criterion — what is the cutoff, and how many otherwise-good
  subjects does it exclude?
- Wayback coverage for the documentation domains that actually matter per language.
