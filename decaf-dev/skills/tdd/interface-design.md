# Interface Design for Testability

Good interfaces make testing natural:

1. **Accept dependencies, don't create them**

   ```
   // Testable — dependency is injected
   processOrder(order, paymentGateway)

   // Hard to test — dependency is internal
   processOrder(order):
       gateway = new StripeGateway()
   ```

2. **Prefer returning results over implicit side effects**

   When the operation is a computation, return a result rather than mutating input:

   ```
   // Testable — assert on the return value
   calculateDiscount(cart) -> Discount

   // Harder to test — must observe mutation
   applyDiscount(cart) -> void:
       cart.total -= discount
   ```

   When side effects are the point (saving to a database, sending a notification), make them explicit and observable through the interface — e.g., return a confirmation, accept an output sink, or expose a way to query the result.

3. **Small surface area**
   - Fewer methods = fewer tests needed
   - Fewer params = simpler test setup

## Language-specific notes

- **C#**: Explicit interfaces (`IPaymentGateway`) are the natural seam for DI and testability. Constructor injection is idiomatic.
- **Go**: Define interfaces where they're consumed, not where they're implemented. Keep them small — one or two methods. Accept interfaces, return structs.
- **Rust**: Use traits for abstraction boundaries. Prefer generics (`impl Trait`) over trait objects (`dyn Trait`) when the concrete type is known at compile time. For simple callbacks, a closure (`Fn`/`FnMut`) is often simpler than a trait.
