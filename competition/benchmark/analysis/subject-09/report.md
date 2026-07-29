# Subject 9 — findings-quality analysis

**kubernetes/kubernetes#130837** (go / large) — an 18-file, ~1,560-line kube-proxy refactor ("node
manager") whose escaped bug was that NodeIP acquisition at startup became **fatal**: the new
`NodeManager` blocks up to 5 minutes for the node to have NodeIPs and, on timeout, returns an error
that aborts kube-proxy startup — removing the previous **non-fatal** ~30–63s backoff plus
localhost/BindAddress fallback. Reverted after breaking out-of-tree cloud providers. Judge:
`claude-opus-5[1m]`, blind. 56 clusters graded: **2 TP-primary, 2 TP-human, 7 valid-other,
28 valid-minor, 2 false-positive, 15 trivia.**

**This is a re-analysis.** The two `anthropic-code-review` cells were re-run on 2026-07-29 with a
plugin-qualified invocation. The cells previously recorded under that label had executed
`decaf-quality` (ours) at `high` mode — see nib dcc-9kkz. The eight non-anthropic cells are
unchanged (17 Jul) and their extraction was reused verbatim; only the anthropic findings were
re-extracted, and all 56 clusters were re-graded blind.

## The subject that finally separates everything

This is the first subject in the study where recall splits four ways:

- **`ours` and `anthropic` caught it in both repeats** (1.00)
- **`superpowers` and `tag1` caught it in one of two** (0.50)
- **`pr-review-toolkit` missed it in both** (0.00) — despite emitting 183 findings and touching 40
  of 56 clusters, more than anyone

That last result is the sharpest illustration in the benchmark of volume not being coverage.
`pr-review-toolkit` produced 17.5 valid-minor and 10.0 trivia per cell and still never asserted
that a startup path had become fatal.

## Three tools, three different unique catches

Unusually, this subject has **three** unique-true clusters, one each:

- **`ours` uniquely caught `c5` — a TP-human.** All three exit sites now use `klog.Flush()` +
  `exitFunc(1)` where the replaced handler used `klog.FlushAndExit(klog.ExitFlushTimeout, 1)`,
  risking the loss of the very log line explaining why kube-proxy died. That is a real human-review
  issue nobody else found, and it is the strongest single result for ours in the repaired set.
- **`anthropic` uniquely caught `c60`** — the deleted `waitForPodCIDR` condition contained a
  `DeletionTimestamp` check; the replacement poll does not, so a terminating node now satisfies the
  wait and its stale PodCIDRs are used. Its `git-history` and `prior-pr` agents both traced this to
  the specific commit that had added the guard.
- **`tag1` uniquely caught `c59`** — the deleted `getNodeIPs` logged on every attempt while the
  replacement poll returns silently, so a multi-minute startup block now emits nothing between
  cache sync and the final error.

The second TP-human (`c35`, the unconditional "Successfully retrieved NodeIPs" log) was found by
several tools.

## Noise character

`ours` emitted **248 findings** across 37 clusters — the most in the study — at precision 0.23,
8.5 trivia/cell, and **2 false positives per cell**, both on `known_safe` traps: it asserted the
exit-on-NodeIP-change behavior is a defect (`c2`, `c3`) when the `NodeManager` type doc explicitly
states it "crashes kube-proxy if there are any changes in NodeIPs or PodCIDRs". That is the
documented contract, and ours argued against it twice.

`anthropic` is again the cleanest: **48 findings, 11 clusters, precision 0.46, 0.5 trivia/cell** —
a seventeenth of `pr-review-toolkit`'s trivia rate on the same diff.

`tag1` also took 2 FP/cell and, like `pr-review-toolkit`, spent most of its output on valid-minor
(14.5/cell).

## Did the fan-out earn its agents?

Partly, and for the first time. Ours ran **19 agents** — its largest roster anywhere — and that
breadth is plausibly what surfaced `c5`, a subtle logging-flush regression buried in an 18-file
diff. Distinctness remains low at 0.23, so most of that breadth was still restatement.

But `anthropic` reached the same primary catch plus its own unique `c60` with 15 agents and a fifth
of the findings, and `pr-review-toolkit`'s 5 agents produced the most clusters and zero catches. On
this subject roster size did not predict recall; brief quality did.

## Cost versus catch

superpowers **$3.21** (half a catch), pr-review-toolkit **$9.97** (no catch), anthropic **$10.19**,
tag1 **$21.18** (half a catch), ours **$32.10**.

Ours is **3.1× anthropic** for the same recall — but this is the one subject where the premium
bought something identifiable: a unique TP-human nobody else saw. Whether one human-review issue
justifies $22 more per run is the product question, not a measurement one.

Ours' $32.10 is the single most expensive cell in the benchmark. Anthropic's $10.19 on a 1,560-line
diff against $5.81 on a 33-line diff confirms its shallow cost curve: a 47× diff-size range moves
it only 1.8×.

## Caveats

- **`pr-review-toolkit` scoring 0.00 rests on two cells.** It is a real miss in both, but n=2.
- **`c19` is a borderline TP-primary at confidence 55** — the grader credited a stale-comment
  framing because it states the load-bearing fact (the 5-minute timeout now fatally bounds startup
  in all modes). A stricter reading would call it a comment nit and drop ours' or whoever's credit
  accordingly. This is the single most consequential judgment call in the subject.
- **Anthropic emits confidence scores, not severities**, so its consolidated report tagged nothing
  here critical/high and calibration is undefined for it on this subject — the earlier 1.00 came
  from a sub-agent's private label, which the metric no longer counts (#dcc-hmp6).
- **The eight non-anthropic cells reuse the 17 Jul extraction.**
- **Cluster count moved 56 → 56** (two dissolved, two added) with a changed verdict vocabulary, so
  headline counts are not comparable to the previous version.
- Twelve clusters were graded at confidence ≤ 60; those plus all four TP verdicts want a human
  eyeball.
