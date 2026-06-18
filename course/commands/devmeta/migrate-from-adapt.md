---
description: Migrate from ADAPT (.adapt/) to DevMeta (.devmeta/) — renames directory, updates all references
---

## Purpose

This command migrates a project that uses the ADAPT framework (`.adapt/` directory, `/adapt:` or `/adapt-m-g:` commands) to use DevMeta (`.devmeta/` directory, `/devmeta:` commands).

It renames the directory, updates all internal references, and updates CLAUDE.md. Run this once per project. Idempotent — if `.devmeta/` already exists, it reports what's already done and skips.

## Phase 1: Discover

Check what exists:

```bash
test -d .adapt && echo ".adapt/ exists: $(find .adapt -type f | wc -l) files"
test -d .devmeta && echo ".devmeta/ already exists: $(find .devmeta -type f | wc -l) files"
test -f .adapt/adapt.md && echo "adapt.md config found"
test -f .adapt/current-increment.md && echo "current-increment.md found"
test -d .adapt/increments && echo "increments: $(ls -d .adapt/increments/*/ 2>/dev/null | wc -l) directories"
test -f .adapt/project-history.md && echo "project-history.md found"
test -f .adapt/lessons-learned.md && echo "lessons-learned.md found"
test -d .adapt/ia-cycles && echo "ia-cycles: $(ls .adapt/ia-cycles/ 2>/dev/null | wc -l) files"
test -d .adapt/projects && echo "projects: $(ls -d .adapt/projects/*/ 2>/dev/null | wc -l) directories"
```

If `.devmeta/` already exists with content, report and stop. If `.adapt/` doesn't exist, report and stop.

## Phase 2: Rename directory

```bash
mv .adapt .devmeta
```

## Phase 3: Rename config file

If `.devmeta/adapt.md` exists:

```bash
mv .devmeta/adapt.md .devmeta/devmeta.md
```

## Phase 4: Update internal references in all `.devmeta/` files

Scan all `.md` files under `.devmeta/` and replace:

| Find | Replace |
|------|---------|
| `.adapt/adapt.md` | `.devmeta/devmeta.md` |
| `.adapt/` | `.devmeta/` |
| `/adapt-m-g:` | `/devmeta:` |
| `/adapt:` | `/devmeta:` |
| `ADAPT Feature` | `DevMeta Feature` |
| `ADAPT Task` | `DevMeta Task` |
| `ADAPT Delivery Engine` | `DevMeta Delivery Engine` |

**Do NOT replace:**
- `Inspect & Adapt` — this is a methodology term
- `adapt` as a verb in prose (e.g., "adapt plans and docs")
- Historical content in project-history.md or lessons-learned.md

```bash
find .devmeta -name '*.md' -exec sed -i \
  -e 's|\.adapt/adapt\.md|.devmeta/devmeta.md|g' \
  -e 's|\.adapt/|.devmeta/|g' \
  -e 's|/adapt-m-g:|/devmeta:|g' \
  -e 's|/adapt:|/devmeta:|g' \
  -e 's|ADAPT Feature|DevMeta Feature|g' \
  -e 's|ADAPT Task|DevMeta Task|g' \
  -e 's|ADAPT Delivery Engine|DevMeta Delivery Engine|g' \
  {} +
```

## Phase 5: Update CLAUDE.md

If `CLAUDE.md` exists, replace:

| Find | Replace |
|------|---------|
| `.adapt/` | `.devmeta/` |
| `/adapt-m-g:` | `/devmeta:` |
| `/adapt:` | `/devmeta:` |
| `adapt.md` (standalone config reference) | `devmeta.md` |

## Phase 6: Update .gitignore

If `.gitignore` references `.adapt/`:
- Replace `.adapt/` with `.devmeta/` (or ensure `.devmeta/` is NOT ignored)

## Phase 7: Update tick metadata

If `.tick/` exists, scan tick descriptions for `.adapt/` references and update:

```bash
find .tick/issues -name '*.json' -exec sed -i 's|\.adapt/|.devmeta/|g' {} +
```

## Phase 8: Commit

```bash
git add -A
git commit -m "Migrate from ADAPT (.adapt/) to DevMeta (.devmeta/)"
```

## Phase 9: Report

```markdown
## Migration Complete: ADAPT → DevMeta

### Renamed
| From | To |
|------|----|
| `.adapt/` | `.devmeta/` |
| `.devmeta/adapt.md` | `.devmeta/devmeta.md` |

### Updated references in
- All `.md` files under `.devmeta/`
- `CLAUDE.md`
- `.tick/issues/*.json`

### Command mapping
| Old | New |
|-----|-----|
| `/adapt:go` | `/devmeta:go` |
| `/adapt:status` | `/devmeta:status` |
| `/adapt:start-increment-spec` | `/devmeta:start-increment-spec` |
| `/adapt:plan-iteration` | `/devmeta:plan-iteration` |
| `/adapt:run` | `/devmeta:run` |
| `/adapt:reflect` | `/devmeta:reflect` |

### Next steps
- Use `/devmeta:` commands from now on
- Run `/devmeta:status` to verify project state
```

## Rules

- **Don't rewrite historical prose** — if project-history.md says "ADAPT migration", leave it
- **Don't touch application code** — this is a framework rename only
- **Don't delete .adapt/ without moving first** — `mv` is the operation
- **Stop if .devmeta/ already exists with content** — don't overwrite
- **Preserve Inspect & Adapt** — it's the I&A methodology name, not the framework
