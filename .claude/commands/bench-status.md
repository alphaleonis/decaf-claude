---
description: Show benchmark v2 progress — cells run, cost, which cells must not be scored, which subjects are graded
---

Read-only. Report benchmark **v2** progress:

```
bash competition/benchmark/v2/status.sh              # treatment arm (shim on)
bash competition/benchmark/v2/status.sh --arm off    # control arm
bash competition/benchmark/v2/status.sh --json       # machine-readable
```

Relay the output. Two parts of it need a sentence of interpretation rather than a paste:

**The `DO NOT SCORE` list is the point of the command.** Four different failures land there and they
have different remedies, so name which one applies rather than calling them all "failed":

| Reason | What it means | What to do |
|---|---|---|
| `probe cell (r0)` | ran to prove a tool's invocation works before the matrix spent | nothing — probes are never scored, by convention |
| `empty final-output.md` | the cell crashed | re-run it |
| `api <code>` | rate or spend limit truncated it mid-review; the output is a well-formed prefix | wait for the limit, then re-run — do not debug the harness |
| `isolation <state>` | CONTAMINATED, NETWORK-GIT, UNVERIFIED or MISSING | read `isolation.txt` before anything else; a cell whose transcript cannot be found is UNVERIFIED, **not** clean |

**`single pass` on a scored subject is a blocker, not a note.** Per-tool figures from one grading
pass are not publishable — judge variance exceeds tool variance at every denominator size
(`v2/analysis/PILOT-RESULTS.md`). Say so if it appears.

Do not compute totals by hand or eyeball the run directories; the script reads every cell's
`meter.json`, `isolation.txt` and `tool-artifacts.tsv` and is the only thing that should be counting.
