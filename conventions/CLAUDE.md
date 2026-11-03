# conventions/

Universal conventions for agents and skills.

## Files

| File                | What                                     | When to read                                            |
| ------------------- | ---------------------------------------- | ------------------------------------------------------- |
| `documentation.md`  | CLAUDE.md/README.md format specification | Writing CLAUDE.md, creating README.md, doc-sync skill   |
| `intent-markers.md` | :PERF:/:UNSAFE:/:SCHEMA: marker spec     | Adding intent markers, QR validation of markers         |
| `severity.md`       | MUST/SHOULD/COULD severity definitions   | Understanding QR severity, writing QR scripts           |
| `structural.md`     | Code quality conventions, testing rules  | QR code review, planner decision audit                  |
| `refactoring.md`    | Refactoring consolidation rules          | Refactoring skill, merging structural/coherence findings |
| `comments.md`       | Rules for code comments and doc comments, any language; project overlay in `.decaf/conventions/comments.md` | Writing or reviewing comments; write-comments skill, knowledge-reviewer, technical-writer |
| `work-items.md`     | Tracker-agnostic work-item adapter contract (create / next-ready / list-ready / read / set-status / close / append-note / create-followup), status model, tracker detection | Any skill that creates or operates on work items; batch-dev; the auto-deliver loop |
| `work-items-<tracker>.md` | One adapter per tracker (`nibs`, `ado`, `github`, `markdown`): how each contract operation runs there | After detection, only the one for the tracker in use |
| `acceptance-criteria.md` | `## Acceptance` format — runnable checks vs. manual-tagged criteria | draft-spec / draft-plan / breakdown-phase (emit it); auto-deliver verify (read it) |
| `open-questions.md` | Open questions a run leaves for a person: kinds, the reflection entry, the filed `draft` item, how a resolution is recorded | auto-deliver (record + file); resolve-open-questions (walk) |
| `artifacts.md` | The `.decaf/` root for skill-generated artifacts (reviews, refactor plans, loop state, etc.) | Any skill that writes generated artifacts to the user's project |
| `session-report.md` | `--report` flag: comparison-grade session reports for skill tuning — data duties per skill + README format | code-review / auto-code-review / auto-tdd / auto-dev when `--report` is passed |
| `subagent-briefs.md` | Subagent dispatch & report delivery — task vs teammate mode, the delivery clause named teammates need, the spawn-ack tripwire | Any skill that launches agents via the `Agent` tool (fan-outs, workers, review subagents, teams) |

## Subdirectories

| Directory       | What                                   | When to read                                                  |
| --------------- | -------------------------------------- | ------------------------------------------------------------- |
| `code-quality/` | Baseline/split/drift quality checks    | QR code review, refactoring, planning-time quality validation |
