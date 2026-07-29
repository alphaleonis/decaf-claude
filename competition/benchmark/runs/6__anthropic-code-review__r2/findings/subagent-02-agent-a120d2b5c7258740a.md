# subagent agent-a120d2b5c7258740a

Based on my investigation, I can confirm this is a REAL issue that was verified in practice.

**Verified facts:**

1. **PR diff confirms the mechanism**: The PR modifies clipboardService.ts to write native OS clipboard formats (NSFilenamesPboardType on macOS, text/uri-list on Linux, FileNameW on Windows) in addition to VS Code's custom format. The readResources() method reads back these formats.

2. **Real issue reports document double-pasting**: Issue #321387 contains explicit user reports: "When copying a file with Command+C and pasting with Command+V, the count increases by one while the dialog is displayed. Then, when clicking 'Paste' in the dialog, it increases by one more." Another comment states "files are still being pasted twice when pasting."

3. **PR was reverted twice**: PR #321516 (merged 2026-06-15) first reverted the changes due to "more than normal regressions." Then PR #323002 attempted a fix by adding `if (await this.clipboardService.hasResources()) return;` to explorerView.ts, but despite this guard, PR #323490 still reverted the changes again on 2026-06-29—indicating the problem persisted.

4. **The mechanism is sound**: The PR now populates the native OS clipboard, making event.clipboardData.files available to the unmodified DOM paste listener, causing both the keybinding handler and the DOM listener to fire on a single paste action.

**Score: 100**

This issue is absolutely real, directly confirmed by multiple user reports describing exactly the double-paste symptom described, and verified by the PR being reverted twice even after an attempted fix was applied.
