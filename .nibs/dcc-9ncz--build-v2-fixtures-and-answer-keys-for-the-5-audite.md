---
# dcc-9ncz
version: 1
title: Build v2 fixtures and answer keys for the 5 audited survivors
status: todo
type: task
priority: critical
created_at: 2026-08-10T18:35:16Z
updated_at: 2026-08-10T18:35:43Z
parent: dcc-ho2w
order: S
---

Surviving the ground-truth audit ([[dcc-5xad]]) is not the same as being usable. v2 fixtures and
answer keys exist for subjects **2 and 9 only**. The other five survivors are validated but have no
checkpoint, no fixture and no key.

**This, not the replacements, is what gates the pilot** — [[dcc-vkeh]] needs two built subjects and
currently has exactly two, both C#/Go-medium-large. Replacements ([[dcc-ixyy]]) can proceed in
parallel; they do not block this.

## To build (METHODOLOGY-v2 section 4, all 8 steps)

| # | Subject | Lang/size | Expected entries | Notes from the audit |
|---|---|---|---|---|
| 1 | dotnet/efcore#32770 | C# / small | ~2 | assert/`-1` sentinel; 2 threads (value-tuple, "Re-add Assert"). 100 cross-refs — the worst leak surface in the corpus, so verify the shim log carefully on the first cell |
| 7 | prometheus/prometheus#13777 | Go / small | 1 | whole PR is the defect; merged 39 min after opening, so the as-opened head is almost certainly the checkpoint |
| 8 | kubernetes/kubernetes#129768 | Go / medium | ~2 | both entries come from re-land #133995, not the revert; liggitt's perma-race thread is a third candidate but he argued it was acceptable — adjudicate explicitly |
| 10 | BurntSushi/ripgrep#3185 | Rust / small | 1 | defect isolated to 1 of 2 commits; the other commit was the fix that was actually needed |
| 12 | rust-lang/rust#153540 | Rust / large | ~3 | richest available; fix undoes one named commit (`29e9273`); 12 real threads to adjudicate |

Evidence for each is already gathered under `competition/benchmark/v2/analysis/subject-NN/audit/`
(gitignored; regenerate with `v2/audit_subject.sh <id>`). Verdict reasoning is in
`v2/analysis/GROUND-TRUTH-AUDIT.md`.

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
