# subagent agent-a6fb1daf3873a43bc

Based on my verification, I can now score this issue.

**Summary of findings:**

1. **Revert PR exists and confirms the issue**: PR 67712 (merged after 67075) explicitly reverts this commit with the exact same criticism: "FlattenHierarchy doesn't flatten instance members, so hiding at an intermediate base type still throws."

2. **Expert comment on the PR**: Youssef1313 explicitly noted on PR 67075: "FlattenHierarchy is only relevant for statics IIRC. And this code can still throw if the previous call returned null and we get into here with some shadowing member in a base type."

3. **Test coverage gap verified**: The added tests all use models where properties are shadowed at the LEAF level (DeepDerivedModel redeclares Tag on itself), or inherited without intermediate shadowing (DerivedModelWithInheritedOnly). None test the specific failure case: a property shadowed at an intermediate level that is NOT redeclared on the leaf type, which would cause:
   - DeclaredOnly to return null (not on leaf)
   - FlattenHierarchy+Instance to throw AmbiguousMatchException (finds both intermediate and base declarations)

4. **Technical claim verified**: The claim that FlattenHierarchy only affects static members for instance-member lookups is confirmed by both the revert PR and expert commentary.

100

The issue is definitely real and critical. The revert PR directly confirms the fix is broken, and the exact scenario described is guaranteed to fail in practice when a property is shadowed at an intermediate type but not redeclared on the leaf type.
