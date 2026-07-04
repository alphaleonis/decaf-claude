# Session Reports — the `--report` flag

The `--report` flag on `code-review`, `auto-code-review`, `auto-tdd`, and `auto-dev` produces a
**comparison-grade session report** for skill-tuning: a self-contained record of what the review
loop did, what it found, and what it cost, in a stable format so sessions can be compared across
time and across skill revisions. (Reference examples of the target format: the reports on the
plugin repo's `tuning` branch, `reports/2026-07-0{3,4}-*-code-review-session/`.)

## Flag plumbing

- **`auto-tdd` / `auto-dev --report`** → forward `--report` to `auto-code-review` and contribute
  the implementation-phase record (see Data duties).
- **`auto-code-review --report`** → forward `--report` to every `/code-review` invocation, keep
  the session ledger through the loop, assemble and write the report in its final step.
- **`code-review --report`** → collect wave metrics and append the **Session Metrics** section to
  the consolidated review file. On a standalone invocation (no orchestrating loop), the enriched
  consolidated file *is* the report — no separate folder is written.

## Output location

`.decaf/session-reports/<YYYY-MM-DD>-<work-item-or-slug>-code-review-session/` in the target
project (per the `.decaf/` artifacts convention):

```
README.md                            # the session report (format below)
iteration-N-consolidated-review.md   # verbatim copy of each iteration's .decaf/code-reviews file
```

Never overwrite an existing report directory — suffix `-2`, `-3`, … on collision. Copies must be
byte-identical to the originals (`cp`, not regeneration).

## Truth discipline (non-negotiable)

- Report **harness-reported figures verbatim** — never invent, recompute, or silently round.
- Label everything not directly measured: `[Estimate]` (with the estimation basis), `[Inference]`,
  `[Unverified]`.
- It is **[Unverified] whether a subagent's reported token figure includes its own children** —
  carry this caveat wherever per-subagent figures are summed.
- Missing data is recorded as *missing* ("not reported"), never silently estimated or omitted.

## Data duties

### `code-review` — Session Metrics (per wave)

Record at dispatch time from each Agent tool result — this is the **only** context that ever sees
the reviewer/validator results, so this data is unrecoverable if not captured here:

```markdown
## Session Metrics (--report)

**Wave timing**: dispatched HH:MM:SS → last reviewer returned HH:MM:SS → consolidated HH:MM:SS
→ validation done HH:MM:SS → file written HH:MM:SS

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|--------|-----------|----------|--------------------|
| quick-reviewer | reviewer | sonnet (mid) | {reported} | {n} | {s} | {n} |
| … one row per reviewer AND per validator … |

**Pre-flight gates**: {what ran + results, or "none discoverable"}
**Anomalies**: {dispatch retries, unusable returns, injected-content flags — or "none"}
```

Figures come from the harness's tool-result metadata (e.g. `subagent_tokens`, tool-use count,
duration). If the harness reports no usage for a call, write "not reported" in that cell.

### `auto-code-review` — session ledger + assembly

Track through the loop (in-context notes are fine; no state file required):

- **Per iteration**: mode (+ roster cap and which gate-matched agents the cap dropped), scope,
  verdict, finding counts (by severity + minor), validation stats, the fix-delta classification
  and chosen `reReviewMode` (Step 5.4), review-file path, orchestrator-subagent usage.
- **Per fix round**: subagent usage, counts (fixed / TDD / differently / not-addressing /
  declined / skipped), files modified.
- **Triage decisions** in main context: per finding — fix / skip / dismiss / defer (+ work item).
- **Anomalies**: any resume, nudge, retry, or kill of a subagent; any deviation from the skills'
  expected flow — or "none". These are the highest-value tuning signals; do not smooth them over.
- **Implementation-phase record** when the caller provided one.

At the end (after the final summary), write the report folder per the format below.

### `auto-tdd` / `auto-dev` — implementation phase

Provide to `auto-code-review` (same-context invocation makes this trivial): implementation
subagent usage (tokens / tool calls / duration), changeset stats (files changed, +/− lines, new
files), and a one-line scope/plan description.

## README.md format

```markdown
# Code-Review Session Report — <work item> (<YYYY-MM-DD>)

<Subject: what was built/fixed; one paragraph on the changeset's character (declarative vs
logic-heavy, languages, size). Skill chain with the exact invocation arguments.>

## 1. Iteration overview
| Iter | Mode | Scope | Verdict | Primary findings | Minor | Validation wave | Fixes applied after |
<one row per iteration; totals line: fixed / deferred / skipped / dismissed / refuted; final state>
<1-3 bullets: the quality signals that justified (or didn't) the loop's cost>

## 2. Agent inventory
<Per iteration: roster with dispatch/drop rationale (from the consolidated files).>
<Table of non-reviewer agents (implementation, orchestrators, fix rounds) with reported usage.>

## 3. Token usage
<All harness-reported figures, including the per-reviewer/validator rows from Session Metrics.
Sub-totals: review-side vs build-side; build:review ratio. Anything still unmeasured, listed as
such. Carry the children-inclusion caveat.>

## 4. Process observations
<What matched the skills' expected behavior and what deviated, from the anomalies ledger. Mark
each item: ✅ held · ⚠️ deviation · 💡 tuning candidate. "Zero anomalies" is itself a result.>

## 5. Timeline
<Wall-clock table from wave timing + subagent durations; end-to-end figure for the review-fix
portion; note any non-productive share.>

## 6. Per-agent yield
| Agent | Iter 1 (found/unique) | Iter 2 | … | Drove a verdict or fix? |
<From the consolidated files' Agent Summary tables. Note: verdict-driver concentration;
assurance-only work ("found 0 ≠ did nothing" — say what the agent verified/cleared); for each
roster cap, whether any dropped agent's lane produced evidence it was missed (natural ablation).>

<Closing 2-3 sentences: outcome vs cost, with explicit caveats (sample size, changeset character).>
```

## What this is not

- Not a replacement for the consolidated review files — those stay authoritative for findings.
- Not analysis-on-demand: the report records; cross-session *comparison* and tuning decisions stay
  with the operator (a sample of one session is not tuning evidence).
