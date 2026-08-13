---
description: Prepare benchmark v2 for a run — rebuild the gitignored checkouts from committed fixtures, verify the corpus, check tooling
argument-hint: "[<subject-id> …]  (default: every pooled and null subject)"
---

Prepare **v2**. This is not v1's `bench_init.sh`, which generates a manifest for a dataset that is
void.

v2 needs no generation step: the corpus is committed. `fixture.json` and `threads.json` are in git;
only the checkouts under `pooled/*/repo` and `null/*/repo` are gitignored, because they run to ~3.3G
and are fully specified by the pinned SHAs.

## 1. What is missing

```
bash competition/benchmark/v2/status.sh
for d in competition/benchmark/v2/pooled/*/ competition/benchmark/v2/null/*/; do
  [ -d "$d/repo/.git" ] && printf '  ok      %s (%s commits)\n' "$(basename $d)" \
      "$(git -C "$d/repo" rev-list --count HEAD 2>/dev/null)" \
    || printf '  MISSING %s\n' "$(basename $d)"
done
```

## 2. Rebuild any missing checkout

```
bash competition/benchmark/v2/build_pooled_repo.sh <subject-id>
```

Two rules that are easy to get wrong and expensive to diagnose:

- **Fetch the checkpoint and nothing else.** A second `fetch --depth 1` of the merge base
  re-shallows the repository and discards the deep history — observed collapsing 129,013 commits to
  7. The base is an ancestor; it arrives with the checkpoint. Verify with `git rev-list --count HEAD`.
- **Each checkpoint has its own merge base.** Reusing an earlier base against a later head drags in
  everything the target branch merged in between — 18 files became 240 on one subject.

A rebuilt checkout must be byte-identical to what the fixture specifies. Verify:

```
git -C <repo> rev-parse HEAD                 # == fixture checkpoint.sha
git -C <repo> status --porcelain | wc -l     # 0
git -C <repo> worktree list | wc -l          # 1
git -C <repo> remote -v                      # empty — no remote, by construction
git -C <repo> diff <base> <sha> --shortstat  # == fixture checkpoint.diff_stat
```

## 3. Verify the corpus agrees with itself

```
python3 competition/benchmark/v2/scoring/test_score_pooled.py
python3 competition/benchmark/v2/scoring/test_judge_stability.py
```

Both suites must pass. A guard without a passing test has not been shown to fire.

Then confirm every admitted thread carries `origin: human|bot` — the scorer refuses without it, and
thread recall is defined over the human population only:

```
for f in competition/benchmark/v2/pooled/*/threads.json; do
  printf '%-34s %s\n' "$(basename $(dirname $f))" \
    "$(jq '[.[]|select(.admission=="admitted" and (.origin|not))]|length' $f) unstamped"
done
```

## 4. Check the tooling a cell needs

- Every roster tool's plugin is installed and its skill resolves under its **plugin-qualified** name.
  A bare name is ambiguous — two plugins ship a skill called `code-review`, and picking the wrong one
  is silent.
- `toolchain.sh` puts node / go / dotnet / python / cargo on PATH. Without it a cell degrades to
  static-analysis-only review and records `build_possible: false` — weaker evidence that looks
  identical to a strong cell.
- `/tmp` free space above 4096MB. It is tmpfs here; a cell has already exhausted it and aborted.

## 5. Report

What was rebuilt, what verified, and anything that would make a cell weaker than its siblings —
particularly a subject where `detect_build.sh` reports `build_possible: false`.
