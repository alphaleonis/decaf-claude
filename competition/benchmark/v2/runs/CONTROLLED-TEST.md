# Controlled test: gh shim on vs off (subject 2, anthropic-code-review, 2026-08-10)

Single variable: `gh` shimmed vs unrestricted. Prompt, model (opus-4-8), effort (high), checkpoint
(`3aa499ae7d23`, 2026-07-07), and the WebFetch/WebSearch denial are identical across arms.
2 repeats per arm.

| Arm | r | e1 reported? | Derivation | Cost | Wall |
|---|---|---|---|---|---|
| **shim on** | 1 | **yes** — "Found 1 issue" | from the code; built a repro against the PR's own test models | $2.85 | 317s |
| **shim on** | 2 | **yes** — "score ~80" | from the code; used `docs-at` for `Type.GetProperty` semantics | $2.79 | 432s |
| **shim off** | 1 | **yes** — "Found 1 primary issue" | **cites a post-checkpoint maintainer comment** | $4.19 | 389s |
| **shim off** | 2 | **yes** — "Finding 1 — Correctness" | from the code | $0.88 | 224s |

## Result 1 — the shim does not change detection

**4 of 4 cells reported e1.** On this subject, restricting `gh` neither helped nor hurt whether the
defect was found. Detection came from the code in three of four cells.

## Result 2 — my suppression hypothesis is NOT supported

I speculated that seeing `state: MERGED` and an approval raises the bar a finding must clear, after a
run collapsed to "No blocking issues found". That run differed from these in **two** ways — a
different prompt *and* the older permissive shim — so it was never a clean comparison. With the
prompt held fixed, both arms report e1 in both repeats. **Withdraw the hypothesis**; one confounded
observation is not evidence.

## Result 3 — what the shim actually protects is PROVENANCE

shim-off r1 wrote:

> "A maintainer (Youssef1313) raised exactly this on 2026-07-09, after the latest commit, and it is
> unaddressed: .../pull/67075#discussion_r3549541503"

Verified: comment `3549541503`, Youssef1313, created **2026-07-09T06:58:15Z** — two days AFTER the
checkpoint. Its text: *"FlattenHierarchy is only relevant for statics IIRC. And this code can still
throw if the previous call returned null and we get into here with some shadowing member in a base
type."* That is e1, stated by a human, read by the reviewer, and cited as support.

So the unrestricted arm did leak — it just leaked into a finding it would have made anyway. The
scoring consequence is not a wrong verdict on this subject; it is that **the finding's provenance is
unknowable without the access log**. On a harder subject, where the tool would not have derived it
alone, the same leak would manufacture a catch. That is the case the shim exists for.

## Result 4 — the DENY path works in situ

First time exercised by a real reviewer, not a synthetic test:

```
r1: pr view --json title,state,...   DENY (state field)
    pr view (bare)                   DENY (prints state/reviewers)
r2: pr view --json ...,state,...     DENY
    gh api .../pulls/67075/comments  DENY (api)      <- the exact leak channel used by shim-off r1
    pr view (bare)                   DENY
    docs-at .../system.type.getproperty  ALLOW x3    <- routed to time-boxed docs instead
```

The `gh api .../comments` call denied in shim-on r2 is precisely how shim-off r1 obtained the
post-checkpoint comment. The control blocks the observed leak channel, and the tool substituted
checkpoint-pinned documentation rather than losing the capability.

## Measurement gap found

With the shim off there is **no access log at all** — logging is performed by the shim. The control
arm's "0 external accesses" is an artifact, not a measurement. Leak detection in the unshimmed arm
had to be done by grepping outputs for post-checkpoint markers, which only catches leaks the tool
chooses to cite. A future control arm needs independent logging (a wrapper that logs and forwards).

## Caveats

- One subject, one tool, two repeats per arm. Enough to withdraw a hypothesis, not to establish one.
- Cost variance within the unshimmed arm is large ($0.88 to $4.19) and unexplained.
- Subject 2's defect is derivable from the diff alone, which is exactly why the leak changed nothing
  here. A subject where it is not derivable would separate the arms.
