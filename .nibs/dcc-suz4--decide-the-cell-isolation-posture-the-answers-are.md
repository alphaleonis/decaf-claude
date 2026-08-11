---
# dcc-suz4
version: 1
title: 'Decide the cell isolation posture: the answers are reachable from a cell'
status: completed
type: task
priority: critical
created_at: 2026-08-11T08:09:18Z
updated_at: 2026-08-11T08:45:22Z
parent: dcc-ho2w
order: m
---

A cell runs `cd v2/pooled/<subject>/repo` with `PERM_FLAGS="--dangerously-skip-permissions"`, so it
has no path gating at all. The scored answers are three relative paths away, and no shim is involved:

    ../threads.json                        this subject's admitted threads, with path:line and body
    ../../*/threads.json                   all 12 subjects
    ../../../analysis/subject-*/answer-key.json
    ../../../runs/*/final-output.md        every prior cell's output

`reset_repo()` cleans inside the checkout only, so none of this is in its scope. This is `dcc-2cxq`
with the contamination moved one directory up and the payload upgraded from "another tool's report"
to "the answer". Relocating the files does not help — with the bypass flag an absolute path reaches
them from anywhere.

Demonstrated, not assumed: `v2/analysis/HARNESS-REVIEW.md` B1.

## Options

- **(a) Permission allowlist** replacing the blanket bypass, scoping Read/Grep/Glob to the checkout.
  Strongest. Risk: it changes what the tools can do, and tool behavior is the thing being measured.
- **(b) Sandbox** rooted at the checkout (container or bwrap). Strong and behavior-neutral. Most setup.
- **(c) Detection only** — `v2/verify_cell_isolation.sh` scans the cell transcript for reads of the
  answer paths, the way the v1 stray-report question was actually settled. Already implemented and
  additive, but it detects rather than prevents.

(c) is in place. The decision is whether the pilot ships with detection alone.

## Acceptance

- [x] Posture chosen and written down with its reasoning
- [x] Implemented as (d), a PreToolUse hook, with two cells run under it — see the summary

- [x] `verify_cell_isolation.sh` wired into the cell runner so no cell is scored without it passing

## Summary

**Completed 2026-08-11** — **Completed 2026-08-11.** A fourth option beat the three this nib was filed with.

The three considered were (a) a permission allowlist replacing `--dangerously-skip-permissions`,
(b) a sandbox rooted at the checkout, (c) transcript detection only. (a) changes what the tools can
do, and tool behavior is exactly what the benchmark measures; (b) is substantial setup; (c) detects
rather than prevents.

**(d) A `PreToolUse` hook still fires under `--dangerously-skip-permissions`, and exit 2 blocks the
call.** This repo already depends on that for `decaf-protection`; re-measured here on Claude Code
2.1.226, where the payload reports `permission_mode: bypassPermissions` and the block held against
both the `Read` tool and a `cat ../notes-b.json` Bash fallback. That gives prevention *without*
touching the permission posture the tools run under.

`v2/hooks/block-answer-access.js` denies any path resolving **inside `competition/benchmark/` but
outside the cell's own checkout**, and allows everything else untouched. `run_cell_v2.sh` generates
the per-cell settings file (the hook command needs an absolute path), exports `BENCH_CELL_REPO`, and
logs every verdict to `access.log` under a new `fs` channel that `leak_audit.sh` renders.

Verified on the decision boundary — 12 escape attempts denied (`../threads.json`,
`../../*/threads.json`, `../../../analysis/*/answer-key.json`, `ls ../../../runs/`,
`cd .. && cat threads.json`, an absolute `grep -r` over `v2/`), 10 legitimate operations allowed,
including `cat test/fixture.json` (a repo-internal file whose name collides with a harness artifact)
and absolute system paths.

Then end to end on the real `sveltejs-kit-15685` checkout:

| Cell | Paths evaluated | Denied | Outcome |
|---|---|---|---|
| adversarially told to read `../threads.json`, `../fixture.json` and the sibling subjects | 3 | **3** | obtained none of them |
| an ordinary review of `base..checkpoint` | 29 | **0** | completed normally |

So it enforces and is behavior-neutral, which is what ruled (a) out — the neutrality is measured, not
assumed. Detection is kept as well: `verify_cell_isolation.sh` still re-checks every transcript, on
the principle that a control which has only been reasoned about is not a control.

⚠️ Both cells ran on **Haiku 4.5**, not `BENCH_MODEL`, and one cell is not a measurement. They show
the control works and does not obstruct; they say nothing about any tool's quality.

Incidental, and worth knowing before [[dcc-vkeh]]: the ordinary-review cell independently reported
`packages/kit/src/exports/vite/index.js:603`, which is one of that subject's three admitted threads —
found with no access to the answers. A single Haiku cell proves nothing about recall, but it is the
first end-to-end evidence that the thread axis produces a signal at all.
