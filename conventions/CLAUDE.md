# conventions/

Canonical shared conventions for agents and skills. Each plugin's `conventions/` holds symlinks to the files it references (see the repo-root `CLAUDE.md` → **Conventions & shared files**).

## Files

| File                | What                                     | When to read                                            |
| ------------------- | ---------------------------------------- | ------------------------------------------------------- |
| `documentation.md`  | CLAUDE.md/README.md format specification | Writing CLAUDE.md or a README; the technical-writer agent |
| `intent-markers.md` | `:PERF:`/`:UNSAFE:`/`:SCHEMA:` marker spec | Adding intent markers; reviewers validating them      |
| `severity.md`       | Severity levels (MoSCoW) and finding categories by recoverability; the confidence anchors are in `code-review-consolidation.md` | Understanding code-review severity; authoring a reviewer persona |
| `structural.md`     | Code-quality conventions, testing rules  | Code review; planning-time quality checks               |
| `refactoring.md`    | Refactoring value matrix + consolidation rules | The refactor skill; merging structural/coherence findings |
| `code-review-consolidation.md` | Merging findings from several agents: severity normalization, confidence anchors, deduplication, the confidence gate | code-review and coverage-review when consolidating agent reports |
| `coverage-config.md` | The `## Coverage` section a project's CLAUDE.md carries: report path, format, thresholds | The coverage-review skill |
| `comments.md`       | Rules for code comments and doc comments, any language; project overlay in `.decaf/conventions/comments.md` | Writing or reviewing comments; the write-comments skill, knowledge-reviewer, technical-writer |
| `work-items.md`     | Tracker-agnostic work-item adapter contract (create / next-ready / list-ready / read / set-status / close / append-note / create-followup), status model, tracker detection | Any skill that creates or operates on work items; batch-dev; the auto-deliver loop |
| `work-items-<tracker>.md` | One adapter per tracker (`nibs`, `ado`, `github`, `markdown`): how each contract operation runs there | After detection, only the one for the tracker in use |
| `acceptance-criteria.md` | `## Acceptance` format — runnable checks vs. manual-tagged criteria | draft-spec / draft-plan / breakdown-phase (emit it); auto-deliver verify (read it) |
| `open-questions.md` | Open questions a run leaves for a person: kinds, the reflection entry, the filed `draft` item, how a resolution is recorded | auto-deliver (record + file); resolve-open-questions (walk) |
| `pr-etiquette.md`   | Rules for anything posted where others read it (PR comments, replies, thread status) | Any skill that posts to a PR (code-review, resolve-pr-feedback) |
| `persona-authoring.md` | Required reviewer-agent anatomy, ownership matrix, integration checklist | Adding or editing a decaf-quality reviewer persona |
| `artifacts.md` | The `.decaf/` root for skill-generated artifacts (reviews, refactor plans, loop state, etc.) | Any skill that writes generated artifacts to the user's project |
| `session-report.md` | `--report` flag: comparison-grade session reports for skill tuning — data duties per skill + README format | code-review / auto-code-review / auto-tdd / auto-dev when `--report` is passed |
| `subagent-briefs.md` | Subagent dispatch & report delivery — task vs teammate mode, the delivery clause named teammates need, the spawn-ack tripwire | Any skill that launches agents via the `Agent` tool (fan-outs, workers, review subagents, teams) |

## Subdirectories

| Directory       | What                                   | When to read                                                  |
| --------------- | -------------------------------------- | ------------------------------------------------------------- |
| `code-quality/` | Baseline / split / drift quality checks | Code review, refactoring, planning-time quality validation   |
