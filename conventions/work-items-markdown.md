# Work Items — Adapter: Markdown (fallback)

The operations of the tracker adapter contract in [work-items.md](work-items.md), on a Markdown plan file.
Read the contract first; this file only says how each operation runs here.

A single plan file at `./plans/<plan-name>.md`. Phases are `##` sections in plan order;
features are checklist items; dependencies are stated in prose; status is the checkbox plus
an optional marker. Everything is by convention; the loop reads/writes the file.

- **create** — append a `## Phase N — <title>` section (or a `- [ ]` feature line) with the body and `## Acceptance` beneath it. Create `./plans/` if missing. For `draft` status, append a `- [?]` item under a `## Drafts` section instead — outside plan order.
- **next-ready** — the **first** phase section not marked done (`[ ]`/`[~]`) whose listed dependency phases are all `[x]`. Skip `[?]` items and anything under `## Drafts`. None ⇒ plan complete.
- **list-ready** — every phase section the `next-ready` rule admits, in file order. None ⇒ nothing ready.
- **read** — read the phase section (spec + `## Acceptance`). Blockers are the items its text names as dependencies; this backend states them in prose, with no machine-readable form. Its children are the `- [ ]`/`[~]`/`[x]` feature items under it, in file order; the checkbox is their status.
- **set-status** — change the section's checkbox marker (`[ ]` → `[~]` → `[x]`).
- **close** — mark `[x]` and append a `> Closed: <summary>` line under the section.
- **append-note** — append a `> <heading>: <text>` line under the item's section or checklist line.
- **create-followup** — append a new `- [ ]` item under a `## Follow-ups` section (or a new phase), with any dependency noted in prose.
