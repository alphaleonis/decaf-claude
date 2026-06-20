# When to Mock

Mock at **system boundaries** only:

- External APIs (payment, email, etc.)
- Databases (sometimes - prefer test DB)
- Time/randomness
- File system (sometimes)

Don't mock:

- Your own classes/modules
- Internal collaborators
- Anything you control

## Designing for Mockability

At system boundaries, design interfaces that are easy to substitute in tests:

**1. Use dependency injection**

Pass external dependencies in rather than creating them internally:

```
// Easy to test — inject a fake/stub
processPayment(order, paymentClient):
    return paymentClient.charge(order.total)

// Hard to test — dependency is hardcoded
processPayment(order):
    client = createStripeClient(config.apiKey)
    return client.charge(order.total)
```

**2. Prefer specific interfaces over generic ones**

Define specific operations instead of one generic catch-all:

```
// GOOD: Each operation is independently substitutable
interface OrderAPI:
    getUser(id) -> User
    getOrders(userId) -> []Order
    createOrder(data) -> Order

// BAD: Substitution requires conditional logic in the test double
interface OrderAPI:
    fetch(endpoint, options) -> Response
```

The specific approach means:
- Each test double returns one specific shape
- No conditional logic in test setup
- Easier to see which operations a test exercises

## Language-specific notes

- **C#**: Use interfaces for boundary abstractions. Moq or NSubstitute are fine for boundary mocks — avoid mocking concrete classes.
- **Go**: Define small interfaces at the consumer site (not the provider). A test double is just a struct that satisfies the interface — no framework needed.
- **Rust**: Use traits to define boundaries. Pass `impl Trait` or `dyn Trait` parameters. For simple cases, accept a closure or function pointer instead of a full trait.
