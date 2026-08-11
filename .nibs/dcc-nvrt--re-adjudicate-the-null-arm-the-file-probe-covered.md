---
# dcc-nvrt
version: 1
title: 'Re-adjudicate the null arm: the file probe covered 12 of 33 files'
status: todo
type: task
priority: high
created_at: 2026-08-11T08:20:56Z
updated_at: 2026-08-11T08:20:56Z
parent: dcc-ho2w
order: w
---

`verify_null.sh` capped its file probe at the first 12 files and said nothing about the rest, so the
nullness adjudication recorded in [[dcc-mjj5]] covered a subset of two subjects:

| Null subject | files | probed then | never queried |
|---|---|---|---|
| `jellyfin#16695` (S) | 3 | 3 | 0 |
| `grafana#122269` (M) | 17 | 12 | 5 |
| `immich#28204` (L) | 33 | 12 | **21** |

The cap is now reported (`dcc-3cm6`). Re-running with it lifted surfaces **eight** files on
`immich#28204` carrying later fix-shaped commits, where the recorded adjudication addressed one
("a different endpoint in a shared e2e spec"). Seven are new, and one is not an e2e spec:

    server/src/middleware/global-exception.filter.ts
      fix: error log on aborted uploads (#28806)

`immich#28204` is *"refactor(server)!: structured validation error responses"* — the global exception
filter is the production file most central to what the PR changes, and a later fix touching it is
exactly the shape the line-level test exists to adjudicate.

This matters because `immich#28204` is the **large** null subject. If it is not null, the noise floor
for large changes is measured on a change that had something to find, which biases every large-subject
precision figure read against it.

Not a defect in the arm's design — the methodology already says file overlap is "a screen, not a
verdict". It is adjudication that was never done because the probe never reported the gap.

## Acceptance

- [ ] All eight `immich#28204` hits adjudicated at line level, `global-exception.filter.ts` first
- [ ] The five unqueried `grafana#122269` files probed and adjudicated
- [ ] Verdicts recorded per subject where a later reader will find them, not only in a nib summary
- [ ] If `immich#28204` fails, source a replacement large null subject before [[dcc-vkeh]] reads a
      noise floor from it
