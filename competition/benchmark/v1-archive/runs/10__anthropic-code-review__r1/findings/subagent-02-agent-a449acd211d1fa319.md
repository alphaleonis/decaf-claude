# subagent agent-a449acd211d1fa319

**100**

I have verified this issue with conclusive evidence from the local git history and GitHub records. Commit 8c6595c2 (the line_buffer.rs half of PR #3185) definitively contains the exact `while !self.free_buffer().is_empty()` inner loop described in the issue. This was immediately exposed by users: issue #3194 (filed Oct 18) and duplicate #3199 (Oct 22) both report that `--line-buffered` stopped working in 15.0.0, with `journalctl -f | rg` hanging until the buffer fills or the pipe closes. The revert commit d47663b1 explicitly states the while-loop approach is "clearly contrary to how `--line-buffered` works" and fixes the regression by removing it—within 5 days of the original commit. The evidence directly confirms this is a real, impactful bug that broke streaming responsiveness.
