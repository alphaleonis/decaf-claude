---
# dcc-9ncz
version: 1
title: Build answer keys for the anchor subjects (blind-spot detection only)
status: in-progress
type: task
priority: normal
created_at: 2026-08-10T18:35:16Z
updated_at: 2026-08-11T11:17:29Z
parent: dcc-ho2w
blocked_by:
    - dcc-595v
order: 8w
---

Surviving the ground-truth audit ([[dcc-5xad]]) is not the same as being usable. v2 fixtures and
answer keys exist for subjects **2 and 9 only**. The other five survivors are validated but have no
checkpoint, no fixture and no key.

**No longer gates the pilot.** That claim predates the pooled corpus: [[dcc-vkeh]] runs on two
*pooled* subjects, of which 12 are built, and it is unblocked. The anchor is a separate instrument
that never ranks tools, so this can proceed at its own pace.

## Re-scoped by the instrument decision

[[dcc-595v]] demoted the retrospective key from the ranking metric to **the anchor** — its only job is
detecting a defect class that *every* tool misses. It is no longer on the critical path, hence the
drop to normal priority and the move behind the corpus work.

Practical consequence: keys are still worth building, but **the marginal value falls off fast**. The
anchor answers a yes/no about the whole field, so a handful of high-confidence entries serves as well
as twelve. Build in the order below and stop when the anchor is convincing rather than complete;
subjects 7 and 12 are the strongest per unit of effort (7 is the cleanest defect in the corpus, 12 is
the richest key).

## To build

Order is by value per unit of effort, not by subject number. Follow METHODOLOGY-v2 §4d (Steps A1-A6)
plus the shared spine in §4b.

| Order | Subject | Lang/size | Projected entries | Why here |
|---|---|---|---|---|
| ✅ 1 | 7 — prometheus#13777 | Go / small | 1 (built) | Crispest defect in the corpus; a 78-line single-file PR whose whole content is the defect, so one entry is a COMPLETE key |
| ✅ 2 | 12 — rust#153540 | Rust / large | **1** (built; ~3 projected) | The ~3 projection was wrong: ALL 12 threads fail `must_flag`, so the thread count contributed nothing |
| 3 | 10 — ripgrep#3185 | Rust / small | 1 | Fix deletes the loop the PR added and root-causes it in the body |
| 4 | 8 — k8s#129768 | Go / medium | ~2 | Both defects stated precisely, but only in the re-land #133995, not the revert |
| 5 | 1 — efcore#32770 | C# / small | ~2 | Mechanism is reconstructed from issue #32944 stack trace, not stated by a fix body |

Built already: 2 (1 entry) and 9 (2 entries). Subject 11 has a key at its as-opened checkpoint that
is deliberately NOT part of this projection.

## Watch for

- **Fetch the checkpoint and nothing else** — a second `fetch --depth 1` of the base re-shallows the
  repo (129,013 commits collapsed to 7 on subject 9). Verify `git rev-list --count HEAD`.
- **Each checkpoint has its own merge base.** Reusing an earlier one turned 18 files into 240.
- A review comment proves something was *once* true, never that it shipped — re-read every candidate
  against the code at the checkpoint. This is how subjects 5 and 11 went invalid.
- Record `thread_comments`, not `human_threads.count` — the v1 field counted comments.

## Acceptance

- [ ] 5 fixtures in `v2/subjects/` with per-checkpoint merge bases and diff stats
- [ ] 5 answer keys in `v2/analysis/subject-NN/answer-key.json`, each with `rejected[]` and
      `admission_evidence` per entry
- [ ] Each key judged **complete for its diff** and that judgment recorded — entry count is not the
      test (see [[dcc-595v]])
- [ ] Step 8 airtightness check passes per fixture (history depth, clean tree, no remote, no
      fix/revert reference reachable)
