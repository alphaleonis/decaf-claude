# subagent agent-a81dbf487c74842bc

## Analysis

I've identified one critical bug in the timeout error handling logic:

**The Bug: Exception Propagation When Timeout Fires**

When a timeout occurs, the code calls `stream.destroy()` which cancels the underlying reader. This causes the pending `iterator.next()` to throw an error (the stream cancellation error from the Web Streams API). However, this exception propagates out of the try block *before* the `if (timedOut)` check can execute.

Here's the problematic flow:

```
1. startTimer() sets timeout
2. await iterator.next() is pending
3. Timeout fires: timedOut = true, stream.destroy() is called
4. stream.destroy() → this.reader.cancel() → pending reader.read() rejects
5. iterator.next() throws the cancellation error
6. Exception is caught by try-finally (not a catch block)
7. Finally block runs: clearTimer(), iterator.return()
8. Exception continues to propagate BEFORE the if (timedOut) check
9. Consumer receives cancellation error, not StreamIdleTimeoutError
```

The intention is clear from the error class and the comment ("Timer runs only while awaiting the next chunk"), but the implementation fails to throw the intended `StreamIdleTimeoutError` when a timeout actually occurs.

**Fix**: Wrap `iterator.next()` in an inner try-catch to suppress the cancellation error when `timedOut` is true, allowing the outer `if (timedOut)` check to execute:

```typescript
let result;
try {
  result = await iterator.next();
} catch (e) {
  if (timedOut) {
    break; // Suppress the cancellation error, let finally run, then throw StreamIdleTimeoutError
  }
  throw e; // Re-throw non-timeout errors
}
```

---

```json
[
  {
    "file": "extensions/copilot/src/platform/networking/common/fetcherService.ts",
    "line": 42,
    "severity": "High",
    "category": "error-handling",
    "issue": "[BUG_LOGIC] When timeout fires and stream.destroy() is called, the cancellation error from iterator.next() propagates before the if (timedOut) check runs, causing the consumer to receive a stream cancellation error instead of the intended StreamIdleTimeoutError. Error handling code expecting StreamIdleTimeoutError will not catch the actual exception.",
    "fix": "Wrap the 'await iterator.next()' call in an inner try-catch block. If an error is caught and timedOut is true, break from the loop to allow the finally block and if (timedOut) check to execute. If timedOut is false, re-throw the error to preserve non-timeout errors.",
    "confidence": 75,
    "pre_existing": false
  }
]
```

## Considered But Not Flagged

- **Timer already fired before clearTimer()**: When a setTimeout callback executes, the timer reference is automatically cleared by the runtime. The explicit clearTimeout() in the code is safe and idiomatic; no issue here.
- **iterator.return() in finally**: If iterator.return() throws, the exception would escape. However, DestroyableStream's generator has only a finally block with simple operations (releaseLock, assignment) that shouldn't throw. Not flagged as it's an edge case not specific to this change.
- **Race between consumer break and timeout**: If a consumer intentionally breaks while a timeout is pending, the finally block clears the timer and the timeout won't be reported. This is correct behavior (no error should be thrown for intentional breaks). Not a defect.
