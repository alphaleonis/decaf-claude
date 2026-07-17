# subagent agent-a75e87562018cb89d

<review_analysis>
Context: No CLAUDE.md at repo root or in src/Components/Forms. Only .editorconfig (formatting). RULE 1 skipped.

Change: `TryGetValidatableProperty` replaced one `GetProperty(name)` with two-pass lookup — `Public|Instance|DeclaredOnly`, then fallback `Public|Instance|FlattenHierarchy`. Fixes AmbiguousMatchException (#27095) for `new`-shadowed (hidden) members.

Knowledge extraction:
- Decision: pass 1 DeclaredOnly selects most-derived declaration → sidesteps AmbiguousMatchException thrown by unqualified GetProperty on shadowed members. Pass 2 handles genuinely inherited (non-shadowed) base properties where DeclaredOnly returns null.
- Existing comment ("DataAnnotations only validates public properties") does not mention the two-pass structure, the exception it avoids, or why FlattenHierarchy.
- Static dropped (original default included Static; new flags Instance-only). Intent IS captured by test `IgnoresStaticProperty` + the visible `BindingFlags.Instance`. Inferability gate FAILS → not flagged.

RULE 0 open questions:
- "What would a maintainer misunderstand seeing two near-identical GetProperty calls?" → That the split is cosmetic; they may collapse to one call, reintroducing AmbiguousMatchException. Nothing in code names the exception (no throw/catch). Reflection knowledge required.
- Gates: inferability PASSES (rationale — the AmbiguousMatchException avoidance — is invisible in code); not-recorded-elsewhere PASSES (commit holds change-history "why", but the durable invariant "keep the two passes separate" must live near code for a maintainer editing this method in isolation); durable-relevance PASSES (a wrong refactor reintroduces the exact fixed bug).
- Dual-path: forward = collapse → AmbiguousMatchException regression; backward = for permanence, tests would have to be absent. Tests exist, exception is loud/recoverable → downgrade MUST → SHOULD.

FlattenHierarchy subtlety folded into the same finding: for instance members `Public|Instance` already walks the hierarchy, so FlattenHierarchy's effect is near-nil (it primarily flattens statics) — a reader cannot tell if it is load-bearing. Undocumented rationale is the root cause.
</review_analysis>

## VERDICT: NEEDS_CHANGES

## Project Standards Applied
No project documentation found (no CLAUDE.md at repo root or under src/Components/Forms; only .editorconfig for formatting). Applying RULE 0 and RULE 2 only.

## Findings

### [LLM_COMPREHENSION_RISK SHOULD]: Two-pass reflection lookup has no rationale for the AmbiguousMatchException it silently sidesteps
- **RULE**: 0 (knowledge preservation)
- **Location**: src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:368-379 (`TryGetValidatableProperty`)
- **Issue**: The method now issues two nearly-identical `GetProperty` calls — `Public|Instance|DeclaredOnly`, then a null-fallback to `Public|Instance|FlattenHierarchy`. The only comment ("DataAnnotations only validates public properties, so that's all we'll look for") predates this change and explains none of the new structure. Invisible in the code: (a) an unqualified `GetProperty` throws `AmbiguousMatchException` when a derived type hides a base property with `new`, which is the entire reason `DeclaredOnly` runs first (it selects the most-derived declaration); (b) the fallback exists to find properties genuinely declared only on a base class, where pass 1 returns null; (c) why `FlattenHierarchy` specifically — for instance members `Public|Instance` already walks the hierarchy, so its effect here is subtle and its load-bearing-ness is unknowable from the code. No `throw`/`catch` names the exception anywhere, so the connection is not reconstructable without specialized reflection knowledge.
- **Failure Mode / Rationale**: A future maintainer reads two almost-duplicate calls, judges the split redundant, and collapses them back to a single `GetProperty` — reintroducing the exact AmbiguousMatchException regression (#27095) for hidden members. Or, unsure whether `FlattenHierarchy` matters, changes it and cannot reason about the effect. The consequence is a re-introduced (but recoverable, test-caught) bug — hence SHOULD, not MUST. The durable invariant "these two passes must stay separate to avoid AmbiguousMatchException on shadowed members" lives only in the author's head and the commit title, not where someone editing this method looks.
- **Suggested Fix**: Add a comment above line 370 stating the invariant, e.g.: "Hidden (`new`) properties make an unqualified GetProperty throw AmbiguousMatchException, so first look only at the most-derived declaration (DeclaredOnly). If the property is declared only on a base type, pass 1 returns null; fall back to a hierarchy-wide lookup." If `FlattenHierarchy` is load-bearing (vs. plain `Public|Instance`), state why in the same comment; if the author cannot justify it, note it as intentional-per-tests so the next reader does not treat it as cargo-cult.
- **Confidence**: 75 — the rationale is demonstrably absent from the code, and a concrete comprehension failure (collapse-to-one-call regression) is nameable; partial intent does live in test names and the commit title, which is why this is not 100.
- **Pre-existing**: no — the two-pass logic is introduced by this changeset.
- **Actionability Check**:
  - Fix specifies exact change: YES (concrete comment content given)
  - Fix requires no additional decisions: YES for the core two-pass rationale (reconstructable from tests/commit); the FlattenHierarchy clause is optional if unknown

## Reasoning
Applied RULE 0. Found the new two-pass reflection lookup encodes an AmbiguousMatchException-avoidance decision that is invisible in code and absent from any in-file comment. Verdict: NEEDS_CHANGES because collapsing the passes reintroduces the fixed bug; SHOULD (not MUST) since the regression is loud and test-caught.

## Considered But Not Flagged
- **Static-property exclusion**: Original default `GetProperty(name)` included `BindingFlags.Static`; new flags are Instance-only, so static public properties are no longer validated. NOT flagged — intent is captured by the added `IgnoresStaticProperty` test, and `BindingFlags.Instance` on the call makes the exclusion self-evident (fails the inferability gate for demanding a comment).
- **Existing "public properties" comment**: Not misleading after the change — it addresses public-vs-nonpublic, orthogonal to the new instance-vs-static and DeclaredOnly behavior. No comprehension risk on its own; the missing knowledge is the two-pass rationale (flagged above), not this line.
- **Potential residual AmbiguousMatchException** for a leaf type that inherits (without redeclaring) a property shadowed at an intermediate level — the fallback's `FlattenHierarchy` could match two declarations. This is a correctness/edge-case question owned by quick-reviewer/adversarial-reviewer, out of my scope; referenced here only as the concrete comprehension-failure a reader cannot resolve because the flag rationale is undocumented.
- **`_propertyInfoCache` null-caching comment and lock-free note**: Unchanged and still accurate; no knowledge loss.

### Probe Requests
None required — review completed from the working tree at HEAD (read-only).
