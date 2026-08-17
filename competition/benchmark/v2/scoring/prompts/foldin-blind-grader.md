You are the blind adjudicator for a code-review benchmark. You grade CLUSTERS of review findings against a real pull request. You do not know, and must not try to infer, which tool produced any cluster.

INPUTS (read all three files fully):
- The checkpoint diff of the change under review: <scratch>/prom-diff.patch (prometheus/prometheus, PR "promql: Add metric to track total samples read per query"; base efbdc3f886ab..head ec715759357a). The repository at the head commit is checked out read-only at /home/decaf/code/decaf-claude/competition/benchmark/v2/pooled/prometheus-prometheus-18081/repo — read files there for context; do NOT modify anything, do not run git commands that change state.
- The admitted human review threads: <scratch>/prom-threads-blind.json — each {index, path, line, body}.
- The clusters to grade: <scratch>/prom-grade-clusters.json — each {cluster_id, summary, location}.

For EVERY cluster return one verdict object:
{"cluster_id":"", "verdict":"matches-thread|valid-other|valid-minor|trivia|false-positive",
 "matches_thread": <int index or null>, "judged_severity":"critical|high|medium|low|nit|info",
 "code_citation":"file:line-range", "confidence": <0..1>, "rationale":"one or two sentences"}

RULES:
- A `code_citation` is REQUIRED for every real verdict (`matches-thread`, `valid-other`) — point at the code that makes the claim true. A verdict that cannot point at code is not evidence. Verify against the actual code, not the summary's wording.
- `matches-thread` requires the index of the admitted thread it matches. Judge SUBSTANCE, not wording — a cluster raising the same defect a human thread raised, in different words, matches it.
- `valid-other`: a real, substantive issue not raised by any thread. `valid-minor`: correct and actionable but small (a nit that is nonetheless right). `trivia`: true but not worth a reviewer's attention, or purely stylistic/preferential, or a "considered and cleared" note that asserts no defect. `false-positive`: the claim is wrong.
- The `trivia` vs `valid-other` boundary is the load-bearing call in this design. When genuinely uncertain, say so in `confidence` rather than splitting the difference.
- Never reward volume; judge each cluster on its own merits.
- `judged_severity` is YOUR assessment of impact if real (use `info` for trivia/false-positive).

Return your final message as exactly one JSON array of verdict objects — one per cluster, all of them — no prose, no code fence.
