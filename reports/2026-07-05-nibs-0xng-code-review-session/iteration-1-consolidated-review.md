# Code Review

**Mode**: mid (explicit) | **Reviewers**: quick, broad, knowledge, consistency, typescript, test | **Date**: 2026-07-05
**Source**: local uncommitted changes (nib 0xng — shared clipboard helper extraction + copy-ID button)
**Scope**: 5 files changed, +107/-19 lines (3 modified: +37/-14; 2 new: clipboard.ts 19, clipboard.test.ts 51)
**Spec**: none found
**Validation**: 1 confirmed, 0 refuted, 0 uncertain

## Agent Selection Rationale

- **quick-reviewer** (always — review floor) · ran mid-tier (sonnet)
- **broad-reviewer** (always — review floor) · ran mid-tier (sonnet)
- **knowledge-reviewer** — substantive change (new shared helper + a11y control rework); judgment agent · ran session model (opus)
- **consistency-reviewer** — sibling code exists to compare against (other `lib/*.ts` helpers, other `<Button>` call sites, sibling `*.test.ts`) · ran mid-tier (sonnet)
- **typescript-reviewer** — hard gate: `.ts` / `.svelte` TypeScript files in changeset · ran mid-tier (sonnet)
- **test-reviewer** — hard gate: test files (`clipboard.test.ts`, `DetailPanel.test.ts`) in changeset · ran mid-tier (sonnet)
- **design-reviewer**: skipped — the new helper is a single pure function; no contract/boundary/concurrency design surface beyond the trivial always-resolves contract (covered by typescript-reviewer + knowledge-reviewer)
- **security-reviewer**: skipped — clipboard write of a non-secret nib ID; no auth/crypto/network/secrets/serialization surface
- **adversarial-reviewer**: skipped — under 50 non-test executable lines (~35), low-risk UI helper, not a high-risk domain
- **spec-compliance-reviewer**: skipped — no spec available (hard gate)

**Mode selection**: explicit (`mid` passed by caller). **Tiering** (mid policy): judgment agent (knowledge) on the session model; volume agents (quick, broad, consistency, typescript, test) and the validator on mid-tier (sonnet).

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 0 |
| 🟠 High | 0 |
| 🟡 Medium | 1 |
| 🟢 Low | 0 |
| 🔵 Minor | 6 |

Critical/High/Medium/Low are **primary** findings and drive the verdict. **Minor** counts reported-but-non-blocking findings (Consistency / Testing Gaps / Residual Risks).

**Verdict**: ✅ APPROVED

---

## Findings

### #1 🟡 Medium: Copy-ID button's accessible name discards its visible label (WCAG 2.5.3 "Label in Name")

| | |
|---|---|
| **File** | `web/src/lib/components/DetailPanel.svelte:256-266` |
| **Category** | accessibility |
| **Confidence** | 75 |
| **Found by** | quick-reviewer (Medium), broad-reviewer (Medium) — validator: **confirmed** |

**Issue:** The new copy-ID `Button` renders the nib ID itself as its only visible text (`{nibId}`, e.g. `nibs-abc1`) but sets a static `aria-label="Copy nib ID"`. The shared `Button` component spreads unrecognized props (including `aria-label`) straight onto the native `<button>` via `{...restProps}` (`ui/button/button.svelte`), and an explicit `aria-label` short-circuits the accessible-name computation — so the programmatic name becomes exactly "Copy nib ID", containing none of the visible ID text. This is the pattern WCAG 2.5.3 (Label in Name) warns against.

**Concrete consequence:** A screen-reader user tabbing the header hears "Copy nib ID, button" with no indication of *which* nib is open (context sighted users get for free from the rendered text). A speech-control user (Dragon / Voice Access) who says the visible text "nibs-abc1" to activate the control fails to match, because the matched accessible name is "Copy nib ID". No test pins the current `aria-label` string, so the fix breaks nothing.

**Fix:** Fold the visible text into the accessible name so it's a superset of the label:
```svelte
aria-label={`Copy nib ID ${nibId}`}
```
(This also naturally resolves the identical `title`/`aria-label` consistency nit below.)

---

## Minor Findings

### Consistency

- `web/src/lib/components/DetailPanel.svelte:259` — Copy-ID button adds `cursor-pointer`, but none of the six other `<Button>` call sites do (`DetailPanel.svelte:328,428,439`, `EditorModal.svelte:368,487`, `SettingsSheet.svelte:152`) and there's no global button cursor reset in `app.css`; this button gets a different hover affordance than every sibling (consistency-reviewer, anchor 100).
- `web/src/lib/components/DetailPanel.svelte:261` — `title` and `aria-label` are the identical string `"Copy nib ID"`; sibling paired buttons (`detail-close`, `EditorModal` close) use a terse `title` plus a distinct, more descriptive `aria-label`. Subsumed by fixing #1 (consistency-reviewer, anchor 75).
- `web/src/lib/clipboard.ts:9-10` — Docstring's closing sentence ("Behaviour matches the \"Copy ID\" action originally inlined in RowContextMenu.") is an evolution-history anchor, not a live constraint; it will become a stale/false parity claim once RowContextMenu diverges. The lines above already fully specify the contract (knowledge-reviewer, anchor 75).

### Testing Gaps

- `web/src/lib/components/DetailPanel.test.ts` — Only the success path is tested at the component level; no click-through test asserts the error branch (`writeText` rejects → `mockToastError`). Rejection logic *is* covered at the unit level in `clipboard.test.ts`; only the DetailPanel wiring to the error branch is unverified (test-reviewer, anchor 50).
- `web/src/lib/components/DetailPanel.test.ts:256-273` — Success-path click test asserts `mockToastSuccess` fired but omits the symmetric `expect(mockToastError).not.toHaveBeenCalled()` that the `clipboard.test.ts` unit tests include; a double-toast bug wouldn't be caught here (test-reviewer, anchor 50).

### Residual Risks

- `web/src/lib/components/DetailPanel.svelte:259` — The `-ml-2.5` negative margin exactly cancels the ghost button's `size="sm"` `px-2.5` padding to align the ID flush-left like the old `<span>`; the coupling to the button's size token is uncommented, so changing `size` silently misaligns the ID. Consider a brief inline comment (knowledge-reviewer, anchor 75).

---

## Agent Summary

| Agent | Issues Found | Unique Issues |
|-------|:------------:|:-------------:|
| quick-reviewer | 1 | 0 |
| broad-reviewer | 1 | 0 |
| knowledge-reviewer | 2 | 2 |
| consistency-reviewer | 2 | 2 |
| test-reviewer | 2 | 2 |
| typescript-reviewer | 0 | 0 |
| **Total** | **7** | |

Notes:
- **Issues Found**: consolidated findings (primary + minor) attributed to the agent, shared findings counted for each finder.
- **Unique Issues**: findings reported only by that agent.
- typescript-reviewer's two submissions were Low/anchor-50 defensive-coding suggestions, both suppressed by the confidence gate (see below) — it contributed no surviving finding.

---

## Specialist Notes

### Considered But Not Flagged (all agents)

**Suppressed by the confidence gate (anchor < 75, not Critical):**
- `clipboard.ts:12-19` — **try/catch changes failure semantics** vs. the original `.then(onFulfilled, onRejected)`: a throw from the success `toast.success(...)` now falls into `catch` and shows a misleading error toast (broad-reviewer, Low, anchor 50). `svelte-sonner` toasts are not expected to throw; cosmetic-only.
- `clipboard.ts:16` / call sites — **swallowed rejection reason / no `console.error`** and **floating promise without `void` marker** at both call sites (typescript-reviewer, Low, anchor 50). Dissented by quick, broad, and knowledge: the swallow is identical to the pre-existing inlined RowContextMenu behavior (not a regression), and the fire-and-forget is intentional per the documented always-resolves contract.
- `DetailPanel.test.ts` / `clipboard.test.ts` — **`navigator.clipboard` stubbed via `Object.defineProperty` with no `afterEach` restore** (test-reviewer, Medium, anchor 50). Currently harmless: `vitest.config.ts` uses the default `isolate: true`, so each test *file* gets a fresh jsdom `navigator`, and no later test in either file reads the ambient value. Latent hazard if isolation is ever disabled; the same stub-without-restore pattern already pre-exists (untouched) at `RowContextMenu.test.ts:507-524`. Worth a shared `stubClipboard`/`restoreClipboard` helper eventually, but not blocking.

**Verified correct (no finding):**
- **Insecure-context safety** — `navigator.clipboard` being `undefined` throws a synchronous `TypeError` while evaluating the `await` operand, inside the `try`, so the `catch` handles it exactly like a rejection. Confirmed by quick and typescript reviewers.
- **Keyboard accessibility** — the shared `Button` renders a real native `<button>` (non-`href` branch), so Tab/Enter/Space work without any extra keydown handler; the "keyboard-accessible" claim holds.
- **Extraction completeness** — grep of `web/src` confirms `navigator.clipboard` now appears only in `clipboard.ts`; no un-migrated inline duplicate remains, and the removed `.detail-nib-id` CSS rule has no remaining references.
- **Helper conventions** — `clipboard.ts` matches sibling `lib/*.ts` helpers (flat layout, named `export function`, JSDoc block, paired `*.test.ts`).
- **Test non-vacuity** — `$lib/clipboard` is *not* mocked in `DetailPanel.test.ts`, so the real `copyToClipboard` runs on click; the `expect(writeText).toHaveBeenCalledWith("nibs-abc1")` assertion would fail if the button did nothing. `clipboard.test.ts` asserts exact call arguments and both positive and negative toast expectations — genuine regression tests, not tautologies.
- **Toast template injection** — `text` is an internal nib ID and `svelte-sonner` renders toast content as text, not HTML; no boundary-trust concern.

## Session Metrics (--report)

**Wave**: 6 reviewers dispatched in parallel (synchronous), then 1 validator. Pre-flight gates ran once before the wave.

| Agent | Kind | Model tier | Tokens | Tool calls | Duration | Findings submitted |
|-------|------|-----------|-------:|-----------:|---------:|-------------------:|
| quick-reviewer | reviewer | mid (sonnet) | 107,876 | 13 | 172,886 ms | 1 |
| broad-reviewer | reviewer | mid (sonnet) | 82,408 | 17 | 203,428 ms | 3 |
| knowledge-reviewer | reviewer | session (opus) | 68,982 | 7 | 133,445 ms | 2 |
| consistency-reviewer | reviewer | mid (sonnet) | 83,495 | 27 | 157,240 ms | 2 |
| typescript-reviewer | reviewer | mid (sonnet) | 64,252 | 13 | 156,052 ms | 2 |
| test-reviewer | reviewer | mid (sonnet) | 102,038 | 11 | 240,625 ms | 3 |
| finding-validator (#1) | validator | mid (sonnet) | 48,557 | 5 | 41,618 ms | — |

**Pre-flight gates**: test = PASS (`vitest run` on `clipboard.test.ts` + `DetailPanel.test.ts`, 67 tests passed); lint = none (web project has no ESLint/Prettier config; golangci-lint covers Go only); build = not run.

**Anomalies**: none. All 6 reviewers and the 1 validator returned reports as their final message. Validator confirmed the sole primary finding; 0 refuted, 0 uncertain.
