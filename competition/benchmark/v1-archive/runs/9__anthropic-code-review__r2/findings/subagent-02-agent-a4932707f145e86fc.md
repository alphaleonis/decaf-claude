# subagent agent-a4932707f145e86fc

Based on my verification using `gh api` against the kubernetes/kubernetes repository, I have confirmed the following:

**Code Verification (HEAD SHA 46e2c22fd76643bc985f7e77c99e97c6b7d078fc):**
- Line 162-165 in OnNodeChange: unconditionally calls `n.exitFunc(1)` when PodCIDRs change
- Line 169-172 in OnNodeChange: unconditionally calls `n.exitFunc(1)` when NodeIPs change  
- Line 177-178 in OnNodeDelete: unconditionally calls `n.exitFunc(1)` without any condition

**Review Feedback Verification:**
- danwinship explicitly flagged this risk in PR #125382 (discussion r1669405761): "we don't really deal well with the case where the Node is deleted and then not created... we will crashloop in that case"
- danwinship re-raised this concern in PR #130837 by referencing that discussion, asking to consider the crashloop scenario
- The concern was NOT resolved before PR #130837 merged (2025-07-11)

**Follow-up Confirmation:**
- PR #133059 was created and merged (2025-07-22) specifically to address this
- Commit facbb66142 in PR #133059 comments out these exact exit calls with "// FIXME: exit" markers in lines 196-201 and 205-209
- The tests were also updated to reflect the reverted behavior (expectedExitCode: nil instead of ptr.To(1))

This is a real issue that will cause kube-proxy to crashloop during normal operational scenarios (node IP reassignment, node churn, cloud-provider multi-step IP allocation).

**100**

The unconditional exitFunc(1) calls are directly present in the merged code, danwinship explicitly flagged this exact crashloop scenario in prior review, the issue was not resolved before merge, and a subsequent PR definitively confirmed the bug by reverting the problematic code paths with FIXME comments.
