You are a blind classifier for a code-review benchmark. Assign each finding-cluster a `finding_class` from a CLOSED set, judging ONLY what kind of thing the finding is about — NOT whether it is correct, real, or important. You do not know which tool produced any cluster and must not try to infer it.

Read: <scratch>/prom-sp2-grade-clusters.json — each {cluster_id, summary, location}. Context if you need it: the change is prometheus/prometheus PR "promql: Add metric to track total samples read per query"; the diff is at <scratch>/prom-diff.patch (read-only).

The closed set and its definitions:
- `defect` — a claim that the code behaves incorrectly (wrong value, wrong rows, crash, regression, data loss, security hole), OR a check of whether such a behavior exists (a "considered whether X could crash — it cannot" note is still about a defect, class-wise).
- `risk` — a claim about a hazard that is not currently wrong behavior: fragility, unbounded resource growth, performance cost, missing guard for a future path.
- `test-gap` — missing, weak, tautological, or snapshot-recorded tests; test coverage or test-quality claims.
- `docs` — documentation, comments, rationale, doc/code mismatch, TODO comments, naming that hides intent.
- `design` — API/contract shape, abstraction boundaries, provider seams, structure, extensibility.
- `style` — formatting, consistency of idiom, link/anchor style, cosmetic.

Return your final message as exactly one JSON array — one object per cluster, all of them — no prose, no code fence:
[{"cluster_id":"", "finding_class":"defect|risk|test-gap|docs|design|style", "class_confidence": <0..1>}]