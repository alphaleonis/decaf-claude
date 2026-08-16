# `ours-bugs` vs `superpowers` — the two implementations, read side by side

Investigation `dcc-1ix0`, acceptance item 2. The pilot measured `superpowers` reporting a strict
superset of `ours-bugs`' findings at half the cost ($4.12 vs $8.56/cell) and half the wall time;
this document reads the two implementations that produced that result and names what the
single-agent path does better. Measured basis: `PILOT-RESULTS.md` (the pooled numbers),
`TUNING-SIGNALS.md` (the class axis and the traced suppression mechanism). Everything here is
subject to the pilot's own caveat: **two subjects, two repeats — replicate before recommending.**

## What exactly was compared

**`superpowers`** — the `requesting-code-review` skill from the `superpowers` plugin
(claude-plugins-official). Two files, 276 lines total: a 95-line SKILL.md and a 181-line
`code-reviewer.md` prompt template. The plugin cache holds 6.2.0 and 6.3.0; their review skills
differ only by a "You Do Not Dispatch Subagents" clause, and every pilot cell dispatched exactly
one reviewer subagent and returned its report verbatim (checked in all four cells' transcripts),
so the version ambiguity has no effect on what was measured.

**`ours-bugs`** — the `bugs` preset of `decaf-quality-dev:code-review`, from the dev copy at
`~/.claude/skills/decaf-quality-dev/`. Every file there is dated 2026-08-06 and unmodified since —
the pilot cells (2026-08-12) ran exactly these files. The SKILL.md alone is 799 lines (69KB),
before the agent briefs (~9–12KB each). All four pilot cells resolved to the same roster
(verified in each cell report's team announcement):

| seat | model tier under `models=low` | brief |
|---|---|---|
| `quick-reviewer` (floor) | cheap | fast generalist pattern checks |
| `broad-reviewer` (floor) | cheap | 5-category comprehensive analysis |
| `test-reviewer` (hard gate) | cheap | test-file quality, not coverage |
| `adversarial-reviewer` | **session model** | emergent failures "in the space between pattern-matching reviewers" |

## What each tool is

`superpowers`: the orchestrator computes two SHAs and dispatches **one** `general-purpose`
subagent with a filled prompt template. The template is a persona ("Senior Code Reviewer"), a
read-only rule, a five-domain checklist — plan alignment, code quality, architecture, testing,
production readiness — calibration guidance ("Categorize issues by actual severity. Not
everything is Critical."), and an output format: Strengths, then Critical / Important / Minor
issues with file:line and why-it-matters, then a merge verdict. Whatever the subagent writes *is*
the deliverable. There is no clustering, no screening, no validation, no consolidation, no gate —
no post-processing of any kind.

`ours-bugs`: a pipeline. Classify the changeset → evaluate 16 dispatch gates → rank and cap the
roster at 4 → assign model tiers → launch the wave in parallel with a shared base context
(`reach=narrow` rules, working-tree safety, probe nomination) → run nominated probes serially →
dispatch a clustering agent (mid tier) → dispatch one cheap screener per cluster against the
`evidence=strong` bar (≥80 solo, or ≥60 with 2+ independent finders) → consolidate (severity
normalization, corroboration promotion, confidence gate, minor-bucket routing) → re-review
dismissed items → dispatch a validation wave over unsettled primaries → emit a tiered report →
scan for recurring findings.

## The differences that explain the measurement

### 1. Both tools field exactly one deep reader — `superpowers` gives it the whole brief and the whole budget

Under `models=low`, three of decaf's four seats run on the cheap tier; the only session-model
reviewer in every pilot cell was `adversarial-reviewer`. So the two tools have the *same*
session-model reading capacity — one agent — but they aim it differently:

- `superpowers`' one agent carries a five-domain checklist and spends the entire $4.12, including
  on its own empirical verification.
- decaf's one agent is briefed to look *between* the other reviewers' lanes — a deliberately
  narrow slice — and shares the $8.56 with three cheap-tier reviewers, a clustering agent,
  per-cluster screeners, and a session-model orchestrator running the pipeline.

The cells show the deep lane is where the findings come from. In efcore r2, `adversarial-reviewer`
was the sole finder of the report's #2 and the only agent to construct counterexamples; the
cheap-tier agents corroborated #1 and originated nothing else. All three real defects `ours-bugs`
binned across the pilot were adversarial's (TUNING-SIGNALS, "Mechanism, traced"). The cheap-tier
lanes on that same cell — three reviewers plus screeners — cost $0.90 of the $8.56.

### 2. Breadth by checklist beats breadth by roster once the cap has bitten

decaf's theory of breadth is persona count; the `bugs` cap keeps four seats, three of them
cheap-tier pattern-matchers. `superpowers`' theory of breadth is one prompt listing every concern
to one strong model. The outcome, by judged class (both pooled subjects):

| | defect | risk | test-gap | docs | design | style | total |
|---|---|---|---|---|---|---|---|
| `superpowers` | 13 | 2 | 12 | 8 | 8 | 2 | 45 |
| `ours-bugs` | 6 | 0 | 0 | 0 | 1 | 0 | 7 |

The zero rows for test-gap/docs/style are **by design** — `reach=narrow` explicitly forbids
absence-hunting, and the report format omits those sections. The defect row is not explainable
that way. On the 16 real defect-class clusters in the pool, *detection* was nearly equal — 8
found by `ours-bugs`' reviewers, 9 by `superpowers`' one agent — but *reporting* was 5 vs 9. The
defect-class gap is mostly manufactured downstream of decaf's own reviewers.

### 3. The funnel only subtracts — and on this preset it subtracted real defects

The machinery after the reviewers (cluster → screen → confidence gate → validate) exists to buy
precision. Measured, it bought none: `ours-bugs` reported at 71% substantive, `superpowers` at
69% — and `superpowers`' 38 solo clusters were 68% substantive, so its volume was not cheaper
noise. The single agent self-calibrates from two prompt lines ("Categorize by actual severity",
"Don't say 'looks good' without checking") to the same precision decaf reaches with a screening
wave, a confidence gate, and a validator wave.

Meanwhile the funnel discarded 3 of the 8 real defects the reviewers delivered, via the traced
interaction: `evidence=strong`'s corroboration escape (≥60 with 2+ finders) is structurally
unavailable to the sole deep finder, because the cap makes corroboration scarce and the deep
finder's brief is non-overlapping *by construction*. `superpowers` has no admission bar to fail —
its equivalent findings went straight into the report.

### 4. The parallel roster forces reviewers to be read-only; the single agent executes

Because decaf runs four agents on one shared working tree, reviewers are barred from mutating
anything and must *nominate* probes for the orchestrator to run serially after the wave. The
`superpowers` reviewer has the tree to itself: in efcore r2 it built base and head commits in
separate worktrees, ran the repro queries, and put an executed before/after table in its report —
the strongest evidence class there is, produced inline, inside the $4.12. decaf's orchestrator
did comparable empirical work on the same subject, but as extra serial turns *after* the wave, on
the orchestrator's session-model meter.

The shared tree also means four agents each independently pay to read the diff and rebuild the
same understanding. Under `models=low` the redundant seats are at least cheap — the entire Haiku
lane, three reviewers plus the Step 4.95 screeners, is $0.91–$1.91 of each `bugs` cell, against
$6.38–$7.92 for the Opus lane (orchestrator + adversarial, inseparable in `modelUsage`). But what
the redundancy produces is corroboration, which decaf then *consumes as an admission signal* — the
thing `superpowers`' findings never needed in the first place.

## What the single-agent path does better, named

1. **Concentration**: the entire budget goes to one session-model reader instead of being split
   across cheap corroborators, screeners, and pipeline turns.
2. **Whole-surface license**: one brief spanning every concern class, instead of one narrow deep
   brief plus pattern-matchers.
3. **Self-calibration**: precision from prompt-level calibration instructions, indistinguishable
   in the measurement from decaf's screen + gate + validators — at zero cost and zero recall loss.
4. **Inline empirical verification**: sole ownership of the tree lets the reviewer execute its
   own probes at the moment of suspicion, rather than nominating them across a protocol boundary.
5. **No corroboration dependency**: a finding stands on its evidence, so a sole-finder deep catch
   is not structurally disadvantaged.
6. **No coordination surface**: nothing to cluster, screen, tier, or validate means no stage at
   which a true finding can be mis-tiered — decaf lost 3 real defects at exactly such a stage.

## What it gives up — and where the roster still wins

Read fairly, the single agent forgoes: any corroboration signal at all; dispatch gating (it costs
the same on a trivial diff as on a dangerous one); reach control (it reports docs gaps and
pre-existing issues even when the caller wanted only introduced defects — `bugs`' entire framing);
any independent check on its claims; and it is a single point of stochastic failure across
repeats. None of that showed up as a precision penalty in this pilot — but the pilot is two
subjects, and PILOT-RESULTS explicitly bars per-tool rankings from thinner evidence than this.

The counterweight the same data provides: `ours-audit` — ten reviewers and the *same* machinery —
is the roster's best defect finder (81% defect recall vs `superpowers`' 56%), and its screen
judged all 16 defect-class demotions correctly. The architecture is not refuted; the `bugs`
operating point is. Four seats is enough to pay roster overhead but too few for corroboration to
function, and `models=low` hollows the seats it does keep.

## Implications for the ≤$4 proposal (acceptance item 3)

- **The regression does not extrapolate to `roster=1`** (it predicts a negative cost). The
  anchor for a one-agent price is the `superpowers` datum itself: one session-model generalist
  that runs its own probes ≈ $4.12/cell.
- **decaf already ships a near-`superpowers` shape**: legacy `low` mode = `bugs roster=2
  evidence=norm`, with `broad-reviewer` — whose 5-category brief is the closest thing decaf has
  to the `superpowers` checklist — on the session model, `quick-reviewer` mid-tier, clustering
  inline, screen skipped, validation skipped. It was not in the pilot roster. Its remaining
  deltas from the `superpowers` shape: `reach=narrow`, the Step 5 confidence gate still applies,
  and two parallel reviewers still mean a read-only tree and probe nomination.
- Candidate mechanisms the comparison points at, for item 3 to develop and item 4 to measure:
  1. benchmark `low` as-is (zero implementation cost);
  2. a `roster=1` point — one session-model generalist seat with a whole-surface brief; with no
     parallel wave, the read-only constraint and probe indirection can be dropped, restoring
     inline execution;
  3. independently of roster: the `evidence` fix from the traced mechanism (`norm` below some
     roster floor), which addresses the 3 binned defects without touching cost.
- Already rejected in `dcc-1ix0` — do not re-propose: raising the roster cap, lowering the
  `strong` bar globally, making the corroboration clause roster-relative.
