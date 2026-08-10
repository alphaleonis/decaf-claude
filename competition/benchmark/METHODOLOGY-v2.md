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

Verified on subject 9 (`kubernetes/kubernetes#130837`, opened 2025-03-15, force-pushed 113×): the
as-opened head `be7da1315a3c` — force-pushed away the same day, 15 months ago — fetches cleanly, and
diffs against merge-base `18e5a4d585f6` to 11 files, +342/−426 (vs 18 files, +757/−803 as merged).

### Choosing the checkpoint

Prefer PRs where review happened against a **stable head** (0–3 force-pushes) — then the checkpoint
is simply the as-opened head and every thread attaches to it. For heavily-rewritten PRs, pick the
head with the largest cluster of substantive threads written against it.

Subject 9 is the pathological case and is instructive: with 113 force-pushes over four months,
threads target whichever version existed when written. The first thread landed three hours after the
first force-push, and several name files (`pkg/proxy/topology.go`, `pkg/proxy/kubemark/hollow_proxy.go`)
absent from the as-opened diff entirely. **A low force-push count should be a subject-selection
criterion, not an afterthought.**

---

## 3. What v2 measures: one retrospective key

One review run per checkpoint, scored against **one retrospectively-built key**.

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

Mechanical pre-filters narrow the candidate set before human judgment is needed:

- does the thread's file exist in the checkpoint diff?
- does its line range fall inside the checkpoint's changed hunks?
- does `git blame` on the fix's deleted lines trace to a commit reachable from the checkpoint head?

On subject 9 these filters alone drop the `pkg/proxy/topology.go` and
`pkg/proxy/kubemark/hollow_proxy.go` threads, and the entire `NewNodeManager`-error-path family. What
survives is a shortlist to adjudicate, not 46 threads plus a fix PR read from scratch.

**The residual judgment is irreducible and must be done by hand** (human, or human-supervised LLM).
Deciding whether a June comment describes a March defect requires reading the code at both points.
This is the expensive artifact of the whole design — and it is one-time per checkpoint, reused across
every tool, repeat, and future run, so it amortizes well.

It is safe to build with total access to the fix PR, the threads, and the post-merge issues,
**because the reviewer never sees it.** Only the judge does.

### Corollary: earlier checkpoints yield richer keys

At T = merged head, only post-merge discoveries can apply. At T = as-opened, the entire lifecycle's
learnings are candidates. **The earliest checkpoint is therefore the most valuable**, not the most
awkward — it maximizes how much of what the world learned is admissible.

### Worked check: subject 9

Applying the admission rule to subject 9's as-opened checkpoint excludes both the primary escaped bug
and human-issue h1:

| | As opened (2025-03-15) | As merged (2025-07-11) |
|---|---|---|
| `NewNodeManager` | returns `*NodeManager` — no error path | returns an error — the fatal path |
| Exit pattern | 2× `klog.FlushAndExit` (correct) | 3× plain `klog.Flush()` (the h1 defect) |
| `node.go` | 92 lines | 190 lines |

Both the primary escaped bug **and** human-issue h1 were introduced *during* review. Four months and
113 force-pushes made the PR worse in exactly the two places that later broke production.

The consequence: at the as-opened checkpoint, subject 9's key contains **neither** of the defects it
is famous for. Its key would consist only of the review findings that applied to the original
92-line `node.go`. Scoring the escaped bug requires a *later* checkpoint — one after the error path
was introduced — which is a second review run of the same subject.

This is not a flaw in the method; it is the method reporting honestly that the escaped bug did not
exist yet. But it makes subject 9 a poor routine subject: 113 force-pushes, a four-month lifecycle,
and a headline defect absent at open. It is a good stress test and a bad default.

**Subject selection should prefer PRs with few force-pushes and a defect present from the first
push** — verifiable mechanically via the presence check before any key-building effort is spent.

---

## 4. How review agents run: time-boxing, not blanket denial

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

### Tier 3 — audit, not only prevention

Prevention is necessary but not sufficient — a shim gap is silent. Every run therefore produces an
access log, and a post-run auditor checks both the log and the findings text for post-checkpoint
references (fix/revert PR numbers, reviewer usernames, dated language). **Cells that trip the auditor
are quarantined, not silently scored.**

Run the auditor on the first 2–3 cells before authorizing a full run.

### On the LLM-approval idea

An in-loop LLM gate — a sidecar that fetches, judges whether content reveals post-checkpoint
information, and returns content or a refusal — is implementable but poorly suited as the *primary*
control. It adds latency and cost to every call, and an LLM asked "is this page dated after T" is
unreliable because most pages carry no usable date. Mechanical date-bounding (Wayback pinning, `gh`
`createdAt` filtering, git ancestry) is deterministic and auditable where it applies.

The LLM's place is Tier 3, where it is cheap, blocks nothing, and is reviewing *evidence of what
happened* rather than guessing at page provenance.

---

## 5. What v2 still cannot fix

**Training-data memorization.** Unaffected by any of the above — it is a calendar problem. Only
subject vintage bounds it: prefer PRs merged after the roster's newest training cutoff, and retire
subjects as cutoffs advance. See the cutoff and vintage tables in nib `dcc-ho2w`. Six of ten current
dated subjects are already inside the benchmark model's training window.

**The judge is also contaminated.** Blind grading hides which *tool* produced a cluster; it does
nothing about the judge already knowing the answer.

**Fast-confirmation bias.** If subject selection requires a confirmed follow-up fix, the corpus skews
toward defects with obvious symptoms (crashes, leaks, regressions). Subtle design problems confirm
too slowly to harvest. Track 1 partially offsets this, since it needs no fix at all.

---

## 6. Open questions

- Key-building is the cost centre and is not scriptable. How many hours per checkpoint is
  acceptable, and does an LLM-assisted first pass (human-adjudicated) bring it down enough?
- The key mixes nits, style, and real defects. Do those get scored separately, weighted, or filtered
  at admission time?
- Where a subject's defect postdates its earliest checkpoint (subject 9), is the second review run
  worth its cost, or should such subjects simply be excluded at selection?
- Force-push count as a selection criterion — what is the cutoff, and how many otherwise-good
  subjects does it exclude?
- Wayback coverage for the documentation domains that actually matter per language.
