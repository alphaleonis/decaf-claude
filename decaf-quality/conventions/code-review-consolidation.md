# Code Review Consolidation Rules

This document defines how findings from multiple review agents are merged into a unified report.

## Severity Normalization

Each agent uses different terminology. Normalize to standard severities.

All personas report `Critical | High | Medium | Low` natively, with one exception: **knowledge-reviewer** uses `MUST | SHOULD | CONSIDER | LOW/MINOR`.

**Mapping Rules:**
- `MUST`, `CRITICAL`, `Critical` → **Critical**
- `SHOULD`, `HIGH`, `High` → **High**
- `CONSIDER`, `MEDIUM`, `Medium` → **Medium**
- `LOW`, `MINOR`, `Low`, anything else → **Low**

## Confidence Anchors

All agents report confidence as one of five discrete behavioral anchors — never intermediate values:

| Anchor | Meaning |
|--------|---------|
| **100** | Certain — verifiable from the code/diff alone: compile/type error, definitive logic bug, or a **quotable fact** (a convention or sibling-consistency violation, a doc-vs-code contradiction, a dead or self-contradicting contract, an identifier/comment mismatch). Impact is irrelevant to this anchor — a low-impact finding whose *claim* is quotable is anchor 100, Low severity. |
| **75** | Confident — a concrete observable consequence can be named that a user, caller, or maintainer hits in normal usage |
| **50** | Real but **its existence or impact depends on conditions outside the diff** — cannot be confirmed as a defect from the code alone (e.g. "works today only because the one caller validates first"). This is *uncertainty*, not smallness — a verified-but-minor fact is anchor 100 Low, not 50. |
| **25** | Speculative — might be real, could not be verified from the diff and surrounding code (agents suppress; never reported) |
| **0** | False positive on closer inspection (agents suppress; never reported) |

Severity and confidence are **orthogonal axes**: a Low finding can be anchor 100 (airtight evidence, small impact); a Critical finding can be anchor 50 (serious if real, not fully verifiable from the diff). The most common scoring error is collapsing a *verifiable but low-impact* finding to anchor 50 because it "feels minor" — score the **certainty of the claim** in the anchor and express impact through **severity**, never by deflating the anchor.

## Deduplication Rules

Two findings are considered **duplicates** if ALL of the following match:

1. **Same file path** (exact match, case-insensitive on Windows)
2. **Line numbers within 3 lines** of each other (`abs(line1 - line2) <= 3`)
3. **Similar category** (exact match or semantic equivalence):
   - `null-safety` = `nullable` = `null-check`
   - `unused-code` = `dead-code` = `unreachable`
   - `security` = `vulnerability`
   - `error-handling` = `exception-handling`

### Merging Duplicates

When duplicates are found:

1. **Combine descriptions**: Include unique insights from each agent
2. **Keep the highest severity** (see Severity Merging below)
3. **List all finders**: Record which agents found the issue and what severity each assigned
4. **Apply agreement promotion** to confidence (see Confidence Merging below) — do NOT average

## Severity Merging

When multiple agents report the same issue with different severities, **the highest severity wins**, regardless of how many agents assigned a lower one.

- Example: 2 agents say "Low", 1 says "Critical" → Report as **Critical**, noting the dissent
- Example: 1 says "High", 1 says "Medium" → Report as **High**
- Rationale: better to over-report than miss a real issue. A specialist's Critical must never be buried by generalists rating the same issue out of their domain.

### Recording Dissent

Always note disagreements in the "Found by" field:
```
**Found by** | security-reviewer (Critical), quick-reviewer (Low - dissenting), design-reviewer (Low - dissenting)
```

## Confidence Merging — Agreement Promotion

Agreement between independent reviewers is evidence that a finding is real. When merging duplicates:

1. Start from the **highest anchor** any finder assigned
2. **Promote one anchor step** (50 → 75, 75 → 100, 100 stays 100) when 2+ agents flagged the same finding — **unless the only finders are the two generalists**
3. Never average, and never demote on disagreement

**Generalist exemption:** `quick-reviewer` and `broad-reviewer` deliberately overlap in scope. Agreement between *only* those two is not independent corroboration and does **not** promote. Promotion requires at least one specialist among the finders (knowledge, design, security, test, or spec-compliance reviewer), or two specialists agreeing.

## Confidence Gate

Applied **after** deduplication and agreement promotion (so anchor-50 findings get their chance to be promoted first):

- **Suppress** findings below anchor 75.
- **Critical exception:** Critical findings at anchor 50 survive the gate — critical-but-uncertain issues must not be silently dropped. Mark them clearly as anchor 50 in the report.
- **Deterministic-claim safety net:** before suppressing, re-anchor to **100** any finding whose claim is a *quotable fact checkable from the code/diff alone* — a convention or sibling-consistency violation, a doc-vs-code contradiction, a dead or self-contradicting contract, an identifier/comment mismatch, or a value laundered through a cast or null-forgiving (`!`) operator. The finder under-scored its certainty (see Confidence Anchors). These are **not suppressed**; if Low/Medium they route to **Minor Findings — Consistency** (see Soft Buckets). The bar is that the *claim* is verifiable by inspection, not that the issue is severe — a genuinely conditional or speculative item (true anchor 50/25) is still suppressed.
- Record the number of suppressed findings (by anchor) in the report's Considered But Not Flagged section so the drop is visible.

## Pre-existing Separation

A finding is **pre-existing** when the issue lives in code this changeset did not add or modify — visible in diff context lines, surrounding code, or files touched only incidentally.

- Agents mark these (`"pre_existing": true` in JSON output; a **Pre-existing** field in markdown formats) and report them only when Critical/High or directly relevant to the change
- Consolidation routes pre-existing findings to a separate **Pre-existing Issues** report section
- Pre-existing findings do **not** count toward the verdict or the Summary table — the review judges the change, not the codebase
- The confidence gate and dedup rules apply to pre-existing findings the same as to new ones

## Soft Buckets → Minor Findings (reported, non-verdict-blocking)

Minor findings are **verified, real, and reported** — they just don't block the verdict or crowd the primary list. They are NOT a graveyard: each is a concrete, actionable one-liner a reviewer fixes in seconds, which is exactly the low-cost-to-triage value a primary-only report throws away. Three buckets feed the report's **Minor Findings** section.

After the confidence gate, route a surviving finding to a minor bucket as follows:

- **Consistency** — the claim is a quotable fact (a convention/consistency violation, doc-vs-code contradiction, dead contract, identifier/comment mismatch; including those recovered by the gate's deterministic-claim safety net) and severity is Low/Medium. **Corroboration is irrelevant here** — the claim is self-verifying, so multi-finder consistency findings land here too.
- **Testing Gaps** — a **single** test-reviewer raised a Medium/Low *coverage* gap (a missing edge-case/branch test, ambient-data dependence) where the test itself is not broken.
- **Residual Risks** — a **single** generalist raised a Medium/Low structure/style observation (categories `naming`, `design`, cosmetic `unused-code`) with no nameable consequence.

Minor findings render as compact one-line entries (`file:line — title (agent)`) under their bucket, are **counted in the Summary (Minor row) and reported**, but do not drive the verdict. They are not sent to the validation wave (the Consistency claim is self-verifying; the others are low-stakes), so they add no validator cost.

**Never route to a minor bucket** a defect with a nameable consequence — bugs, leaks, races, security findings, error-handling gaps, silent test failures — regardless of severity; those stay primary. In particular, **a test that passes when it should fail is a defect, not a coverage gap**: a tautological assertion, an assertion of a framework/Moq default value, or a test that cannot detect the regression it names is a **false-positive test**. Report it at its severity — Medium or higher → primary finding; Low → **Minor Findings — Consistency** (it is a quotable fact). Testing Gaps is only for *absent* coverage, never for a *broken* test.

## Category Taxonomy

Standardize categories across agents:

| Standard Category | Aliases |
|-------------------|---------|
| `null-safety` | nullable, null-check, null-reference, NRE |
| `unused-code` | dead-code, unreachable-code, unused-variable |
| `security` | vulnerability, injection, authentication, authorization, THREAT_ATTACK_SURFACE, THREAT_CRYPTO, THREAT_DEPENDENCY, THREAT_TEST_COVERAGE, THREAT_CONFIG, THREAT_AUDIT, THREAT_PRIVILEGE, THREAT_COMPLIANCE, THREAT_RESOURCE_BOUNDS |
| `error-handling` | exception-handling, try-catch, error-propagation |
| `performance` | efficiency, optimization, memory, allocation |
| `design` | architecture, pattern, coupling, cohesion, SOLID |
| `naming` | convention, identifier, readability |
| `type-safety` | casting, type-conversion, generics |
| `async` | async-await, task, concurrency, threading |
| `resource-management` | disposal, IDisposable, using-statement |
| `spec-compliance` | SPEC_UNIMPLEMENTED, SPEC_PARTIAL, SPEC_DEVIATION, SPEC_UNCOVERED, SPEC_EDGE_CASE |
| `data-migration` | MIG_DATA_LOSS, MIG_IRREVERSIBLE, MIG_BACKFILL, MIG_DEPLOY_WINDOW, MIG_LOCKING, MIG_DRIFT, MIG_VERIFICATION, migration, schema |
| `prior-feedback` | PRIOR_UNADDRESSED, PRIOR_PARTIAL, PRIOR_REGRESSION |
| `other` | anything that doesn't fit above |

## Consolidation Algorithm

```
1. Collect all findings from all agents
2. For each finding:
   a. Normalize severity using mapping table
   b. Normalize category using taxonomy
3. Group findings by (file, approximate_line, category)
4. For each group with multiple findings:
   a. Keep the highest severity; record all finders with their original severities
   b. Apply agreement promotion to confidence (highest anchor, +1 step if
      promotion applies; generalist-only agreement does not promote)
   c. Merge descriptions (deduplicate similar text)
   d. pre_existing: true only if ALL finders marked it pre-existing
5. Apply the confidence gate (suppress < 75; Critical at 50 survives; the
   deterministic-claim safety net re-anchors quotable-fact findings to 100
   so they are kept, not suppressed)
6. Separate pre-existing findings into the Pre-existing Issues section
   (informational; excluded from verdict and Summary counts)
7. Route minor findings to their buckets (Consistency / Testing Gaps /
   Residual Risks; Low/Medium, reported and counted in the Summary Minor
   row but not verdict-driving). A false-positive test is a defect, not a
   Testing Gap — Medium+ stays primary, Low goes to Consistency
8. Run the validation wave (skill Step 5.6, skipped in low mode). Validate
   where marginal value is highest — every Critical, every single-finder
   primary, and any finding carrying dissenting severities — but **skip** a
   dedicated validator for a non-Critical primary already corroborated by 2+
   independent finders (≥1 specialist) at anchor 100; its corroboration is
   the verification. Budget-capped at 15; minor and pre-existing findings are
   not validated. Refuted findings drop to Considered But Not Flagged with the
   validator's reason; confirmed corrections (line/file/pre_existing) are applied
9. Sort the remaining (primary) findings:
   a. Primary: Severity (Critical > High > Medium > Low)
   b. Secondary: Confidence anchor (descending)
   c. Tertiary: File path (alphabetical), then line number (ascending)
10. Generate unified report; verdict and Summary table reflect primary
    findings only
```

## Edge Cases

### No Findings
If all agents return empty results:
- Report verdict as **APPROVED**
- Include note: "No issues found by any reviewer"

### Agent Failure
If an agent fails or times out:
- Continue with results from successful agents
- Note the failure in the report header
- Example: `**Reviewers**: quick-reviewer, security-reviewer (failed), design-reviewer`

### Conflicting Fixes
If agents suggest different fixes for the same issue:
- Include both suggestions
- Label each with the source agent
- Let the developer choose
