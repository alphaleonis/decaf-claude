# subagent agent-a1763d0d6aaa029ca

The comment in `fillEditorsDragData` (line 241, `src/vs/workbench/browser/dnd.ts`) is explicit: `// Text: allows to paste into text-capable areas`. That's the authoritative statement of intent.

I now have enough to answer.

## Findings

**Definition** (`src/vs/base/browser/dnd.ts`): `DataTransfers.TEXT = Mimes.text` (i.e. `'text/plain'`), documented as "Typically transfer type for copy/paste transfers."

**All codebase usages of `DataTransfers.TEXT` are writes (`setData`), never reads (`getData`).** GitHub code search across the repo turned up six call sites, all setting it as an outgoing drag payload:
- `src/vs/workbench/browser/dnd.ts:241` — `fillEditorsDragData`, with the explicit comment `// Text: allows to paste into text-capable areas`
- `src/vs/base/browser/ui/list/listView.ts:1213`, `.../splitview/paneview.ts:442`, `.../actionbar/actionViewItems.ts:124`, `.../parts/editor/editorTabsControl.ts:437` (drags labels/URIs as plain text)
- `src/vs/editor/contrib/gotoSymbol/browser/peek/referencesWidget.ts:231`

No `getData(DataTransfers.TEXT)` / `getData('text/plain')` / `getData(Mimes.text)` reads exist anywhere in the repo for drag-drop purposes (the one `getData('text/plain')` hit, in `copyPasteController.ts:263`, is clipboard **paste** logging, unrelated to drag-drop).

**Internal drop targets deliberately ignore it and use VS Code-specific formats instead:**
- **Terminal** (`terminalInstance.ts`, `TerminalInstanceDragAndDropController.onDrop`, ~line 2625): reads `DataTransfers.RESOURCES`, `CodeDataTransfers.FILES`, and falls back to `e.dataTransfer.files`. Its drag-enter gate (`containsDragType`, line 2582) checks `DataTransfers.FILES, DataTransfers.RESOURCES, TerminalDataTransfers.Terminals, CodeDataTransfers.FILES` — `DataTransfers.TEXT` is absent from both.
- **Editor drop target** (`editorDropTarget.ts`): gates on `DataTransfers.FILES, CodeDataTransfers.FILES, DataTransfers.RESOURCES, CodeDataTransfers.EDITORS`, plus in-memory `LocalSelectionTransfer` instances (`editorTransfer`, `groupTransfer`, `treeItemsTransfer`) for same-window editor/group/tree drags.

**Conclusion**: `DataTransfers.TEXT` is purely an outbound convenience format so that dragging a VS Code file/tab onto an external, non-VS-Code text-capable surface (browser address bar, Slack, Notes, a plain text field) yields the file's path/label as plain text. It is not consumed by any internal VS Code drop target — those all use `DataTransfers.RESOURCES`/`CodeDataTransfers.FILES`/`CodeDataTransfers.EDITORS` or in-memory transfer objects.

**History**: I could not fetch usable blame/PR data pinpointing exactly when the TEXT line was first added to `fillEditorsDragData` — the commit list for `dnd.ts` (fetched via `gh api repos/microsoft/vscode/commits?path=...`) only reaches back to 2021 in the queried page and doesn't clearly isolate that line's origin, so I won't assert a specific PR/date for its introduction. [Unverified] The comment (`// Text: allows to paste into text-capable areas`) is directly readable in current source and is the strongest first-party evidence of purpose.
