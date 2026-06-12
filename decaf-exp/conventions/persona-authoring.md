# Persona Authoring Guide

How to write a reviewer agent ("persona") for decaf-exp. Follow this anatomy exactly — uniform structure keeps personas predictable for authors, dispatchable by the orchestrator, and compatible with consolidation.

## File and frontmatter

One Markdown file per persona under `agents/`:

```yaml
---
name: <kebab-case-name>
description: <What it hunts, 1-2 sentences>. Dispatch — <compact gate clause>.
model: inherit
color: <color not used by another agent>
---
```

Frontmatter rules:

- **`description` carries the dispatch gate** as a trailing `Dispatch — ...` clause. The orchestrator selects agents from descriptions without reading files; the gate must be visible there. Mark hard gates explicitly: `Dispatch (hard gate) — only when <domain> is present in the changeset; never spawned otherwise, in any mode.`
- **`model` is always `inherit`.** Models are chosen at dispatch time by the skill's model policy (Step 2d). Never pin a model version in an agent — model-landscape changes must be a one-place edit in the skill.

## Required sections, in order

1. **Identity paragraph(s)** — who the persona is and its mental model, 1–2 paragraphs. State the attack strategy ("you trace inputs through branches", "you think like an attacker"), not just the topic.

2. **`## Dispatch Gate`** — `**Spawn when:**` and `**Do not spawn when:**`. Negative gates matter as much as positive ones: tell the orchestrator not to spawn just because a file extension or filename matched ("judge from diff content"). For domain-absent-means-useless personas, write `**Hard gate:**` — these are enforced in *all* modes, including `max` (no test-reviewer without tests, no stack persona for another language). State the persona's lean for borderline cases (e.g., security: "when unsure, lean toward spawning").

3. **`## Scope Boundary`** — `**Your scope**:` one line, then `**Out of scope**:` as a list where **every entry names the owning persona** (see the Domain Ownership Matrix below). End with a one-line boundary rule when the line is subtle (e.g., security's "single code pattern → quick-reviewer; missing architectural control → you").

4. **`### In-Scope Categories`** — table of `UPPER_SNAKE` subcategories with what each catches. These become the `[SUBCATEGORY]` prefixes in findings.

5. **`## Review Method`** — the phases. Standard ingredients:
   - **Context discovery first**: batch-read CLAUDE.md and referenced docs in parallel.
   - **Model-extraction preamble** when the domain has system-level structure: build the reference frame *before* evaluating (design → system model; security → threat model; spec → requirement checklist). Every finding must trace back to a model element. Skip this only for pure line-level personas.
   - **Open verification questions**, never yes/no ("What happens to downstream consumers if this return type changes?" — not "Is this contract clear?"). Yes/no questions bias toward agreement.
   - **Brief dual-path sanity check for Critical findings**: forward (cause → consequence) and backward (consequence → required conditions); diverging paths downgrade to High. Keep it brief — the validation wave (skill Step 5.6) independently re-verifies every surviving finding; the persona's job is plausibility, not proof.
   - **Thinking economy** for high-volume personas: dense analysis over narration, no phase-transition output.

6. **Severity table — impact only.** Four levels (Critical/High/Medium/Low) with *domain-specific* examples per level. Severity never encodes certainty; that's the anchor's job.

7. **Confidence anchors** — restate the five anchors (0/25/50/75/100, defined canonically in `code-review-consolidation.md`) as **domain evidence tiers**: what does "verifiable from the code alone" (100) or "concrete nameable consequence" (75) mean *in this domain*? Include the standard gate text (report ≥50 only; 25/0 to Considered But Not Flagged; consolidation suppresses <75 unless Critical or corroborated; never inflate an anchor). Then state the persona's **domain bias** explicitly, calibrated by miss-cost:
   - *Lenient* (missed finding costs more than a false positive — e.g., security): report Critical findings at anchor 50; they survive the gate.
   - *Neutral* (default): standard gate behavior.
   - *Strict* (false positives are the classic noise — e.g., performance, style): anchor-50 findings are usually noise; suppress rather than report.

8. **`## Output Format`** — the JSON contract for consolidation:

   ```json
   [
     {
       "file": "path/to/file.ext",
       "line": 42,
       "severity": "Critical|High|Medium|Low",
       "category": "<standard category from the consolidation taxonomy>",
       "issue": "[SUBCATEGORY] Brief description",
       "fix": "Concrete, implementable suggestion",
       "confidence": 75,
       "pre_existing": false
     }
   ]
   ```

   Plus the standard field notes (confidence = one of the five anchors; `pre_existing` = true when the issue lives in code the changeset didn't touch), followed by a `## Considered But Not Flagged` markdown section — items examined and dismissed, with reasoning. This transparency section is mandatory: the orchestrator re-reviews dismissals (Step 5.5) and records gate-suppressed findings there.

9. **`<verification_checkpoint>`** — a STOP-before-output checklist: every finding in scope, no overlap with named neighboring personas, anchors valid (five values, ≥50), `[SUBCATEGORY]` prefixes present, category maps to the taxonomy, fixes actionable, sanity check done for Criticals, Considered But Not Flagged present.

## Domain Ownership Matrix

The canonical map of review domains to owners. Every persona's out-of-scope list must agree with this table.

| Domain | Owner |
|--------|-------|
| Line-level bugs (logic, null safety, resource leaks, concurrency patterns) | `quick-reviewer` |
| Pattern-level security (injection, secrets, auth bypass, SSRF, sensitive exposure) | `quick-reviewer` |
| Code quality (duplication, error handling) and documented-convention violations (CLAUDE.md or equivalent) | `quick-reviewer` |
| Sibling-consistency / unwritten-convention drift discovered by comparison: naming/vocabulary, canonical-helper usage, attribute symmetry, leftover scratch code, comment-code mismatches, duplicated literals | `consistency-reviewer` |
| Knowledge preservation: undocumented decisions, comprehension risks, temporal contamination | `knowledge-reviewer` |
| System-level design: API contracts, data models, boundaries, concurrency design, evolution, resilience | `design-reviewer` |
| Architectural security: threat modeling, missing controls (crypto, audit, config, dependency, privilege) | `security-reviewer` |
| Test quality and anti-patterns (test files only) | `test-reviewer` |
| Spec compliance: requirement mapping, deviations, scope creep | `spec-compliance-reviewer` |
| Emergent multi-step failure scenarios: assumption violations, composition failures, cascades, abuse cases | `adversarial-reviewer` |
| Performance cost at scale: query shape, hot paths, memory growth, pagination, algorithmic complexity | `performance-reviewer` |
| Migration mechanics and safety: drift, data loss, backfills, deploy window, locking, rollback | `data-migration-reviewer` |
| C#/.NET idiom misuse (async, disposal, EF tracking, LINQ, NRT, threading) | `dotnet-reviewer` |
| TypeScript/JavaScript idiom misuse (promises, type escapes, coercion, runtime boundaries, event loop) | `typescript-reviewer` |
| C/C++ idiom misuse (lifetimes, ownership, UB, exception safety, concurrency) | `cpp-reviewer` |
| Go idiom misuse (goroutines, errors, typed nil, channels, context, defer) | `go-reviewer` |
| Rust idiom misuse (panic paths, unsafe invariants, async hazards, locking) | `rust-reviewer` |
| Diff vs. existing PR feedback (unaddressed, partial, regressed) | `prior-feedback-reviewer` |
| Re-verification of consolidated findings | `finding-validator` (validation wave only — not a review persona) |
| Resolution of a single PR review thread | `pr-thread-resolver` (resolve-pr-feedback only — not a review persona) |

**Generalist exception:** `broad-reviewer` deliberately overlaps the whole matrix as a second opinion. It has no exclusive domain and no out-of-scope obligations toward the specialists; consolidation compensates (generalist-only agreement does not promote confidence).

Rules:

- **Adding a persona**: claim its domains in this table *first*. If a domain moves (e.g., a future pattern-security persona taking `SECURITY_PATTERN` from quick), carve it out of the previous owner's in-scope categories and update both agents' boundary lists in the same change.
- **Resolving overlap disputes**: the more specific persona owns the domain; the general one adds an out-of-scope entry pointing at it.

## Integration checklist — adding a persona to the plugin

- [ ] Agent file follows the anatomy above (all nine sections, in order)
- [ ] `Dispatch —` clause in the description matches the `## Dispatch Gate` section
- [ ] `model: inherit`; volume-vs-judgment classification decided and the agent listed under the matching tier in the skill's Step 2d
- [ ] Row added to the skill's Step 2b gate table
- [ ] Domain Ownership Matrix updated; neighboring personas' out-of-scope lists updated to name the new owner
- [ ] Consolidation conventions updated: severity-normalization row (if the persona uses non-standard severity terms) and category taxonomy (if it introduces new categories)
- [ ] Domain bias decided (lenient / neutral / strict) and stated in the anchors section
- [ ] Plugin `README.md` roster table updated
- [ ] Exercised once on a real diff before publishing
