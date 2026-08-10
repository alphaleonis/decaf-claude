# Subject 7 — prometheus/prometheus #13777 (go/small): findings-quality analysis

**The subject.** A single-file, 32+/21− refactor of `storage/remote/read_handler.go`: querier
creation, hints building, and `querier.Select(...)` move out of the chunked remote-read loop into a
new helper, `getChunkSeriesSet`, which holds `defer querier.Close()` and returns the result of
`Select`. The defect is a textbook Go lifetime error: `Select` returns a **lazy** `ChunkSeriesSet`,
so the deferred `Close()` fires when the *helper* returns — before `StreamChunkedReadResponses` ever
iterates it. The consumer then reads chunk bytes through a closed querier whose memory-mapped files
may already be unmapped. Production result: `fatal error: fault` / SIGSEGV inside
`chunks.(*Reader).ChunkOrIterable`, reproducibly right after a block write (issue #14422); fully
reverted four months later (#14515, whose author names the mechanism exactly: *"the iterators for the
querier can access memory-mapped files, which are closed when the querier is closed"*).

The camouflage is notable: the helper's own doc comment asserts the opposite of the truth
("...to ensure timely release of the querier resources"), the PR title frames it as a deliberate OOM
improvement, and it passed human review with **zero inline comments**.

**Every tool caught it, in every repeat — 10/10 cells, with the correct mechanism.** This is the
cleanest recall result in the benchmark, and unlike subject 1's sweep it is a meaningful one: the bug
is diff-visible but genuinely requires reasoning (Go `defer` semantics + laziness of `Select` +
ownership of mmap-backed data), and no retrieval is needed. Several tools went well past the bar,
tracing `querier.Close()` → `blockBaseQuerier.Close` → `chunks.Close()` → `pendingReaders.Done()`
and naming the concurrent-compaction race (`Block.Close`/`reloadBlocks` unmapping segments
mid-stream) that converts the latent bug into a crash. Multiple tools independently reached the same
conclusion the Prometheus maintainers did in the revert. On a bug that a human review missed
entirely, all five tools succeeded — the strongest evidence in this benchmark that these tools read
code rather than merely pattern-match or retrieve.

**Zero false positives across the entire subject.** All three `known_safe` traps held. Nobody claimed
the querier *leaks* (the inverse error — the `defer` moved, it wasn't deleted); nobody claimed the
`ChunkQuerier` construction error is swallowed (it round-trips via `storage.ErrChunkSeriesSet` and is
checked by `chunks.Err()`); nobody claimed the verbatim-moved hints mapping or `sortSeries=true`
changed semantics. Across 174 findings and five tools, not one refuted claim — the best FP discipline
of any subject so far.

**A genuinely additive second defect, found by three tools.** `ours` (both reps), pr-review-toolkit,
and tag1 surfaced the **head-path variant** (c2, valid-other): the same premature `Close()` also
releases the read's `isolationState`, unregistering it from `Head.iso.readsOpen` so a concurrent head
truncation can advance past a still-iterating read. The judge confirmed this is not the primary
reworded — the consequence differs (snapshot-isolation breakage, not use-after-free) and so does the
fix surface, since the revert's proposed ref-counting of the chunk reader would *not* restore
isolation. Notably, `ours`' own validator **corrected the claim downward** mid-run: head chunks are
copied under `readPathMtx`, so the outcome is isolation breakage rather than a memory fault. That is
a validator doing its job — reducing an overstated severity instead of amplifying it.

**The contract-vocabulary catch.** A second cluster (c5) also graded TP-primary: four cells
(`ours` r2, pr-review-toolkit ×2, tag1 r1) framed the defect as an *undocumented storage-interface
contract* — the code requires a `ChunkSeriesSet` to stay valid after its `ChunkQuerier` is closed,
`storage/interface.go` states no such rule, the nearest precedent (`LabelValues`) documents the
opposite, and the first-party TSDB block querier does not uphold it. That is the primary stated in
design language with the violation asserted, and it points at the durable fix (write the lifetime
rule into the interface docs) rather than just the local patch.

**Noise profile and the suggestion tier.** With recall saturated, the separation is again in what
else got said. anthropic was the most economical: ~4 findings per cell, **zero trivia**, precision
0.42 at $4.85 — it found the bug, noted the missing test, and stopped. superpowers matched it for
discipline (zero trivia, $1.94/cell) with a slightly thinner valid set. pr-review-toolkit ran widest
(5.0 valid-minor and 3.5 trivia per cell, precision 0.27), and its volume was not empty: it produced
the concrete missing-error-path test list (c20), the orphaned sorted-comment drift (c13), the
duplicated hints mapping (c6), and the sole unique-true finding (c18). tag1 sat between, adding an
observability/metrics wish-list that graded trivia. `ours` was mid-pack on noise (2.0 trivia) with the
strongest deep-mechanism writing, but at $15.82/cell — 8× superpowers for the same headline catch.

**Cost–quality verdict.** Every tool caught the escaped bug, so cost-per-bug is just cost:
superpowers $1.94, anthropic $4.85, pr-review-toolkit $7.15, tag1 $10.85, `ours` $15.82. On this
subject the frontier is unambiguously **superpowers and anthropic** — cheapest and cleanest, with
anthropic's zero-trivia profile making it the best "read the top of the list and act" tool. The
premium tools bought marginal extras: pr-review-toolkit's unique c18 and its bounded error-path test
list, tag1 nothing distinctive, `ours` the richest mechanism narratives and validator self-correction
but no unique finding. Subagent distinctness stayed low across all fan-outs (0.20–0.26), i.e. ~75–80%
of subagent findings restate a sibling's cluster.

**Caveats.** (1) `human_issues` is empty — the PR had zero inline review comments — so the grade rests
entirely on primary recall, FP discipline, and valid-other yield; there is no human-issue axis here.
(2) **One grader verdict was human-overridden**: c18 ("the helper makes it structurally impossible for
the caller to keep the producer alive during consumption") was graded TP-primary, but the judge had
denied c3 that status for omitting the use-after-close consequence while acknowledging c18 omits the
same thing. Applying the bar consistently, c18 was regraded valid-other; this does **not** change any
tool's bug-catch rate, since its sole reporter already catches c1 in both reps. (3) c5's TP-primary is
a judgment call — it is the primary in contract vocabulary rather than a separate defect; it is
retained because it asserts the invariant is violated by the real implementation, but a stricter
reading would fold it into c1. (4) Lowest-confidence cluster is c9 at 58 (chunk-vs-samples path
asymmetry — a correct observation whose remedy, "document why", treats the bug as a design choice).
(5) Because recall saturated at 10/10, this subject discriminates only on precision and cost — it is
the counterweight to subject 4, where the same tools mostly failed on a downstream-only bug.
