Only this review exists — no recurring-findings section needed.

✅ Review complete: `.decaf/code-reviews/CODE_REVIEW_2026-08-10_09-56-59.md`

**Findings by severity: 0 Critical · 1 High · 0 Medium · 0 Low · 1 Minor — Verdict: ❌ NEEDS_CHANGES**

The one High-confidence bug (validated `confirmed`): `NodeTopologyConfig` attaches its handler to the **already-started** node informer that `NewNodeManager` starts and syncs in `newProxyServer`, then registers the proxier afterward — with no mutex. That yields (1) a deterministic data race on `eventHandlers` between the informer's synthetic-Add replay goroutine and `RegisterEventHandler`, and (2) a scheduling-dependent-but-permanent loss of the initial zone label (the `reflect.DeepEqual` guard suppresses re-delivery), silently disabling topology-aware routing. It's introduced by this PR, which dropped the old "register handlers, then Start the informer" ordering.

I dismissed four reviewer claims after verifying the code: the `pollErr`-vs-`err` return (intentional, comment-confirmed), the outside-lock comparison in `OnNodeChange` (operates on locals; events are delivered serially), the nil `nodeManager` guard (unreachable in current control flow), and the "goroutine leak" (real smell but the error path exits the process, so demoted to Minor).

Note: this was **review-only** — nothing was posted to PR #130837. The PR is already **MERGED**; I proceeded because you explicitly requested the review and the diff is present at the current HEAD. Also, the `bugs` preset's roster cap of 4 dropped test-reviewer, so test quality in the changed test files wasn't independently reviewed (flagged in the report).
