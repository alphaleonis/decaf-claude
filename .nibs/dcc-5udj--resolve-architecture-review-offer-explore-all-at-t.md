---
# dcc-5udj
version: 1
title: 'resolve-architecture-review: offer "Explore all" at the start'
status: in-progress
type: task
created_at: 2026-11-25T14:47:24Z
updated_at: 2026-11-25T14:47:45Z
order: I
---

Today the interactive mode asks Explore / Skip / Dismiss / Defer for every candidate, and batch mode's triage asks the same per candidate. When the operator already wants every candidate explored, that is one approval per candidate with nothing to decide.

Add one question at the start (Step 4): **Explore all** or **Choose each**. With Explore all, no per-candidate action question is asked. Interactive mode still walks the candidates one at a time — frame, design, pick, RFC, next — and the operator can still skip, dismiss or defer a candidate in a free-form answer at the interface pick. Batch mode marks every candidate Explore and goes straight to the framing gate, where candidates can still be dropped.

## Acceptance

- [x] [run] `scripts/check-skill-references.sh` — expect: exit 0
- [ ] [manual] An interactive run with Explore all goes from the summary straight to candidate #1's framing and asks no action question for any candidate — needs a real architecture-review candidates file and a live session.
