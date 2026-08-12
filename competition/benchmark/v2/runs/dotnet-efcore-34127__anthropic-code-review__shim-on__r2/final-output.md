The final agent confirmed finding #1 independently (same operator-gate defect, same missing test shapes) and adds one point worth appending:

### 4. [Minor] The new helpers bypass the provider extension points

**`src/EFCore.Relational/Query/SqlNullabilityProcessor.cs:595-648`**

`DropNotNullChecks` and `NullPropagatedOperands` are `static` local functions that read `OperatorType`, `IsNullable`, `InstancePropagatesNullability`, and `ArgumentsPropagateNullability` directly, rather than dispatching through the `protected virtual VisitSqlBinary` / `VisitSqlUnary` / `VisitSqlFunction` / `VisitCustomSqlExpression` methods this class exposes for providers (class doc at `:10-17`). A provider whose operator or custom expression type has different null-propagation behavior cannot influence this optimization. The `SqlFunctionExpression` branch at least mirrors the metadata contract used by `VisitSqlFunction` (`:1506-1543`) faithfully, and unrecognized expression types degrade safely (node added, no recursion) — so this is a design note, not a defect on its own. It does compound #1: the one branch that both contradicts the documented invariant *and* is unreachable by providers is the `SqlBinaryExpression` branch.

Nothing changes in the rest of the review. Summary: one critical correctness regression (#1, reproduced against builds of both commits), a test-coverage gap that let it through (#2), and two minor notes (#3, #4).
