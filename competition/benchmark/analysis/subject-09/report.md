# Subject 9 — kubernetes/kubernetes#130837 (go / large)

*Re-graded 2026-08-10 after the cross-cell contamination fix (nib `dcc-2cxq`). Every cell in this
analysis ran against a pristine checkout; the earlier grading of this subject is void and sits in
`quarantine/2026-08-06-decaf-leak/`.*

The PR replaces kube-proxy's `NodePodCIDRHandler` with a new `NodeManager` — 18 files, +757/-803.
It was merged, then reverted (#132958) and re-landed as a take-2 (#133059) that restored backward
compatibility. The escaped defect: `NewNodeManager` makes NodeIP acquisition a hard, fatal
prerequisite, so kube-proxy aborts startup on nodes whose IPs are assigned late by an external
cloud provider, where the deleted `getNodeIPs` path was non-fatal and fell back to localhost.

800 findings from 15 cells collapsed into 98 clusters. One cluster matched the primary bug, two
matched human review issues, 31 were other real defects, 6 were false positives, and 58 were
nitpicks. The nitpick share — nearly 60% of everything reported — is the dominant fact about
reviewing a diff this size.

## Did anyone catch the escaped bug?

Yes, and by a wide margin more tools than the difficulty of the bug would suggest. Nine of the
fifteen cells landed on cluster `c11`, which states the regression in the terms the answer key
demands: the poll returns an error, `newProxyServer` propagates it, and startup aborts where the
old code degraded gracefully.

`anthropic-code-review`, `ours-review`, and `ours-audit` caught it in **both** repeats. `ours`
caught it in its single surviving repeat. `superpowers` and `tag1-comprehensive-review` caught it
in one repeat of two — a coin-flip that matters more than the average, because a reviewer you can
only trust half the time is a reviewer you have to double-check.

Two tools never found it. `pr-review-toolkit` missed it in both repeats despite producing the
largest volume of any tool (17.5 valid findings per cell, 39 clusters touched in r1 alone) — it
searched broadly and still walked past the one defect that forced a revert. `ours-bugs` also
missed it in both repeats, which is the most pointed result in this subject: it is the preset
whose entire purpose is hunting bugs.

That `ours-bugs` result deserves care rather than a verdict. Under the contaminated harness this
same cell *did* report the finding — and its own report admitted the finding "was **missed by the
`bugs`/`models=low` wave** and recovered via the recurring-findings cross-check," i.e. lifted from
a prior tool's report file left in the checkout. Removing that channel removed the catch. The
honest reading is that `ours-bugs`'s apparent catch on this subject was always borrowed, and the
clean run simply shows what the preset finds on its own. One subject, two repeats — a hypothesis
worth testing on subjects 1 and 5, not a settled property.

The near-miss is instructive. Cluster `c27` correctly identifies that the new hardcoded 5-minute
poll replaced a ~63s bounded backoff — the right code, the right hunk, the wrong conclusion. It
complains the timeout is too long without ever saying that failure became fatal. The reviewer who
foreshadowed this bug on the real PR (danwinship: "this loses the timeout that the previous
version had") made the same near-miss, which is presumably why it shipped.

## Human issues

Both were found, each by exactly one tool, and neither by the tools that caught the primary bug in
both repeats.

`h1` — the exit sites use unbounded `klog.Flush()` instead of the codebase-wide bounded
`klog.FlushAndExit`, so a stalled log sink can swallow the crash reason (cluster `c46`). Found by
`ours` r1, `ours-review` r1, and both `ours-audit` repeats. This is the issue a human reported
post-merge as breaking cluster creation, so it has real-world confirmation.

`h2` — `NodeIPs()` discards the `GetNodeHostIPs` error and returns nil while the caller logs
"Successfully retrieved NodeIPs" unconditionally (cluster `c37`). Found **only** by
`pr-review-toolkit` r2 — the tool that missed the primary bug entirely. Volume bought it the one
finding nobody else got.

## False positives and the shape of the noise

Six clusters were false positives, but they are not evenly distributed and one dominates.

Cluster `c7` — "`NodeEligible()` dereferences `hs.nodeManager` with no nil guard, so a nil
NodeManager panics" — was reported by **ten of the fifteen cells**, spanning seven of the eight
tools. It is in the answer key's `known_safe` list: the `if s.NodeManager != nil` guard in `Run()`
and the hollow-proxy's absent NodeManager are deliberate special-casing, and the normal path
cannot reach the deref. This is the benchmark's clearest case of a plausible-looking pattern that
survives independent rediscovery — seven tools reached the same wrong conclusion, so cross-tool
agreement is worthless as a correctness signal here. Notably `ours-review` and `ours-audit` r1
avoided it; `ours-bugs` reported it in both repeats.

Cluster `c47` — flagging the intentional crash-on-NodeIP-change as a defect — is the second
`known_safe` trap, caught by `anthropic-code-review` r2, both `ours-audit` repeats, `superpowers`
r2, and both `tag1` repeats. The type's own doc comment says it crashes on change by design.

Per-cell false-positive rates put `ours-audit` (2.0) and `tag1` (3.5) at the top and
`ours-review` at the bottom (0.5). `ours-audit`'s extra FPs are its own: `c50`, a speculative
"self-termination across a trust boundary with no debounce or rate limit" framing, was reported by
both its repeats and nobody else.

## Did the fan-out earn its agents?

Subagent distinctness — the share of subagent reports that aren't another sibling re-finding the
same cluster — separates the tools sharply.

`pr-review-toolkit` is the most efficient fan-out at 0.82 across only 5 subagents, and
`ours-review` and `ours-audit` both hit 0.77. But they get there differently: `ours-review` runs
14 subagents and `ours-audit` 17.5, against `pr-review-toolkit`'s 5. High distinctness on a large
roster means the personas genuinely cover different ground; the cost is that you pay for all of
them.

`anthropic-code-review` is the weakest at 0.45 across 15 subagents — more than half its subagent
reports are duplicates of a sibling's finding. It still catches the primary bug in both repeats at
$10.19/cell, so the redundancy is not fatal, but it is the clearest case of a roster not paying
for itself.

`ours` (the retired combined preset) sits at 0.58 with 20 subagents and $34.88/cell — the most
expensive cell in the subject by 56%, for a catch rate matched by `ours-review` at $20.43 and
`anthropic-code-review` at $10.19. `ours-bugs` at 4.5 subagents and $5.48 is the cheapest decaf
configuration and, on this subject, the one that missed the bug.

`superpowers` runs a single reviewer, so distinctness is undefined; at $3.21/cell it is the
cheapest tool in the benchmark and still caught the bug once in two tries.

## Cost versus catch

Ranked by what it costs to actually catch the escaped bug: `superpowers` $6.43,
`anthropic-code-review` $10.19, `ours-review` $20.43, `ours-audit` $22.30, `ours` $34.88,
`tag1` $42.36. `ours-bugs` and `pr-review-toolkit` never caught it, so no figure exists.

`anthropic-code-review` is the standout on this subject: both repeats caught the bug, precision
0.58, only 4.0 valid findings and 2.5 nitpicks per cell, at half the cost of the decaf presets. It
found nothing unique, but it found the thing that mattered, twice, cheaply, and buried it in very
little noise.

Among the decaf presets, `ours-review` is the clear pick here: the only one with both repeats
catching the bug at the highest precision of the three (0.62), the lowest FP rate of any tool
(0.5/cell), and $2 cheaper per cell than `ours-audit`. `ours-audit` buys 2 unique true findings and
3 more valid findings per cell for more false positives and more nitpicks — worth it for an audit,
hard to justify for routine review.

## Caveats

**`ours` has one repeat, not two.** Its r2 cell was contaminated and could not be re-run — the tool
was retired from `tools.json` (nib `dcc-gxuk`) before the contamination was found. Every `ours`
figure here rests on a single observation and carries no variance estimate. It should not be
compared to the two-repeat tools on reliability at all.

**One subject, two repeats.** Every "caught it in both repeats" claim rests on two samples. The
1/2 results for `superpowers` and `tag1` are indistinguishable from luck at this sample size, and
so, in the other direction, are the 2/2 results.

**Three low-confidence verdicts.** Clusters `c24`, `c33`, and `c54` were graded at confidence
52–58, and `c34` at 55 — the judge could not fully verify them against the diff, generally because
the cited code sits outside the changed hunks. These need human eyes.

**The human-issue sample is thin.** Only two human issues exist for this PR, each found by one
tool, so `TP-human` counts are near-anecdotal and should not drive any ranking.

**Nitpick classification is a judgment call.** 58 of 98 clusters were graded nitpick, and the
boundary between "trivial doc nit" and "genuine maintainability issue" is where a different judge
would most plausibly disagree. The valid/nitpick split per tool is softer than the primary-bug
result, which is objective.
