# subagent agent-ab817f8977b13438b

Based on my analysis of the PR and the relevant code in the aspnetcore repository, I can now provide a confidence score.

The issue is accurate in identifying an inconsistency: there are indeed three different property-resolution approaches in the codebase:

1. **ValidatableTypeInfo.TryFindProperty** (lines 84-114 in ValidatableTypeInfo.cs): Checks local members first, then recursively walks interfaces and base types.

2. **PropertyHelper.GetVisibleProperties** (lines 411-480 in PropertyHelper.cs): Filters all properties by walking the hierarchy to exclude `new`-hidden base declarations (checking `DeclaringType==type`).

3. **TryGetValidatableProperty** (lines 370-378 in the PR fix): Tries `DeclaredOnly` first, then falls back to `FlattenHierarchy`.

However, I verified that all three approaches produce **functionally equivalent results** for:
- Shadowed properties (derived `new` properties hiding base properties)
- Inherited properties (only on base)
- Deep inheritance hierarchies with multiple shadowing levels
- All test scenarios pass

The fix solves a real bug (AmbiguousMatchException when both base and derived define properties with the same name), and the `DeclaredOnly + FlattenHierarchy` approach correctly handles both cases. The separate implementation exists as a fallback when `ValidatableTypeInfo` is unavailable, and `PropertyHelper` is internal (cannot be reused). This fallback path is necessary and working correctly.

40

This is a valid code-consistency observation, not a false positive, but the issue represents a minor design concern rather than a critical problem. The fix is functionally correct, the approaches are equivalent, and there is justification for the separate implementation path. Without an explicit CLAUDE.md requirement or a concrete functional failure, this is a lower-priority code-quality observation.
