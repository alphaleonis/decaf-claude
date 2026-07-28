# subagent agent-a1c746241930d2c3e

I can see the code change at lines 237-248. The PR introduced filtering that restricts `DataTransfers.TEXT` to only `file://` URIs via `nativeResources = fileSystemResources.filter(({ resource }) => resource.scheme === Schemas.file)`, setting TEXT only if that filtered array is non-empty.

The comment justifies this exclusively for native-app compatibility ("macOS would create .webloc URL bookmark files"), but `DataTransfers.TEXT` is also consumed by in-VS-Code text targets (terminals, search, editors). Remote workspaces (SSH/WSL/dev-container) using `vscode-remote://` URIs would now have *no* TEXT data set at all when dragged to in-app text areas, since they would not pass the scheme filter.

Critically, the issue's external corroboration is dispositive: PR #323490 reverted this exact change, and its summary explicitly notes it "restores prior behavior of setting text from all file-service resources"—direct evidence that the PR introduced a regression that was subsequently fixed by undoing this change.

**85**

The PR's approach is insufficient because it conflates two separate use-cases (native vs. in-app drops) under one data channel and optimizes only for one. The regression is real, impacts remote workspace users, and was confirmed by reversion.
