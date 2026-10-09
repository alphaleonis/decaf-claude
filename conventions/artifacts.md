# Generated Artifacts — the `.decaf/` root

Skills that generate working artifacts (review reports, refactor plans, loop state, etc.)
write them under **one per-project root: `.decaf/`** — created in the user's target project,
not in this plugin repo. One predictable, gitignorable location instead of scattered
top-level dot-dirs.

## Layout

```
.decaf/
├── code-reviews/                # code-review + coverage-review reports + resolve state
│   ├── CODE_REVIEW_<ts>.md
│   ├── COVERAGE_REVIEW_<ts>.md
│   ├── .resolve-state.json
│   └── .resolve-coverage-state.json
├── refactoring-plans/           # refactor plans + resolve state
│   ├── REFACTOR_PLAN_<ts>.md
│   └── .resolve-refactor-state.json
├── auto-review/                 # auto-code-review loop state
│   └── state.json
├── batch-dev/                   # per-item review specs, self-ignoring (never committed)
│   ├── .gitignore               # `*`
│   └── specs/<item-id>.md, cluster-<n>.md
├── architecture-improvements/   # architecture-review candidates + resolve state
│   ├── CANDIDATES_<ts>.md
│   └── .handle-state.json
├── conventions/                 # project additions to the plugin conventions — hand-written, committed
│   └── comments.md              # glossary, line width, local comment rules (see comments.md)
├── grill-me/                    # grill-me running summaries
│   └── <topic>.md
├── session-reports/             # --report session reports (see session-report.md)
│   └── <date>-<slug>-code-review-session/
│       ├── README.md
│       └── iteration-N-consolidated-review.md
└── auto-deliver/                # auto-deliver loop state/artifacts
    └── …                        # see the auto-deliver skill's artifact-layout.md
```

## Not under `.decaf/`

- **`plans/`** (PRDs, plans, RFCs from the plan skills) — human-facing **deliverables**, kept
  visible at the repo root, not tool scratch.
- The project's own tracker store (e.g. `.nibs/`) — not ours.

## For skill authors

A skill that emits artifacts writes them to `.decaf/<domain>/…` in the target project. These
are paths in the **user's project**, written at runtime — not `@file` references into this
repo, so no symlink is needed (unlike the shared convention files, which are `@`-referenced).
Pick a clear `<domain>` subdir and keep state files inside it.

## Git-tracking

`.decaf/conventions/` is the exception to "generated": a person writes it, and it is always
committed, because agents read it as project configuration.

For the rest, each domain decides. The ephemeral review / refactor / coverage / candidate artifacts are
typically gitignored; the `auto-deliver` loop intentionally **tracks** its durable state
(`state.json`, `lessons.md`, `phases/*/reflection.md`) and ships its own `.gitignore` for the
regenerable logs — see its artifact-layout.md. Projects add the artifact subdirs
they want ignored to their `.gitignore`, one by one. Ignoring `.decaf/` as a whole would also hide
`.decaf/conventions/`.
