# Work Item Creation

Shared conventions for detecting a work item tracking system and creating work items.

## System Detection

If the user specified a target system in their prompt, use that. Otherwise, detect what's available and ask.

Check in this order:

1. **GitHub** — Is this a GitHub repo? Check: `gh repo view --json name 2>/dev/null`. If yes, GitHub Issues is available.
2. **Azure DevOps** — Is an Azure DevOps MCP server connected? Check if MCP tools with "azuredevops" or "azure-devops" in their name are available. Alternatively, check: `az devops project show 2>/dev/null` for CLI availability.
3. **Beans** — Is the `beans` CLI available? Check: `command -v beans 2>/dev/null`. Also check if a `.beans.yml` config exists in the project (indicates beans is already initialized).

If multiple systems are available, or none are detected, ask the user which system to use. If only one system is detected, confirm with the user before proceeding.

## User Confirmation

**Always show the draft content to the user before creating work items in collaborative systems** (GitHub, Azure DevOps). These are shared-system actions visible to others. Only create after the user approves the draft.

For local-only targets (Beans, Markdown files), create directly — the user can edit afterward.

## Work Item Format

Regardless of tracking system, every work item has a **title** and a **body**. Use the same content structure everywhere — only the creation mechanism differs.

### Creation Methods

**GitHub Issues:**
Use `gh issue create --title "<title>" --body "<body>"`.

For parent/child hierarchies, use `--parent <parent-issue-number>` to create sub-issues. If `--parent` is not supported by the installed `gh` version, reference the parent issue number in each child's body and maintain a checklist in the parent.

**Azure DevOps:**
Prefer Azure DevOps MCP tools if available. Fall back to `az` CLI:

```
az boards work-item create --type "<type>" --title "<title>" --description "<body>"
```

Link children to parent:
```
az boards work-item relation add --id <child-id> --relation-type "System.LinkTypes.Hierarchy-Reverse" --target-id <parent-id>
```

Choose hierarchy based on scope:
- **Large scope** (multi-sprint): Feature → User Stories
- **Small scope** (single sprint): User Story → Tasks

If unsure about scope, ask the user.

**Beans:**
Beans is a local markdown-based issue tracker. When beans is detected, run `beans prime` first — it outputs project-specific instructions for AI agents, including any custom configuration. Follow those instructions for the project's conventions.

Core usage for work item creation:

```
beans create "<title>" --body "<body>" --type <type> --status todo
```

Beans supports parent-child hierarchies via `--parent`:
```
beans create "Root item" --type epic --status todo
beans create "Child item" --parent <root-id> --type task --status todo
```

Available types: `milestone`, `epic`, `bug`, `feature`, `task`. Choose hierarchy based on scope:
- **Large scope**: `milestone` → `epic` → `task`/`feature`
- **Small scope**: `epic` → `task`

Additional flags:
- `--body "<description>"` or `--body-file <path>` for body content
- `--priority <critical|high|normal|low|deferred>` for priority
- `--tag <tag>` for tagging (repeatable)
- `--blocked-by <id>` / `--blocking <id>` for dependency relationships

Use `beans roadmap` to generate a markdown roadmap from milestones and epics after creating work items.

**Markdown file (fallback):**
Write to `./plans/<feature-name>.md`. Create the `./plans/` directory if it doesn't exist.
