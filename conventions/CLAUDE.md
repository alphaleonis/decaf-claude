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
| `temporal.md`       | Timeless present rule for comments       | TW/QR temporal contamination checks, writing comments   |
| `work-items.md`     | Tracker-agnostic work-item adapter contract (create / next-ready / read / set-status / close / create-followup) per backend | Any skill that creates or operates on work items; the auto-deliver loop |
| `acceptance-criteria.md` | `## Acceptance` format — runnable checks vs. manual-tagged criteria | draft-spec / draft-plan / breakdown-phase (emit it); auto-deliver verify (read it) |
| `artifacts.md` | The `.decaf/` root for skill-generated artifacts (reviews, refactor plans, loop state, etc.) | Any skill that writes generated artifacts to the user's project |

## Subdirectories

| Directory       | What                                   | When to read                                                  |
| --------------- | -------------------------------------- | ------------------------------------------------------------- |
| `code-quality/` | Baseline/split/drift quality checks    | QR code review, refactoring, planning-time quality validation |
