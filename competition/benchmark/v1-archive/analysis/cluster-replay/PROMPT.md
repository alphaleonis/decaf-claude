# The clustering-replay prompt

The prompt given to each clustering agent in `cluster_replay.py`'s replay experiment, verbatim.
`{RUN}` is the task name (`subject-06-r1`), `{WORKDIR}` the directory `build` wrote to.

**This file exists because the 2026-07-29 run's prompt was not recorded.** That run produced the
F1 0.87 / 0.86 / 0.80 tier comparison the skill's Step 4.9 cites, and it cannot be reproduced or
extended without guessing at its wording — which is exactly what the 2026-08-06 subject 6 run had
to do. A replay number is only comparable to another replay number if the prompt is held fixed, so
any future run must use this file or supersede it explicitly.

The wording below is derived from the code-review skill's **Step 4.9** brief — the grouping rules,
the singletons-are-expected instruction, and the hard count assertion all come from there. That
makes it the right prompt for asking whether the shipping design holds, and the wrong prompt for
comparing against 2026-07-29.

Model: mid tier (sonnet). One agent per task.

---

Group code-review findings into clusters, each cluster being ONE underlying issue.

Read exactly this file and nothing else:
`{WORKDIR}/{RUN}.input.json`

It is a JSON array of findings, each `{id, file, line, category, claim}`, produced by several independent reviewers looking at the same changeset. Different reviewers often report the same defect in different words.

STRICT CONSTRAINT — this is a measurement, and reading anything else invalidates it:
- Do NOT read, glob, grep, or open any other file. Not the repository under review, not any other file in that directory (several contain the answer), not any benchmark or analysis file.
- Work only from the claims in the input file. You are not verifying the findings, only grouping them.

Grouping rules:
- Same underlying issue = the same defect at the same place. Group those together.
- Different symptoms of one root cause = one group.
- A finding that nothing else matches is a group of one. Singletons are expected and correct — forcing merges is worse than leaving things apart.
- Same file and nearby lines is evidence of a match, but not proof: two unrelated defects can sit on one line, and one defect can be reported at different lines by different reviewers.

Write your answer to:
`{WORKDIR}/{RUN}.result.json`

as exactly `{"groups": [["F00","F07"], ["F03"], ...]}` — a JSON object, one key, a list of lists of id strings. No commentary in the file.

COUNT ASSERTION — do this before you finish, it is the most common failure:
Every input id must appear in EXACTLY ONE group. Not zero, not twice. After writing the file, count the ids in your output and confirm the total equals the number of findings in the input, and that the set of ids is identical. If it does not match, fix the file and check again. Do not return a partial grouping.

Return only: the number of input findings, the number of groups, and confirmation that the count assertion passed.

---

## Verify the count assertion yourself

The agent reports whether it passed; that report is not evidence. Both 2026-08-06 runs passed under
independent check, but the failure this assertion guards against is a model silently dropping
findings and not noticing — so re-derive it from the files rather than trusting the return value.
`score` reports a `dropped` column for exactly this reason.
