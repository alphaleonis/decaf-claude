---
# dcc-lf4a
version: 1
title: Make the shared-context-file pattern the documented default in code-review
status: todo
type: feature
priority: low
estimate: s
tags:
    - code-review
created_at: 2026-07-28T20:41:05Z
updated_at: 2026-07-28T20:42:40Z
parent: dcc-hyxw
order: ay
---

# Why

On a small subject the orchestrator pasted the diff into **all 10 reviewer prompts** — 8 of the
10 byte-identical, ~63.6k chars ≈ 15.9k tokens — and re-composed the working-tree safety preamble
10 times (9 of 10 *distinct* hashes: it rewrites rather than copies, ~5.4k tokens).

On a large subject it did none of that. It wrote `/tmp/pr130837.diff` plus a
`/tmp/pr130837_context.md` and pointed all 20 agents at the files: **0 of 20 prompts contained a
diff**, and prompts averaged 2.2 KB against 6.8 KB on the small subject.

`decaf-quality/skills/code-review/SKILL.md:253` says only `<paste git diff or file content here>`.
The shared-context-file pattern is **emergent behaviour** — it appears when the diff is big and
is skipped when it is small, which is exactly backwards from where the saving is free.

# What to change

Make it the documented default in the Step 3 dispatch: write the diff (and the shared pre-flight
/ safety preamble) once to a path, and pass the path. Every reviewer already has Bash and can
read it.

# Honest sizing

Small. The corrected numbers cap the prize: agent prompts are ~a third of orchestrator output,
and the orchestrator is 23% of session output — so this is low single-digit percent of session
cost, and zero on large diffs where the orchestrator already does it.

Worth doing for consistency and determinism rather than for the saving. Do not let it displace
#dcc-c2uc or #dcc-3fl5 in priority.

# Acceptance

- [ ] [run] `rg -n "paste git diff" decaf-quality/skills/code-review/SKILL.md` — expect: no
      output; the inline-paste instruction is gone
- [ ] [run] `rg -n "shared context|context file" decaf-quality/skills/code-review/SKILL.md` —
      expect: the write-once/pass-a-path pattern documented in Step 3
- [ ] [manual] A small-subject re-run shows reviewer prompts no longer carrying the diff.
      `[manual]` because confirming it requires reading the dispatched prompts in the transcript,
      which no committed artifact captures.

# Notes

Reasoning and measured basis: #dcc-e0wj → `# Candidate interventions` → item 6. Prompt-capture
caveat: the benchmark archives sub-agent *outputs*, not the prompts sent to them, so verification
means reading the session transcript directly.
