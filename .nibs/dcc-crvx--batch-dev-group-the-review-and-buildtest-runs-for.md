---
# dcc-crvx
version: 1
title: 'batch-dev: implement small series nibs as a group, with one build/test and one review'
status: in-progress
type: feature
created_at: 2026-11-24T13:04:26Z
updated_at: 2026-11-24T13:18:01Z
order: zzzzzzzzzs
---

In Phase 4, batch-dev may combine consecutive series nibs into a *review group*. That saves one review run and one full build/test per extra nib, which matters most for batches of stray fixes and on projects with long build/test runs. Today Phase 6a runs one full `/decaf-quality:auto-code-review` per nib, and the Common rules run the full build (and tests, for tdd work) after each nib.

Parallel clusters already review once per cluster: Phase 7 soft-resets to the pre-merge tag, writes one spec file with every cluster item and runs one review (dcc-s2a6). The group path reuses that mechanism.

## Who qualifies

A nib qualifies when its Phase 2 Explore summary shows a small, contained change with no open `risks`/`unknowns`. It doesn't need to overlap with the other nibs: stray fixes from unrelated areas are the main case, and the fixed cost is paid either way. A group is consecutive in series order, so dependency order still holds. tdd and dev nibs can share a group; the implementer's brief gives each nib's approach. A high-risk area needs no special rule: code-review's content triggers add the matching specialist for the whole group.

## Group size

There's no numeric limit; the conductor decides. It closes a group when the members together span more separate areas than one reviewer can hold at once, or when a nib's estimate is borderline "small". Phase 5 shows each group with its estimated file count, and Adjust can split one.

## Execution (Phase 6a, group path)

1. Tag the group start. Dispatch one implementer for the whole group. It implements the nibs in order and stages each one. A tdd nib's red-green loop runs only its targeted tests; the full build and suite do not run between nibs.
2. The conductor commits each nib as it finishes (code plus tracker file).
3. Run the full build and tests once, after the last nib. On failure, the implementer fixes it.
4. `git reset --soft <group-start>`, write `.decaf/batch-dev/specs/group-<n>.md` (the cluster-spec format) and run one `auto-code-review` with `--implementer <group agent>`.
5. `git reset --soft <last nib commit>`, so only the review's fixes are staged, and commit them as one review-fixes commit. Close the group's nibs.

The result is one commit per nib plus one review-fixes commit. Tested in a scratch repo, including two nibs editing the same file. The per-nib commits in between are never built or tested; only the group's tip is.

One review per group also means one set of auto-code-review fix-round test runs (`{testCommand}` after each fix), not one per nib.

## Failure

When a nib still has to be parked after the implementer's attempt, `git revert` its commit, plus those of any later group members that depend on it. Write a `Batch failure note` for each, per Failure handling, and let the rest of the group land. For a build/test break, find the culprit by building at each per-nib commit; this runs only on failure. For a review that won't converge (as with bibbla's bibl-nle7), the findings point at the nib.

## Flag

Grouping is on by default. `--no-group` turns it off, which is the only off-switch under `--unattended`. `auto-deliver` accepts `--no-group` and passes it to batch-dev in EXECUTE.

## Docs

The README sections for batch-dev and auto-deliver get the flag and the group path. `conventions/artifacts.md` lists `group-<n>.md` beside `cluster-<n>.md`.

## Key Decisions

- Commits: one per nib plus one review-fixes commit, via two soft resets; no code-review change. Rejected: one commit per group; splitting by path after review (breaks when nibs share a file).
- Qualifying: small and well understood; overlap not required.
- Size: conductor judgment with written signals, no number until `--report` data supports one (follow-up dcc-va4f).
- Failure: revert and park only the stuck nib and its dependents in the group.
- Default on, with `--no-group`; forwarded by auto-deliver.

## Acceptance

- [x] [run] `grep -c -- '--no-group' decaf-build/skills/batch-dev/SKILL.md` — expect: ≥ 2 (argument hint, argument parsing)
- [x] [run] `grep -c -- '--no-group' decaf-build/skills/auto-deliver/SKILL.md` — expect: ≥ 2 (argument hint, forwarded in EXECUTE)
- [x] [run] `grep -c -- '--no-group' README.md` — expect: ≥ 2 (batch-dev and auto-deliver argument lists)
- [x] [run] `grep -n 'group-<n>' conventions/artifacts.md` — expect: one match in the batch-dev specs line
- [x] [run] `grep -n -i 'review group' decaf-build/skills/batch-dev/SKILL.md` — expect: matches in Phase 4, the Phase 5 template, Phase 6a and Failure handling
- [x] [run] `bash scripts/check-skill-references.sh` — expect: exit 0
- [ ] [manual] An attended batch-dev run over three or more small stray-fix nibs shows one review group with its file estimate in Phase 5, runs one build/test and one auto-code-review for the group, and leaves one commit per nib plus one review-fixes commit. Reason: needs a live model run; no harness for that exists.

## Context

Raised 2026-11-24 while discussing whether batch-dev / auto-deliver review each item separately. The operator noted that many batch-dev runs are not broken-down phases but stray bugs found in other reviews and other minor items, so `breakdown-phase` is not the lever; the per-nib review and build/test are. Example: three different one-line fixes each getting a full review, and a 15-minute build/test run three times instead of once. Related goal: dcc-b578 (cheaper reviews in tokens without losing findings; runtime secondary). Parking in practice: three `Batch failure note`s across 12 nibs projects, all bibbla, none from a build/test break.
