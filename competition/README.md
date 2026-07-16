# Competitive Analysis — Claude Code Code-Review Plugins & Skills

A survey of prominent, actively-maintained Claude Code plugins and skills focused on
**code review**, with the source of each (10 tools) cloned into its own subdirectory here
for reference. Compiled **2026-07-16**. Candidates were cross-checked against the major
"awesome Claude" collections (travisvn/awesome-claude-skills, awesomeclaude.ai) and the most
prominent general frameworks (obra/superpowers) in addition to search and "best of 2026"
roundups. **Token-cost comparison:** see [`COST.md`](./COST.md) — measured figures for ours
and Tag1, estimates for the rest, and the caveats.

> **On verification.** Star/fork counts, dates, licenses, authors, and commit SHAs below
> were pulled from the GitHub REST API and each repo's own files on 2026-07-16 — treat
> those as verified. Claims about *adoption*, *sentiment*, and *usage on specific
> projects* come from third-party listicles and vendor marketing and are labeled
> `[Unverified]` or `[Inference]` accordingly. "Popular by stars" is a proxy for
> attention, not proof of production use.

## Selection criteria

Candidates were filtered for: (1) a primary focus on code review (not general-purpose
mega-collections, except where a dedicated review skill could be extracted); (2) evidence
of prominence — GitHub stars, inclusion in "best plugins" roundups, or first-party/vendor
backing; (3) recent activity (pushed within the last few months); and (4) — where it could
be established — a credible tie to large or well-regarded projects.

## The field at a glance

| # | Subdir | Source | Type | Author | Stars¹ | License | Last push¹ |
|---|--------|--------|------|--------|-------:|---------|-----------|
| 1 | [`anthropic-code-review/`](./anthropic-code-review) | `anthropics/claude-code` › `plugins/code-review` | Slash command (multi-agent) | Anthropic (Boris Cherny) | 138,058² | — (repo) | 2026-07-15 |
| 2 | [`anthropic-pr-review-toolkit/`](./anthropic-pr-review-toolkit) | `anthropics/claude-code` › `plugins/pr-review-toolkit` | Agent bundle (6 agents) | Anthropic (Daisy) | 138,058² | MIT | 2026-07-15 |
| 3 | [`anthropic-security-guidance/`](./anthropic-security-guidance) | `anthropics/claude-code` › `plugins/security-guidance` | Hook-based security reviewer | Anthropic | 138,058² | — (repo) | 2026-07-15 |
| 4 | [`awesome-skills-code-review/`](./awesome-skills-code-review) | `awesome-skills/code-review-skill` | Skill (progressive-disclosure guidance) | awesome-skills | 1,415 | MIT | 2026-07-16 |
| 5 | [`coderabbit-claude-plugin/`](./coderabbit-claude-plugin) | `coderabbitai/claude-plugin` | Slash command → CodeRabbit CLI | CodeRabbit AI | 51³ | MIT | 2026-04-13 |
| 6 | [`tag1-comprehensive-review/`](./tag1-comprehensive-review) | `tag1consulting/claude-comprehensive-review` | Skill orchestrating 10+ agents | Tag1 Consulting | 6³ | MIT | 2026-07-16 |
| 7 | [`alirezarezvani-code-reviewer/`](./alirezarezvani-code-reviewer) | `alirezarezvani/claude-skills` › `engineering-team/skills/code-reviewer` | Skill + Python scripts | alirezarezvani | 22,693⁴ | MIT | 2026-07-16 |
| 8 | [`trailofbits-skills/`](./trailofbits-skills) | `trailofbits/skills` | Marketplace of ~40 security-audit plugins | Trail of Bits | 6,141 | CC-BY-SA-4.0 | 2026-07-15 |
| 9 | [`agamm-owasp-security/`](./agamm-owasp-security) | `agamm/claude-code-owasp` | Skill (OWASP security review) | agamm | 290 | MIT | 2026-06-28 |
| 10 | [`obra-superpowers-code-review/`](./obra-superpowers-code-review) | `obra/superpowers` › `requesting/receiving-code-review` | Review *methodology* (subagent dispatch + reception) | obra (Jesse Vincent) | 255,751⁵ | MIT | 2026-07-16 |

¹ GitHub REST API, 2026-07-16.
² Star count is for the parent monorepo `anthropics/claude-code`, which vends the plugin as a subtree; the same three plugins are also mirrored in `anthropics/claude-plugins-official` (**32,197 ⭐**, Apache-2.0).
³ Plugin-repo stars understate reach: CodeRabbit is a thin wrapper over a widely-used commercial product; Tag1's plugin is new (created 2026-03-30) but at **v1.12.2** with a 150-test suite.
⁴ Star count is for the 345-skill parent collection; only the `code-reviewer` skill subtree is vendored here.
⁵ Star count is for the whole superpowers framework (the most-starred entry here by a wide margin); only its two code-review skill subtrees are vendored.

Per-directory provenance (exact commit SHA + retrieval method) is recorded in each
subdir's `PROVENANCE.md`.

---

## 1. Anthropic — Code Review plugin (`/code-review`)

- **Source:** https://github.com/anthropics/claude-code/tree/main/plugins/code-review
- **Also on the official marketplace:** `/plugin install code-review@claude-plugins-official`
- **Mechanism:** a single slash command that fans out to a fleet of subagents.

**What it is.** The flagship, first-party PR reviewer that ships with Claude Code. Running
`/code-review` on a PR branch:

1. Uses a Haiku agent to skip PRs that don't need review (closed, draft, trivial/automated,
   or already commented on by Claude).
2. Collects the relevant `CLAUDE.md` guideline files.
3. Summarizes the diff (Sonnet).
4. Launches **4 parallel reviewers** — two Sonnet `CLAUDE.md`-compliance auditors, and two
   Opus bug/logic/security hunters scoped strictly to the diff.
5. Spawns a **validation subagent per finding** (Opus for bugs, Sonnet for `CLAUDE.md`)
   that adversarially re-verifies each issue.
6. Filters to issues scoring **≥ 80/100 confidence**, then either prints to the terminal or
   (with `--comment`) posts inline GitHub comments with full-SHA permalinks.

**Why it stands out.** The design is explicitly tuned for *high signal*: an anti-false-positive
checklist (ignore pre-existing issues, lint-catchable nits, pedantry) plus a
verify-every-finding pass. This is the same review pattern Anthropic documents using on its
own repos — the command file's link examples reference reviewing `anthropics/claude-code`
PRs directly.

**Popularity / provenance.** Bundled with Claude Code itself and a fixture of virtually every
"best Claude Code plugins (2026)" roundup, usually as the recommended first-pass reviewer.
`[Inference]` Given it ships in the CLI, its install base tracks Claude Code's overall
adoption — far beyond any community alternative. Authored by Boris Cherny (Anthropic).

**Usage:**
```bash
/code-review            # review current PR branch, print to terminal
/code-review --comment  # post inline review comments to the GitHub PR
```

---

## 2. Anthropic — PR Review Toolkit

- **Source:** https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit
- **Install:** `/plugin install pr-review-toolkit@claude-plugins-official`
- **License:** MIT · **Author:** Daisy (Anthropic)
- **Mechanism:** a bundle of **6 specialized review agents** that trigger automatically from natural-language intent (or on demand).

**The six agents:**

| Agent | Focus | Scoring |
|-------|-------|---------|
| `code-reviewer` | General bugs, style, `CLAUDE.md` compliance | issues 0–100 (91–100 = critical) |
| `code-simplifier` | Complexity/clarity reduction, behavior-preserving | qualitative |
| `comment-analyzer` | Comment accuracy & rot | confidence on accuracy |
| `pr-test-analyzer` | Test-coverage gaps (behavioral, not line) | gaps rated 1–10 |
| `silent-failure-hunter` | Swallowed errors, bad fallbacks | severity per issue |
| `type-design-analyzer` | Encapsulation / invariants of new types | 4 dimensions rated 1–10 |

**Why it stands out.** Where `/code-review` is one orchestrated command, this is a *toolbox*
of composable reviewers you invoke by asking (e.g. "check if the tests cover the edge cases"
→ `pr-test-analyzer`). It is the de-facto community building block: **Tag1's
comprehensive-review (#6) declares it a hard dependency** and reuses all five of its
non-simplifier agents rather than reimplementing them. The README notes the agents are
maintained in Anthropic's internal `claude-cli-internal` repo — i.e. dogfooded internally.
`[Inference]`

> Note: this toolkit is the one wired into *this* environment's agent roster
> (`pr-review-toolkit:code-reviewer`, `:silent-failure-hunter`, etc.).

**Usage (intent-driven):**
```
"Review my recent changes"                        → code-reviewer
"Check for silent failures in the API client"     → silent-failure-hunter
"Are the tests for this PR thorough?"             → pr-test-analyzer
"Review the UserAccount type design"              → type-design-analyzer
"Simplify this code"                              → code-simplifier
```

---

## 3. Anthropic — Security Guidance

- **Source:** https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance
- **Install:** `/plugin install security-guidance@claude-plugins-official` — **ships enabled by default** in Claude Code.
- **Mechanism:** three ambient **hooks**, not a command — security review runs continuously as you code.

**The three layers:**

1. **Pattern warnings** — regex reminders on `Edit`/`Write` for ~25 known-dangerous patterns
   (`yaml.load`, `pickle.load` on untrusted data, `torch.load(weights_only=False)`, raw
   `innerHTML`, hardcoded secrets…).
2. **LLM diff review** — on turn end, sends the diff to a fast model (Opus 4.7 default) and
   feeds high-severity findings back to Claude to address before you see the reply.
3. **Agentic commit review** — on `git commit`, an SDK-driven reviewer reads related files
   (`Read`/`Grep`/`Glob`) to trace cross-file data flow, catching multi-file issues pattern
   matching misses (IDOR, auth bypass, cross-file SSRF).

**Why included.** It's the security-specialist counterpart to `/code-review`, covers
OWASP-class web-vuln categories, supports org-specific policy files
(`claude-security-guidance.md`), and is configurable per-layer via env vars. Its README is
candid that it is "best-effort assistive… not a substitute for human review, SAST/DAST, or
pen-testing" — i.e. no over-claiming.

**Config highlights:** `SECURITY_GUIDANCE_DISABLE=1` (kill switch), `SECURITY_REVIEW_MODEL`,
`SG_DUAL_OR=on` (higher-recall dual-review), and a committed `.claude/claude-security-guidance.md`
for codebase-specific rules.

---

## 4. awesome-skills — Code Review Skill

- **Source:** https://github.com/awesome-skills/code-review-skill
- **1,415 ⭐ / 151 forks · MIT · pushed 2026-07-16 (active).** Bilingual (English/中文).
- **Mechanism:** a knowledge-heavy **skill** — not agents. ~21,000 lines of curated review
  guidance across **20+ languages/frameworks**, loaded via **progressive disclosure**.

**What it is.** The most-starred *dedicated* community code-review skill. The core `SKILL.md`
is only ~220 lines; language guides (React 19, Vue 3.5, Svelte 5, Angular 17+, TypeScript,
Java 17/21 + Spring Boot 3, Java 8 legacy, Django, FastAPI, Go, Rust, Kotlin, Swift, C/C++,
Zig, Qt, Ruby/Rails, PHP, C#/.NET…) and cross-cutting guides (security, performance,
architecture, N+1, XSS, SQLi, error-handling, async) load **only when the relevant code is
in scope**, keeping context lean.

**Method.** A four-phase process (Context → High-level → Line-by-line → Summary/Decision) and
a six-level severity vocabulary: `blocking · important · nit · suggestion · learning ·
praise`. Deliberately collaborative in tone ("questions over commands") and
automation-aware (separates human-review concerns from linter-catchable ones).

**Popularity / sentiment.** `[Unverified]` Cited in 2026 roundups as a leading structured
code-review skill; the star count (1.4k, growing, MIT) is the strongest signal. No specific
well-known-project usage is established. Ships a `pr-analyzer.py` complexity script plus a
review checklist and PR-comment template.

**Usage:**
```
Use code-review-skill to review this PR
Review this React component        # loads reference/react.md
Security review of this Go service # loads go.md + security-review-guide.md
```

---

## 5. CodeRabbit — Claude Code Plugin

- **Source:** https://github.com/coderabbitai/claude-plugin · **v1.1.0** · MIT · 51 ⭐ (plugin repo)
- **On the official marketplace:** `/plugin install coderabbit` · also packaged for [35+ coding agents](https://github.com/coderabbitai/skills).
- **Mechanism:** a thin `/coderabbit:review` command that shells out to the **CodeRabbit CLI**, which performs the actual review on CodeRabbit's platform.

**What it is.** The Claude Code front-end for CodeRabbit, an established commercial AI
code-review product. The plugin verifies CLI install/auth, runs the review, and presents
findings grouped by severity — so Claude can write code, CodeRabbit reviews it, and Claude
applies fixes in one loop.

**Why included.** Brand recognition and a fundamentally different architecture from the LLM-only
tools here: CodeRabbit advertises **40+ integrated static analyzers**, AST/codegraph
context, and reads your `CLAUDE.md`/coding guidelines. `[Unverified]` CodeRabbit markets
wide adoption across many engineering orgs; the low *plugin*-repo star count reflects that the
wrapper is new and most usage is via its GitHub/GitLab app and CLI rather than this repo.

**Prerequisites:** `curl -fsSL https://cli.coderabbit.ai/install.sh | sh` then
`coderabbit auth login` (free for use in any git repo, per vendor).

**Usage:**
```bash
/coderabbit:review                 # review all changes
/coderabbit:review uncommitted     # only uncommitted changes
/coderabbit:review --base main     # compare against main
```

---

## 6. Tag1 Consulting — Comprehensive Review

- **Source:** https://github.com/tag1consulting/claude-comprehensive-review · **v1.12.2** · MIT · 6 ⭐ (created 2026-03-30, very active)
- **Install:** `claude plugin marketplace add tag1consulting/claude-plugins` → `/plugins install comprehensive-review@tag1consulting`
- **Mechanism:** a Sonnet **orchestrator skill** coordinating **10+ agents + deterministic linters** across GitHub/GHE, GitLab, and Bitbucket.

**What it is.** The most feature-dense community entry. `/comprehensive-review` builds on
pr-review-toolkit (#2, a hard dependency) and layers on its own Opus agents —
`security-reviewer` (OWASP-class), `architecture-reviewer` (coupling/design), plus
`blind-hunter` / `edge-case-hunter` / `adversarial-general` (adapted from BMAD-METHOD) — then
**normalizes, confidence-filters, dedups, and severity-ranks** every finding into one report.
It also runs opportunistic external analyzers when present (Semgrep, TruffleHog, ESLint,
golangci-lint, Ruff, Checkov, hadolint, phpcs/phpstan, kube-linter, tflint) and an OSV.dev
CVE check on changed dependency manifests.

**Notable engineering.** Two-block output (summary vs. findings) with posting gated behind
explicit flags; a shared `GOVERNANCE.md` inlined into every agent (harm-prioritization,
verify-before-naming, non-destructive remediations, secret redaction); tiered
token-efficiency (auto `TIER=tiny`/`DOCS_ONLY`/`LOW_RISK_CONFIG` modes, `--quick`, symbol-context
enrichment); 19 per-language profiles; verify-before-suppress suppression rules; optional
claude-mem integration; and a **150-test bats suite**. Cost is documented (~$0.25 `--quick`,
~$0.50–1.25 full).

**Popularity / provenance.** Star count is low (new repo), but the author is a signal: **Tag1
Consulting is a well-known engineering firm and major Drupal contributor.** The plugin's
PHP/Drupal-specific tooling (phpcs Drupal standard, `.module`/`.install`/`.theme` handling)
is `[Inference]` evidence it was built for and exercised on Drupal-scale codebases. Actively
developed (v1.12.2; pushed 2026-07-16).

**Usage:**
```bash
/comprehensive-review                       # full local review, nothing posted
/comprehensive-review --quick               # ~60–80% cheaper, core agents only
/comprehensive-review --pr 42 --post-findings  # review someone else's PR, post inline
/comprehensive-review --security-only       # security + CVE scan on changed manifests
/comprehensive-review --depth deep          # Opus everywhere + CVE reachability triage
```

---

## 7. alirezarezvani — Code Reviewer skill (from `claude-skills`)

- **Source:** https://github.com/alirezarezvani/claude-skills › `engineering-team/skills/code-reviewer`
- **Parent collection:** 22,693 ⭐ / 3,158 forks · MIT · pushed 2026-07-16. Only the `code-reviewer` subtree is vendored here.
- **Mechanism:** a **skill + 3 stdlib-only Python scripts** — a deterministic-checker approach rather than pure LLM prompting.

**What it is.** A code-review skill extracted from one of the most-starred Claude Code skill
collections on GitHub (which also targets Codex, Gemini CLI, Cursor, and 9 more agents). It
ships:

- `scripts/pr_analyzer.py` — complexity score (1–10), risk tier, prioritized review order,
  commit-message validation; flags hardcoded secrets, SQLi, debug statements, analyzer
  suppressions, `any`/`dynamic` overuse, `async void`, blocking-on-`Task`, etc.
- `scripts/code_quality_checker.py` — quality score (0–100) + letter grade; detects long
  methods, god classes, deep nesting, swallowed exceptions, undisposed `IDisposable`,
  per-language smell packs (C#, Java, C banned-function checks).
- `scripts/review_report_generator.py` — combines the above into an approve / request-changes /
  block verdict (markdown or JSON).

Review rules are split so each review loads exactly two files (`rules/universal.md` + one of
14 `languages/*.md`). Ships labeled smell/clean sample fixtures and `expected_outputs/*.json`
as a regression harness.

**Popularity / sentiment.** `[Unverified]` The parent repo's 22.7k stars make it highly
visible, but that's a collection-level signal — it reflects the whole 345-skill library, not
this one skill. No specific well-known-project usage is established. The stdlib-only,
testable-scripts design is its most distinctive trait versus the prompt-only skills above.

**Usage:**
```bash
python scripts/pr_analyzer.py . --base main --head HEAD
python scripts/code_quality_checker.py /path/to/code --language csharp --json
python scripts/review_report_generator.py /path/to/repo --format markdown --output review.md
```

---

## 8. Trail of Bits — Skills Marketplace

- **Source:** https://github.com/trailofbits/skills · **6,141 ⭐ / 541 forks · CC-BY-SA-4.0 · pushed 2026-07-15 (active)**
- **Install:** `/plugin marketplace add trailofbits/skills` → `/plugin menu`
- **Mechanism:** a **marketplace of ~40 focused plugins** (skills + agents + commands + hooks) for security research, vulnerability detection, and audit workflows.

**What it is.** Not a single reviewer but the security-audit toolkit from **Trail of Bits**,
one of the best-known independent security-audit firms. It's the strongest "provably used on
well-regarded projects" entry in this survey: the README maintains a **Trophy Case** of real
bugs found with the skills — e.g. a [timing side-channel in ML-DSA signing in
`RustCrypto/signatures`](https://github.com/RustCrypto/signatures/pull/1144). Also loadable by
Codex via Claude-marketplace compatibility.

**Most review-relevant plugins:**

| Plugin | What it does |
|--------|--------------|
| `differential-review` | Security-focused review of a diff/PR/commit: risk-first triage, git-blame regression detection, blast-radius (caller counting), test-gap analysis, adversarial attacker-model phase, markdown report with PoCs |
| `c-review` | C/C++ security review with clustered parallel workers, SARIF output |
| `rust-review` | Rust review across the safe/unsafe boundary, memory safety, concurrency, panic-DoS, FFI, async |
| `static-analysis` | CodeQL + Semgrep + SARIF parsing toolkit |
| `variant-analysis` | Find similar vulnerabilities across a codebase from a known pattern |
| `insecure-defaults` | Detect fail-open patterns, hardcoded creds, insecure default configs |
| `fp-check` | Systematic false-positive verification with mandatory gate reviews |
| `second-opinion` | Run reviews via *external* LLM CLIs (Codex, Gemini) on your changes for a cross-model check |
| `supply-chain-risk-auditor` | Audit dependency supply-chain threat landscape |
| `spec-to-code-compliance` | Specification-to-code compliance checking (blockchain audits) |

**Why it stands out.** This is professional-grade *security-audit* tooling, not general PR
review — deep, methodology-driven skills authored to the firm's house standards (every
security SKILL.md must include "When NOT to use" and "Rationalizations to Reject" sections).
`differential-review` is the closest analogue to a PR reviewer, and its adversarial /
blast-radius / regression-detection phases are more rigorous than most. The high star count
plus the firm's reputation make it a benchmark for security review depth.

**Usage (differential-review):**
```
Review the security implications of this PR:
git diff main..feature/auth-changes
```

---

## 9. agamm — OWASP Security Skill

- **Source:** https://github.com/agamm/claude-code-owasp · **290 ⭐ / 25 forks · MIT · pushed 2026-06-28**
- **Install:** `npx degit agamm/claude-code-owasp/.claude/skills/owasp-security ~/.claude/skills/owasp-security`
- **Mechanism:** a single progressive-disclosure **skill** — an always-loaded `SKILL.md` core plus on-demand `reference/` files.

**What it is.** A focused, standards-anchored security-review skill. The core carries the
**OWASP Top 10:2025** table, security code-review checklists (input handling, auth, access
control, data protection, error handling), and safe/unsafe code patterns; on-demand
references add language-specific security quirks for **20+ languages** and a deep-dive on every
covered standard. Notably current on AI-era risk: it also covers the **OWASP Top 10 for LLM
Applications (2025)** and **OWASP Agentic AI Security (2026, ASI01–ASI10)** plus **ASVS 5.0** —
relevant when reviewing chatbots, RAG, and tool-calling agent code.

**Why included.** It fills the "standards-checklist" niche: where security-guidance (#3) is
ambient and Trail of Bits (#8) is deep audit tooling, this is a lightweight, self-activating
reviewer keyed to a recognized external standard, and one of the few that explicitly addresses
LLM/agentic-app security categories. Decent traction (290 ⭐) for a single-purpose skill.

**Usage:**
```
"Review this code for security issues"          # auto-activates the skill
"Check this AI agent for OWASP agentic risks"
"What are the security risks in this Python code?"
```

---

## 10. obra — Superpowers (code-review skills)

- **Source:** https://github.com/obra/superpowers › `skills/requesting-code-review` + `skills/receiving-code-review`
- **Parent framework:** **255,751 ⭐ / 22,858 forks · MIT · pushed 2026-07-16** — by Jesse Vincent (obra). The single most-starred entry in this survey; only its two review skills are vendored here (plus the repo README).
- **Mechanism:** a **methodology**, not a scanner — two skills that structure *how* review happens inside the "subagent-driven development" workflow.

**What it is.** Superpowers is a broad agentic software-development methodology (brainstorming,
plans, TDD, subagent dispatch, verification). Its code-review contribution is two paired skills:

- **`requesting-code-review`** — after each task / before merge, dispatch a **fresh
  `general-purpose` subagent** given *precisely crafted context* (a description, the
  requirements, and a `BASE_SHA..HEAD_SHA` range) rather than your session history. The
  bundled `code-reviewer.md` prompt template casts the subagent as a Senior Code Reviewer and
  fixes the output shape: **Strengths → Critical / Important / Minor issues (each with
  file:line, what, why, how) → Recommendations → Ready-to-merge verdict**, with an explicit
  read-only-checkout constraint. "Review early, review often."
- **`receiving-code-review`** — a discipline for *acting on* feedback: verify against the
  codebase before implementing, no performative agreement ("You're absolutely right!" is
  explicitly forbidden), push back with technical reasoning when the reviewer is wrong, apply
  a YAGNI check to "implement it properly" suggestions, and fix one item at a time with a test
  each.

**Why it stands out.** It's the *process* archetype, complementary to the scanners above: a
disposable-context reviewer subagent (keeps the main context clean; gives genuine "fresh
eyes") plus a rigor discipline for feedback. Its influence is visible elsewhere — Trail of
Bits' `AGENTS.md` cites superpowers as a reference for workflow patterns. `[Inference]` The
enormous star count reflects the whole framework's viral popularity, not the review skills
specifically, but those skills ship as a first-class part of it.

**Usage (conceptual — invoked by the workflow, not a slash command):**
```
BASE_SHA=$(git rev-parse origin/main); HEAD_SHA=$(git rev-parse HEAD)
# dispatch general-purpose subagent with code-reviewer.md template
#   → returns Strengths / Critical / Important / Minor / Assessment
```

---

## Honorable mentions (surveyed, not cloned)

| Repo | Stars¹ | Why not cloned |
|------|-------:|----------------|
| [`getsentry/skills`](https://github.com/getsentry/skills) | 864 | **Sentry's own production skills** (provably used by the Sentry team); includes a well-regarded `security-review` skill, but it's a general team collection, not a standalone reviewer. |
| [`BehiSecc/VibeSec-Skill`](https://github.com/BehiSecc/VibeSec-Skill) | 1,083 | Popular secure-coding skill, but oriented to *writing* secure code more than *reviewing*; stale since 2026-02. |
| [`mhattingpete/claude-skills-marketplace`](https://github.com/mhattingpete/claude-skills-marketplace) | 647 | Software-engineering skills marketplace incl. `review-implementing`; not review-focused overall. |
| [`jeremylongshore/claude-code-plugins-plus-skills`](https://github.com/jeremylongshore/claude-code-plugins-plus-skills) | 2,519 | A 425-plugin / 2,810-skill *marketplace* (tonsofskills.com), not a focused reviewer. |
| [`travisvn/awesome-claude-skills`](https://github.com/travisvn/awesome-claude-skills) | 14,140 | The largest curated *index* of Claude skills — a discovery source used to build this survey, not a reviewer. |
| [`aidankinzett/claude-git-pr-skill`](https://github.com/aidankinzett/claude-git-pr-skill) | 41 | Focused GitHub PR-review skill (pending reviews + suggestions via `gh`), but small and **stale since 2025-12**. |
| [`ComposioHQ/awesome-claude-plugins`](https://github.com/ComposioHQ/awesome-claude-plugins) | 1,826 | Curated *index* of plugins, useful for discovery; not a reviewer itself. |

## How they compare

The ten split into three groups: **general reviewers** (compared head-to-head below),
**security specialists** (security-guidance #3, Trail of Bits #8, OWASP #9 — different depth
and scope, covered in their sections), and a **methodology** entry (superpowers #10, which
structures *how* review is dispatched rather than performing a scan).

### General reviewers, head-to-head

| Axis | Anthropic code-review | pr-review-toolkit | security-guidance | awesome-skills | CodeRabbit | Tag1 | alirezarezvani |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Form** | 1 command → agents | 6 agents | 3 hooks | guidance skill | CLI wrapper | orchestrator skill | skill + scripts |
| **Multi-agent** | ✅ 4 + validators | ✅ 6 | — | — | (external) | ✅ 10+ | — |
| **Adversarial re-verify** | ✅ per finding | — | — | — | `[Unverified]` | ✅ blind/edge/adversarial | — |
| **Confidence scoring** | ✅ ≥80 | ✅ per agent | severity | severity labels | — | ✅ `--min-confidence` | risk tiers |
| **Posts to PR** | ✅ GitHub | — | — | — | ✅ | ✅ GH/GL/BB | — |
| **Multi-forge** | GitHub | — | — | — | GH/GL | GH/GHE/GL/BB | — |
| **Deterministic linters** | — | — | regex layer | — | ✅ 40+ | ✅ ~12 opt-in | ✅ Python scripts |
| **Security specialization** | in-diff | silent-failure | ✅ primary | security guide | ✅ | ✅ Opus agent + policy | secret/SQLi checks |
| **Distribution** | in-CLI + marketplace | marketplace | in-CLI default | clone/skill | marketplace | Tag1 marketplace | clone/skill |
| **Standout** | high-signal validate loop | composable building block | ambient/always-on | 21k lines, 20+ langs | 40+ analyzers, commercial | breadth + governance + tests | testable scripts |

**Reading the field.** The three Anthropic plugins are the reference implementations and the
most broadly deployed by virtue of shipping with Claude Code. Among community work, several
philosophies coexist: **knowledge-dense guidance skills** (awesome-skills, alirezarezvani,
OWASP) that make one review smarter; **multi-agent orchestrators** (Tag1) that fan out and
consolidate — explicitly building on Anthropic's pr-review-toolkit rather than competing with
it; **professional security-audit tooling** (Trail of Bits) with the deepest methodology and
the only documented real-world bug trophies; a **process/methodology** layer (superpowers)
that dispatches a fresh reviewer subagent and disciplines how feedback is handled; and
**external-engine delegation** (CodeRabbit), the outlier that hands the review to a commercial
platform with 40+ analyzers. `[Inference]` For general PR review the Anthropic `/code-review`
command and Tag1's orchestrator are the most directly comparable to a decaf-style multi-agent
suite; for security depth Trail of Bits sets the bar.

---

### Provenance & reproducibility

Each subdirectory contains a `PROVENANCE.md` with the exact source URL, commit SHA, commit
date, retrieval date (2026-07-16), and clone method. The Anthropic plugins, the alirezarezvani
skill, and the superpowers review skills were obtained via sparse partial clone of just the
relevant subtree; the standalone community repos (awesome-skills, CodeRabbit, Tag1, Trail of
Bits, OWASP) were shallow-cloned and had their `.git` directories removed after recording the
SHA. Popularity numbers are point-in-time (2026-07-16) GitHub API values and will drift.

### Sources

- Anthropic Code Review plugin — https://github.com/anthropics/claude-code/tree/main/plugins/code-review
- Anthropic PR Review Toolkit — https://github.com/anthropics/claude-code/tree/main/plugins/pr-review-toolkit
- Anthropic Security Guidance — https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance
- Official marketplace — https://github.com/anthropics/claude-plugins-official
- awesome-skills/code-review-skill — https://github.com/awesome-skills/code-review-skill
- CodeRabbit Claude plugin — https://github.com/coderabbitai/claude-plugin · docs https://docs.coderabbit.ai/cli/claude-code-integration
- Tag1 comprehensive-review — https://github.com/tag1consulting/claude-comprehensive-review
- alirezarezvani/claude-skills — https://github.com/alirezarezvani/claude-skills
- Trail of Bits skills — https://github.com/trailofbits/skills
- agamm/claude-code-owasp — https://github.com/agamm/claude-code-owasp
- obra/superpowers — https://github.com/obra/superpowers
- getsentry/skills — https://github.com/getsentry/skills
- Awesome collections — https://github.com/travisvn/awesome-claude-skills · https://awesomeclaude.ai/awesome-claude-skills
- Roundups consulted — designrevision.com/blog/claude-code-code-review · firecrawl.dev/blog/best-claude-code-plugins · composio.dev/content/top-claude-code-plugins · claudedirectory.org/plugins/code-review
