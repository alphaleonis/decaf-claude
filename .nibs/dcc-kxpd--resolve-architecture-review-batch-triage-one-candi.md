---
# dcc-kxpd
version: 1
title: 'resolve-architecture-review batch: triage one candidate at a time with a plain summary'
status: completed
type: task
created_at: 2026-10-10T15:58:16Z
updated_at: 2026-10-10T15:58:38Z
order: zzzzzzz
---

Batch triage (Step B1) asks about four candidates per AskUserQuestion call, each shown only by its title. A title alone is too little to decide on.

- [x] B1 presents one candidate per response: a plain-language summary, then one question about that candidate only
- [x] Record each triage answer as the user gives it

## Summary

**Completed 2026-10-10** — B1 now walks candidates one per response: a two-or-three-sentence plain summary from the candidates file, then a single AskUserQuestion about that candidate. Answers are recorded as given. The compact table of all candidates stays as an overview.
