# code-quality/

Code quality checks for LLM-assisted development, organized by detection scope.

## Files

| File           | What                                              | When to read                                             |
| -------------- | ------------------------------------------------- | -------------------------------------------------------- |
| `README.md`    | Format rationale, integration with skills         | Understanding category format, modifying categories      |
| `baseline.md`  | Atomic smells detectable in isolation             | Code review (baseline pass), planning-time quality checks |
| `coherence.md` | Repetition/consistency patterns (file + codebase) | Code review (consistency), refactoring at any scope      |
| `drift.md`     | Codebase-wide architectural issues                | Periodic architecture review, detecting accumulated debt |
