# subagent agent-a962d7f1512c31495

85

The code trace is verified across all four components. `cutFileHandler` sets `pasteShouldMove=true` and calls `setToCopy(..., true)`, but `setToCopy` unconditionally calls `resolveClipboardResources`, which downloads remote files to temp `file://` URIs and writes those to the clipboard. `pasteFileHandler` then moves the temp copies, leaving the originals in place. This is a real behavioral regression: cut+paste of remote files (increasingly common with Remote Development) now leaves the source file behind instead of deleting it.
