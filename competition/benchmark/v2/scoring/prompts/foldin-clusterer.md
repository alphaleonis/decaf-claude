You are the clustering stage of a code-review benchmark. Read the JSON file __INPUT__. It has:
- `existing_clusters`: already-formed clusters, each `{cluster_id, summary, location}` — one cluster = one underlying issue (same file, ~same line, same claim).
- `new_findings`: new findings from a newly added tool, each `{nid, file, line, severity, claim}`.

TASK: assign every new finding either to the existing cluster asserting the SAME underlying issue, or to a NEW cluster. Rules:
- "Same underlying issue" = the same defect/observation at the same place, even when described in different words or with different measurements. Different symptoms of one root cause = same cluster. This is the engine that makes cross-tool comparison possible — a real match must not be missed, but do NOT force a merge between issues that are merely nearby or thematically similar (a different claim about the same line is a different cluster). Many findings cite the same file; discriminate on the CLAIM.
- A finding that examines an issue and CLEARS it ("traced, unreachable", "not a defect") asserts the same underlying issue as a finding that flags it — cluster them together; the benchmark records the disposition separately.
- Two new findings that assert the same issue as each other (e.g. from repeat 1 and repeat 2) but match no existing cluster go into the SAME new cluster.
- Location match is evidence but not sufficient; claim match is what decides. Do a full pass over all existing clusters for each new finding.
- Every nid must appear exactly once in the output.

For each NEW cluster you create, write a `summary` in the same style as the existing ones (one sentence, specific, mechanism + consequence, no tool names) and a `location` (`file:line`). New cluster IDs continue the existing sequence: __NEWIDS__.

OUTPUT: your final message must be exactly one JSON object, no prose, no code fence:
{"assignments": [{"nid": "n1-00", "cluster_id": "c01", "confidence": 0.9, "why": "one short phrase"}, ...],
 "new_clusters": [{"cluster_id": "...", "summary": "...", "location": "file:line", "members": ["n1-03","n2-02"]}, ...]}
`confidence` is your certainty (0–1); for merges into existing clusters below 0.7, say in `why` what made you unsure.
