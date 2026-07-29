# subagent agent-a304e1631d0bed109

Based on my examination of the PR diff, I can verify the issue claim:

**Verified Facts:**
1. **Before the change**: `event.dataTransfer.setData(DataTransfers.TEXT, fileSystemResources.map(...))` was called unconditionally for ALL fileSystemResources regardless of scheme.
2. **After the change**: Text is only set when `nativeResources.length > 0`, where `nativeResources` filters to only `resource.scheme === Schemas.file`.
3. **For remote-only selections**: If dragging only vscode-remote:// resources, `nativeResources` will be empty, so the `if (nativeResources.length)` block is skipped and NO TEXT is set.
4. **Text is the only place**: Lines 240-248 are the ONLY place in `fillEditorsDragData()` where DataTransfers.TEXT is set. No fallback or alternative mechanism exists for remote resources.
5. **Real functional impact**: This measurably changes drag-and-drop behavior. Remote-only selections lose the ability to paste URIs into external text areas (terminals, browsers, chat apps).

**Assessment:**
The code change is exactly as described: TEXT is conditionally set only for file:// resources, which means remote-only selections will have an empty TEXT payload. The change appears intentional (based on the comment about avoiding macOS Finder .webloc files), but the implementation is broader than the stated intent—it disables TEXT for remote resources globally on all platforms, not just for Finder. This is a genuine functional regression for users with remote-only selections, even if it was an intentional tradeoff decision.

**Score: 68**

The behavior change is verified and measurable, will affect users with remote workspaces, and directly impacts paste functionality. However, the implementation suggests this was an intentional design decision (not an accidental bug), which prevents a "highly confident" rating. The tradeoff between avoiding macOS Finder .webloc files and disabling remote-URI text transfer is debatable—users might have preferred a more targeted fix (e.g., macOS-only, or setting TEXT with a different MIME type to prevent .webloc creation).
