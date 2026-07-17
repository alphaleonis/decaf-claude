# subagent agent-a3c992e7e54194bc9

```json
{
  "finding": "#1",
  "verdict": "confirmed",
  "reason": "Independently re-derived from reflection semantics: RuntimeType.GetPropertyCandidates dedupes same-name candidates only via vtable-slot matching, which applies solely to virtual members; C#'s `new`-hiding produces non-virtual properties, so a name+flags-only GetProperty query that must flatten across levels accumulates every same-named PropertyInfo in the ancestor chain regardless of differing property type, and the single-string overload throws AmbiguousMatchException when it cannot disambiguate. Also, BindingFlags.FlattenHierarchy documented behavior only governs static-member visibility (per MSDN); for instance members (as used here, Public|Instance with no Static flag) the fallback call is functionally identical to plain Public|Instance, i.e. it already walks the whole hierarchy and collects every hidden same-named instance property — it adds no disambiguation power over the pre-fix single-arg GetProperty call for this exact repro shape. Verified against the actual file: DeclaredOnly(leaf) at lines 370-372 only short-circuits when the model type ITSELF redeclares the property; when only an intermediate ancestor hides it, DeclaredOnly(leaf) returns null and the fallback at lines 376-378 re-triggers the identical ambiguity the PR set out to fix. Confirmed the PR's own test dodges this: EditContextDataAnnotationsExtensionsTest.cs line 423-427 shows DeepDerivedModel (the leaf/model type actually instantiated at line 243) itself declares `public new int Tag`, so DeclaredOnly succeeds on the very first call and the vulnerable FlattenHierarchy fallback path is never exercised, even though MidLevelModelWithShadow (line 418-421, `new string Tag`) vs. ModelWithHiddenBaseProperty (line 411-416, `object Tag`) sets up exactly the differently-typed hidden-property shape needed to reproduce the bug at the intermediate level. Confirmed via `git show 3b00cfca` that this DeclaredOnly/FlattenHierarchy fallback is entirely new code introduced by this exact commit (the prior line was the single-arg `GetProperty(cacheKey.FieldName)`), so pre_existing:no is correct. Confirmed the exception path is uncaught: OnFieldChanged (lines 79-100) calls TryGetValidatableProperty at line 94 with no try/catch, and TryGetValidatableProperty (lines 363-386) calls GetProperty directly with no try/catch, so AmbiguousMatchException propagates uncaught out of NotifyFieldChanged.",
  "corrections": {
    "line": 376,
    "pre_existing": false
  }
}
```
