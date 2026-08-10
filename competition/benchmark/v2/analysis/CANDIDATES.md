# Pooled-adjudication corpus: candidate pool (nib dcc-ixyy)

Gathered 2026-08-10. Regenerate with `v2/find_candidates.sh <repo>` then
`v2/classify_candidate.sh <repo> <pr>`. Raw classified rows: `candidate-pool.tsv`.

Every candidate satisfies the hard admission rules: **merged after 2026-05** (out of window for both
`BENCH_MODEL` and the judge, per METHODOLOGY-v2 section 6), **carries real human review threads**
(now a scored target, not decoration), non-bot author, and >=20 changed lines.

Pool: 547 candidates found across 10 repos; 69 classified by application type.

## Coverage — every cell is populated

| Type | S | M | L |
|---|---|---|---|
| app-ui | 10 | 20 | 3 |
| contract-crossing | 3 | 3 | 3 |
| backend | 5 | 5 | 1 |
| library internals | 2 | 4 | 2 |

Contract-crossing — the row the corpus has never had — is thinnest but real at every size. It is also
the only row that exercises multi-specialist dispatch (`typescript-reviewer` + `dotnet-reviewer`
together), because the defect lives in the mismatch between two files in two languages.

## Proposed phase 1 (6 subjects)

Deliberately **not** all 12 cells. The full grid should not be built before `dcc-vkeh` shows that
pooled adjudication works — in particular that the judge is stable at the `valid-other`/`nitpick`
boundary. Six subjects cover all four types and all three sizes and are enough to run the pilot.

| Cell | Subject | Size | Threads | Why this one |
|---|---|---|---|---|
| contract / S | `immich-app/immich#28886` | +52/-45 | 5 | Svelte web + TS server — the operator's stack shape, smallest real contract crossing |
| library / S | `sveltejs/kit#15685` | +53/-24 | 8 | "breaking: nested server-only directories" — server-only leakage, security-adjacent and subtle |
| library / M | `dotnet/efcore#34127` | +233/-97 | 15 | "null propagation to optimize away `IS NOT NULL`" — C#, genuinely tricky logic |
| backend / M | `grafana/grafana#124181` | +177/-12 | 17 | lease auto-renewal — concurrency and lifetime, the kind of thing reviews miss |
| contract / M | `PostHog/posthog#61823` | +199/-11 | 22 | richest contract-crossing thread set available |
| app-ui / L | `element-hq/element-web#32964` | +560/-6 | 21 | pure SPA behavior, large, 21 threads |

Spread: 6 repos, 3 sizes, 4 types, and 5 languages (TS, Svelte, C#, Go, Python) — none of which was
designed for. Language falling out naturally is the intended behavior of dropping it as an axis.

Notably `immich#28886` and `sveltejs/kit#15685` are Svelte and `efcore#34127` is EF Core, so the
operator's actual stack is represented without having been targeted.

## Deferred to phase 2

The remaining six cells, after the pilot. `contract / L` candidates are strong but expensive —
`PostHog#55149` carries **72 threads** at +2527/-635, which is the richest single subject found and
likely worth its cost once the pipeline is proven.

## Screening notes

- `sort:comments-desc` is used because thread count cannot be filtered server-side. It biases toward
  large PRs, which is why the S band needed a separate pass at a >=3 thread bar rather than >=5.
- `reviewThreads.totalCount` was verified trustworthy against counted nodes (12 = 12) — unlike
  `timelineItems.totalCount`, which ignores its `itemTypes` filter and misled an earlier session.
- `find_candidates.sh` exits 4 rather than emitting zero rows on a GraphQL error. Two repos initially
  reported "0 candidates" from transient failures swallowed by `2>/dev/null`; both in fact have ~100.
