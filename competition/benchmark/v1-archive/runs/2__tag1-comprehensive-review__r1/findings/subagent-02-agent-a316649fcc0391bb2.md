# subagent agent-a316649fcc0391bb2

I empirically verified the reflection behavior with a .NET 10 console app. Here are my findings.

## Review scope
- `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs` — `TryGetValidatableProperty` (lines 362-386), the two-step `GetProperty` lookup.
- `src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs` — new tests and model types (lines 176-283, 405-457).

---

## High — the fix does NOT eliminate `AmbiguousMatchException` when an INTERMEDIATE ancestor hides the property and the leaf declares nothing

**File:** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:376-378`

```csharp
propertyInfo = cacheKey.ModelType.GetProperty(
    cacheKey.FieldName,
    BindingFlags.Public | BindingFlags.Instance | BindingFlags.FlattenHierarchy);
```

The two-step lookup only avoids the ambiguity when the *leaf* model type itself redeclares the property — that case is caught by the `DeclaredOnly` first step (line 370-372) and never reaches the fallback. When the leaf type declares nothing but an intermediate ancestor hid a base property with a `new` member of a different type, the `DeclaredOnly` step returns `null` and the fallback (which is not `DeclaredOnly` — `FlattenHierarchy` does not restrict instance members) searches the whole hierarchy, finds two same-named properties with different signatures, and throws.

`FlattenHierarchy` is a red herring here: for instance members it behaves identically to plain `Public | Instance`, so the fallback is effectively the same ambiguous lookup the PR set out to fix.

**Confirmed failure scenario** (verified by running it on the .NET 10 SDK in this repo):

```csharp
class Base   { public object Foo { get; set; } }
class Middle : Base   { public new int Foo { get; set; } } // intermediate hides
class Leaf   : Middle { }                                   // leaf declares nothing
```
- `typeof(Leaf).GetProperty("Foo", Public|Instance|DeclaredOnly)` → `null`
- `typeof(Leaf).GetProperty("Foo", Public|Instance|FlattenHierarchy)` → **throws `AmbiguousMatchException`**

Root cause: `RuntimeType.GetPropertyImpl` throws directly when there is more than one candidate and no `returnType`/index `types` are supplied — it never gets to the binder. Reflection keeps both `Middle.Foo (int)` and `Base.Foo (object)` in the candidate list because they hide by name *and signature* and the signatures differ. In a Blazor form this surfaces as an unhandled exception on `NotifyFieldChanged`/validation for that field — the exact crash tracked by the issue this PR closes, still reachable for this hierarchy shape.

The new test `ValidatesPropertyHiddenAtMultipleInheritanceLevels` does *not* cover this: `DeepDerivedModel` (line 423) redeclares `Tag` itself, so it is caught by the `DeclaredOnly` step and never exercises the ambiguous fallback. There is no test where the bound leaf inherits an intermediate-hidden property unchanged.

**Remediation:** replace the single ambiguous fallback with a walk up the base-type chain, taking the first (most-derived) `DeclaredOnly` match. `GetProperty(..., DeclaredOnly)` can never be ambiguous within a single declaring type, so this eliminates the throw for every hiding configuration. Verified working (returns `Middle.Foo (int)` for the case above):

```csharp
for (var type = cacheKey.ModelType; type is not null && propertyInfo is null; type = type.BaseType)
{
    propertyInfo = type.GetProperty(
        cacheKey.FieldName,
        BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly);
}
```

Rejected alternative: keeping the `FlattenHierarchy` fallback but wrapping it in `try/catch (AmbiguousMatchException)` — it suppresses the crash but then has to reimplement most-derived selection anyway, and would silently pick nothing on the exception path, so the chain walk is cleaner and deterministic.

---

## Low — dropping `Static` is an undocumented behavior change, and the description/implementation diverge

**File:** `src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs:370-378`

The original `cacheKey.ModelType.GetProperty(cacheKey.FieldName)` used the default flags `Public | Instance | Static | FlattenHierarchy`. Both new branches drop `Static`, so a public static property that was previously found and validated is now silently skipped. The new test `IgnoresStaticProperty` (test line ~146) codifies this as intended, but the PR's stated intent is only "eliminate `AmbiguousMatchException`" — the static behavior change is not mentioned anywhere in the change description.

Failure scenario: `new FieldIdentifier(model, "StaticValue")` for a `[Range] public static int StaticValue` previously produced a range validation message; after this change it produces none. In practice binding a form field to a static property is a fringe case (and arguably nonsensical for instance-based `FieldIdentifier` validation), so the impact is minimal and the change is defensible — but it should be called out as an intentional behavioral change rather than shipped implicitly under a bug-fix title.

**Remediation:** either state the static-property behavior change explicitly in the PR/commit description, or, if only ambiguity resolution was intended, keep parity by not narrowing the flag set beyond what the ambiguity fix requires (the base-chain walk above can include `Static` if preserving the old behavior is desired).

---

Net: the leaf-redeclare cases the tests exercise are handled correctly, but the fix is incomplete for the intermediate-ancestor hiding case (High), and it carries an unadvertised static-property behavior change (Low).
