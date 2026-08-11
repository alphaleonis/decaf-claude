---
# dcc-13wh
version: 1
title: Decide v2 pilot matrix scope at the measured $600 cost
status: todo
type: task
priority: high
created_at: 2026-08-11T16:46:34Z
updated_at: 2026-08-11T16:47:08Z
parent: dcc-ho2w
order: "y"
---

The pilot ([[dcc-vkeh]]) is built, probed and committed; only the spend decision is outstanding.

Seven probe cells on `dotnet-efcore-34127` (library M, 8 files, +202/-100), shim on, one repeat each,
all isolation-CLEAN with zero denied accesses:

| Tool | cost | wall |
|---|---|---|
| `ours-audit` | $28.52 | 1851s |
| `pr-review-toolkit` | $19.57 | 1384s |
| `ours-review` | $17.84 | 1528s |
| `comprehensive-review` | $17.61 | 1925s |
| `ours-bugs` | $7.99 | 1249s |
| `superpowers` | $4.28 | 804s |
| `anthropic-code-review` | $3.37 | 699s |
| **one repeat, 7 tools** | **$99.18** | ~2.6h |

## The options, costed

| Option | Cells | Cost | What it gives up |
|---|---|---|---|
| Full matrix | 35 | ~$600 | nothing |
| 1 repeat | 21 | ~$300 | within-tool variance — separation would rest on single observations |
| efcore + null, 2 repeats | 21 | ~$300 | cross-subject and cross-language evidence (C# only, no Go) |

The only soft figure is the prometheus multiplier: it is size L (+1409 lines against efcore's +202)
and is scaled x1.5 on judgment, not measurement. One prometheus cell would firm that up for ~$5-30
depending on the tool chosen.

## Why the estimate moved twice

Both revisions came from extrapolating instead of measuring. The archived v1-era costs understated v2
by 4-5x for any tool that builds: `ours-review` cost $17.84 against $4.16 archived, while
`anthropic-code-review` moved only $2.85 -> $3.37. The split is not the tool, it is whether the cell
uses the build toolchain v2 gives it ([[dcc-fhp1]]) — the five expensive cells compiled EF Core and
executed queries; the two cheap ones read the diff.

## Acceptance

- [ ] Operator picks a matrix scope, or cancels the pilot
