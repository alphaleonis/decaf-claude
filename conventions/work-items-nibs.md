# Work Items — Adapter: nibs

The operations of the tracker adapter contract in [work-items.md](work-items.md), on nibs.
Read the contract first; this file only says how each operation runs here.

Local markdown tracker with native types, hierarchy, dependencies, and a ready filter. Run
`nibs prime` once per project first — it emits project-specific agent instructions; honor
them. Types: `milestone`, `epic`, `bug`, `feature`, `task`, `research`.

> **Prose is never inline.** `-d`/`--body` and `close --summary` accept **only** `-`
> (stdin) or `@FILE` — passing inline text is rejected. Either pipe the body in
> (`... -d - <<'EOF'`) or write it to a file first and pass `@<path>` / `--body-file`.

- **create** — `nibs new "<title>" --type <type> --status <draft|todo> [--body-file <path> | -d @<path> | -d -] [--parent <id>] [--blocked-by <id> ...] [--priority <p>] [--tag <t> ...]`. Hierarchy by scope: large = `milestone → epic → phase(epic)/task`, small = `epic → task`.
- **next-ready** — native: `nibs list --ready --parent <plan-id> [--type epic] -q` → take the **first** id (default sort is the sibling order key = plan order). `--ready` already excludes blocked / in-progress / completed / **draft** / deferred, so drafts are filtered natively — no extra work on this backend. Empty output ⇒ no ready phase ⇒ plan complete.
- **list-ready** — the `next-ready` command, keeping every id it prints instead of the first (omit `--parent` for the whole project). Empty output ⇒ nothing ready.
- **read** — `nibs get <id>` (document) or `nibs list --parent <id> --view full --json` for structured. Body holds the spec + `## Acceptance`. Blockers: the `blocked_by` field. Children: `nibs rel <id> --rel children --all` (TSV of id, title, status, in sibling order).
- **set-status** — `nibs set <id> --status <draft|todo|in-progress|completed>`.
- **close** — `nibs close <id> --summary -` (summary on stdin; marks completed, merges Key Decisions / Current Focus into the parent).
- **append-note** — `nibs body <id> --append -`, with the note on stdin starting with its own `## <heading>` line.
- **create-followup** — `nibs new "<title>" --type <task|feature> --parent <plan-or-epic-id> --body-file <path> [--blocked-by <id>]`.
