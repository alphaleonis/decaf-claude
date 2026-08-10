# subagent agent-ac5cb3102f1ef01db

100

This is a documented real issue causing fatal crashes in production. The verified code unconditionally waits for GetNodeHostIPs; when it fails on out-of-tree cloud provider clusters, kube-proxy blocks for 5 minutes then exits fatally—preventing the cloud provider from initializing its own node addresses (circular dependency). The issue history confirms this: PR #132958 reverted #130837 for this exact reason, and PR #133059 re-landed it with a non-fatal fix specifically addressing this deadlock scenario.
