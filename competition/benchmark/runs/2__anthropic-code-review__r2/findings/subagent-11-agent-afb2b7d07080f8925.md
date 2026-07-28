# subagent agent-afb2b7d07080f8925

## PR #67075 Summary

**Title:** Fixed AmbiguousMatchException in DataAnnotationsValidator for Hidden Members

**Linked Issue:** #27075

**Status:** Merged

### Purpose
This PR fixes a runtime bug in Blazor's DataAnnotationsValidator where validating models with hidden properties (derived class properties that shadow base class members using the `new` keyword) would throw an `AmbiguousMatchException`. The fix ensures the validator correctly resolves properties in inheritance hierarchies where members are hidden/shadowed.

### Files Changed

1. **src/Components/Forms/src/EditContextDataAnnotationsExtensions.cs** (+10, -1)
   - Modified the `TryGetValidatableProperty` method's reflection logic to use explicit `BindingFlags` when calling `GetProperty()`. The fix employs a two-pass approach: first tries `BindingFlags.DeclaredOnly | BindingFlags.Public | BindingFlags.Instance` to find the derived property, and if that returns null, falls back to `BindingFlags.FlattenHierarchy | BindingFlags.Public | BindingFlags.Instance` to find inherited properties.

2. **src/Components/Forms/test/EditContextDataAnnotationsExtensionsTest.cs** (+158, -0)
   - Added 8 new test cases covering:
     - Validation of hidden properties without exceptions
     - Property caching with hidden properties
     - Exact name matching
     - Inherited properties from base classes
     - Properties hidden at multiple inheritance levels
     - Unattributed hidden properties
     - Static properties
     - A comprehensive property-sequence validation test

### Key Behavioral Changes
- The validator now correctly resolves properties when a derived class hides a base class property with the same name and different type
- Avoids `AmbiguousMatchException` by prioritizing derived-class declarations over base-class members
- Maintains proper validation of DataAnnotations attributes on hidden properties
- Handles edge cases like multiple inheritance levels and unattributed shadows

### Root Cause
The original code used `Type.GetProperty(string name)` without binding flags, which returns multiple matches when both base and derived types define a property with the same name, causing ambiguity.

### Solution Approach
Implements targeted reflection with explicit `BindingFlags` to eliminate ambiguity—first seeking the declared property on the derived type, then falling back to the inheritance hierarchy if needed.
