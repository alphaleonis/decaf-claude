# Code Quality Guidelines

Prompts for LLM agents detecting code smells. Organized by detection scope:

| File           | Scope                       | Detection Method         |
| -------------- | --------------------------- | ------------------------ |
| `baseline.md`  | Single code unit            | Snippet analysis         |
| `coherence.md` | Repetition across file/repo | Cross-reference patterns |
| `drift.md`     | Codebase-wide architecture  | Full system view         |

## Format Rationale

Each section uses principle-first framing:

```markdown
## N. Category Name

<principle>
Abstract rule unifying all examples. Stated first to prime generalization.
</principle>

<detect>
Detection question framing the evaluation lens.
</detect>

<grep-hints>
Terms that sometimes indicate issues (starting points, not definitive):
`pattern1`, `pattern2`
</grep-hints>

<violations>
Illustrative patterns (not exhaustive) -- similar violations exist:

[severity] Category label

- Example with "e.g." prefix
- Open-ended: "Any X that causes Y"
</violations>

<exceptions>
Boundary cases with principle-based test.
</exceptions>

<threshold>
Severity bar for flagging.
</threshold>
```

### Why This Works

| Feature                           | Mechanism                                               |
| --------------------------------- | ------------------------------------------------------- |
| `<principle>` first               | Primacy effect -- early content shapes interpretation   |
| "starting points, not definitive" | Hedging breaks literal anchoring                        |
| "e.g.," prefix                    | Signals exemplification vs enumeration                  |
| Open-ended escape hatch           | Keeps violation list unbounded                          |
| XML semantic markers              | Structure for LLM; transparent to line-range extraction |

## Integration

Skills extract sections by line range (regex: `^## \d+\. (.+)$`). Content within sections is free-form -- parser extracts raw text, LLM interprets structure.

### Skill Prompt Additions

Wrap extracted blocks with:

```
<interpretation>
Examples illustrate a PRINCIPLE, not exhaustive checklist.
Detect ANY violation of the principle, including unlisted patterns.
</interpretation>
```

Add analogical prompting after block:

```
GENERALIZATION:
Before searching, identify 2-3 OTHER patterns violating the SAME principle.
Search for BOTH listed exemplars AND self-generated patterns.
```

This triggers domain-specific recall, enabling transfer beyond listed examples.
