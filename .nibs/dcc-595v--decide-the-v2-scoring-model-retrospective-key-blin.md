---
# dcc-595v
version: 1
title: 'Decide the v2 scoring model: retrospective key + blind judge'
status: todo
type: research
priority: critical
created_at: 2026-08-10T17:42:29Z
updated_at: 2026-08-10T17:43:40Z
parent: dcc-ho2w
order: V
---

Key-only scoring is probably the wrong frame, and subject 2 is the evidence: its key has ONE entry,
while each tool produced ~6 findings, several genuinely valid — the dropped `BindingFlags.Static`,
`FlattenHierarchy` being a no-op for instance lookups, and the added tests never exercising the
fallback branch. A key-only metric discards all of it, and a 1-entry key cannot rank tools at all
(everyone who finds the defect scores 1/1).

v1 already solved this shape: the key carries the primary defect, and a blind judge classifies
everything else as `valid-other` / `false-positive` / `nitpick`. That makes thin keys survivable.

Decide, before building anything:

- Is the retrospective key the METRIC, or one INPUT to a judged metric? (Recommendation: the latter.)
- Which v1 verdict vocabulary carries over, and what replaces `TP-human` now that human issues are
  reclassified as secondary escaped defects?
- How is severity weighted? v1's precision was severity-unweighted, so a tool reporting four minor
  issues outscored one finding the revert-forcing defect.
- Does the judge see the key? (v1: yes, blind to tool identity. Keep.)
- Judge contamination: the grading model's training cutoff is later than most subjects' merge dates,
  so it may know the defect independently. Blind grading hides the TOOL, not the answer. Decide
  whether this is mitigated or merely disclosed.

Blocks the pipeline work — build once the shape is settled.

## Acceptance

- [ ] Written decision in METHODOLOGY-v2.md replacing the current key-only framing
- [ ] Verdict vocabulary and severity treatment specified
- [ ] Judge-contamination position stated explicitly
