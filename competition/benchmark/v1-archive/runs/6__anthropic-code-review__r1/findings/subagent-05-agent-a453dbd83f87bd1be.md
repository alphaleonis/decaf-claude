# subagent agent-a453dbd83f87bd1be

100

The code confirms the regression exists. Lines 62-104 of clipboardService.ts now write native OS file formats (NSFilenamesPboardType, text/uri-list, FileNameW) for internal local-file copies. Line 341 of explorerView.ts's DOM paste listener fires whenever `event.clipboardData?.files?.length` is non-empty—meaning internal copies now populate the OS clipboard with real files, triggering both the keybinding paste AND the DOM paste handler, causing double execution. The external corroboration (PR #323002 "Fix explorer paste" merged to counter this exact issue, and PR #323490's full revert) directly confirms this was a production regression requiring fixes.
