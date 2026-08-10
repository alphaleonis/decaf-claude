# subagent agent-ab3d6f57a691e1bbc

**95**

The code substitution is definitively verified: `resolveClipboardResources` (lines 287–326) downloads every remote resource to a temp `file://` URI and returns that instead, breaking the source's workspace identity. The external evidence is overwhelming: issue #321394 reproduces the exact failure (copy/paste in WSL, target-exists error on same folder), a telemetry spike in EntryExists errors shipped with this PR, and PR #323490 fully reverted it—all confirming this caused a real-world regression.
