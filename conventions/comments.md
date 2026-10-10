# Writing comments

The rules for comments in code, doc comments and inline comments alike, in every language. Agents
that write code follow them, and reviewers check comments against them.

A project can add to these rules in `.decaf/conventions/comments.md` at its repository root: a
glossary, a line width, and local rules. Read that file when it exists. Where it contradicts this
file, the project file wins. See [Project overlay](#project-overlay).

## What a comment is for

- **Explain why, not what.** A comment says why the code is written the way it is, or makes complex
  logic easier to follow. When the code already says it, leave the comment out.
- **Describe the code as it is now.** A comment never tells how the code got here. That belongs in
  the commit message, where `git blame` finds it. See [No history](#no-history).
- **State the reason, not a reference to it.** Never cite a decision number, a spec section, a
  phase, an option name or a ticket ID. Those mean nothing to a later reader and go stale once the
  work they name ships. Write the reason itself. The link to the decision belongs in the commit
  message and the work item.
- **State the constraint, don't argue for it.** Write the constraint that holds, not the
  alternative that lost. Rejected alternatives and the reasoning that led here belong in the commit
  message or the work item. A comment of the form "X rather than Y, because Y would…" is nearly
  always this mistake.
- **Past about 10 lines, ask whether code should carry the constraint.** A long comment that
  explains a subtle interaction often means a type, a guard or a narrower interface should make
  that interaction impossible. Turn the prose into a mechanism where you can. A shorter comment is
  the fallback.
- **State a rule once, on the member that keeps it.** Every other site gives one clause of what the
  rule does and a cross-reference to that member, without the reasoning. If each site explains the
  rule again, the explanations go stale together. When no member that the other sites can see holds
  the rule in its doc comment, point at the type. Then file a work item for a code change that gives
  the rule such a home.
- **Check a claim before you write it.** A comment that names a mechanism, such as what a check
  catches, what a call refuses or how a type behaves, has no compiler behind it. Confirm it in the
  code or by running it, or write less. Prefer a guard or a test that makes the claim checkable.
  When you change behavior, search for the comments that describe it.
- **Back a fact about a vendor or a tool with a source.** The code cannot show how a vendor's server
  or a tool behaves. Keep such a fact only with a link to the vendor's docs, or to the vendor's
  source at a fixed commit when the docs do not say. A test that pins the fact also backs it, and
  the comment then names the test instead of a link. Drop the fact otherwise. A source counts as
  checked only when the writer fetched it and found the line that backs the claim. A claim checked
  any other way goes to a work item to check. Give each fact one link: the vendor's docs where they
  state it, and a source line range only where they do not. A pointer to another comment counts
  only when that comment has a source.
- **Back a figure.** A figure that comes from the code shows its arithmetic or names the test that
  pins it. A measured figure names the file that records the measurement. Drop any other figure.
- **Keep a reason that guards the code, even without a source.** When the two rules above would
  drop a reason that keeps a maintainer from undoing the code, keep one clause of what the code
  relies on. File the claim in a work item to source or pin it.

## No history

Write every comment for a reader who sees the code for the first time and knows nothing of how it
got here. A comment that only makes sense to someone who knows the code's history breaks this rule,
whatever its words. Five kinds of comment break it most often. The signal words are examples, so
judge the meaning, not the word.

1. **A change, not what exists.** "Added", "replaced", "now uses", "changed to", "new", "updated".
   `// Added mutex to fix race condition` becomes `// The mutex serializes cache access from
   concurrent requests.`
2. **A comparison with code that is gone.** "Instead of", "rather than", "previously", "replaces",
   "unlike the old", "no longer". `// Unlike the old approach, this is thread-safe` becomes
   `// Each goroutine gets its own state, so this is thread-safe.`
3. **Where to put code.** "After the call", "insert before", "at line 425". Delete these. The diff
   already shows where the code goes.
4. **A plan, not behavior.** "TODO", "will", "eventually", "temporary", "workaround until". Delete
   the comment, do the work now, or state the constraint that holds today:
   `// Temporary workaround until API v2` becomes `// API v1 cannot filter, so the client filters.`
5. **The author's choice, not the reason.** "Intentionally", "deliberately", "chose", "decided",
   "by design", "we opted". Keep the technical reason and drop the decision:
   `// We decided to cache at this layer` becomes `// The cache sits here because every request
   for a page passes through this layer.` If the comment still makes sense without the choice
   word, delete the word.

The rule covers how the code got here, not the order of events that the code handles. "A session
created before the user signs in has no owner" describes behavior. A regression test may say that a
case once caught a fault, as [Tests](#tests) says.

The same word can pass or fail:

| Comment | Verdict | Reason |
|---|---|---|
| `// Now handles edge cases properly` | Fails | "Properly" says the code was wrong before. |
| `// Now blocks until the connection is ready` | Passes | "Now" names a moment at run time, not in the code's history. |
| `// Fixed the null pointer issue` | Fails | It describes a fix, not behavior. |
| `// Returns null when the key is not found` | Passes | It describes behavior. |

## Doc comments

A doc comment is the comment on a declaration that the language's tools read: XML doc comments in
C#, Javadoc, JSDoc and TSDoc, `///` in Rust, the comment above a declaration in Go, and docstrings
in Python. These rules apply to each of them. Where the language's own convention prescribes a
form, that convention wins.

- **The summary says what the type is or what the member does, first.** Interfaces and methods
  open with a verb: "Provides…", "Returns…", "Records…". Types that hold data open with a noun
  phrase: "A snapshot of…". Properties, fields and enum members open with a noun phrase too. An enum
  member that names an event takes a noun phrase for the event: "A drop of the connection". A
  Boolean member opens with "Whether…" or "Returns whether…", and "Whether" stays for Booleans. Go
  opens with the declared name: "Find returns…". Python docstrings use the imperative: "Return
  the…". Test classes and test methods follow [Tests](#tests) instead.
- **In a format with a return tag, keep a summary that opens with "Returns" to one short clause.**
  The conditions and the absent-value clause go in the return tag, such as `<returns>` in C# or
  `@returns` in JSDoc. The remarks do not restate either.
- **Cost, mechanism and reasons come after the what.** Put them in a later sentence, a later
  paragraph, or the format's remarks section. Don't fold them into the summary's first sentence.
- **Put a rule on the member that keeps it.** A promise about what a method does goes on that
  method, not on the types it uses. A method may state what its callers must do, as part of its
  contract, and the callers then do not repeat it.
- **Use the format's fields for what they are for.** Inputs go in the parameter field, results in
  the return field, and failures in the error field: `<param>`, `<returns>` and `<exception>` in C#,
  `@param`, `@returns` and `@throws` in JSDoc, `Args:`, `Returns:` and `Raises:` in Python, and
  `# Errors` in Rust. A format without fields, such as Go's, gives each its own sentence after the
  summary.
- **Document each member of an interface.** Don't rely on the interface's summary to describe its
  members. The same applies to traits and protocols.
- **Let a block of constants share one comment** when each constant's name and value already say
  what it is, as with rule ids or field names. The comment above the block says what the block
  holds. A constant gets its own doc comment only when it says more than its name. A shared comment
  covers only constants with no blank line between them. A comment pass may remove the blank lines
  between such constants.
- **Give a private member a doc comment only when its name misleads, or when a rule lives on it.**
  The same holds for the members of a private nested type.
- **Leave an override or an interface implementation without a doc comment, unless it narrows or
  changes the base member's contract.** Readers find the contract on the base member. When the
  member does differ, its comment says what it does in one clause, then states the difference.
- **Put a blank line before each doc comment that sits above its declaration**, except before the
  first member after an opening brace.
- **Split a long summary into paragraphs**, one idea each.
- **Write for the editor.** Most doc comments are read as plain text where they stand. Keep markup
  to the fields above, cross-references and inline code. Write a list of items as sentences. A
  project that publishes rendered docs can relax this in its overlay.
- **Say what an absent value means in one short clause, at the end:** "…, or null when no account
  has the email." Use the language's word: null, `None`, `nil`, `undefined`. When the absent value
  also means nothing was done, add a second sentence: "…, or null when the file had changed.
  Nothing was written then."
- **Say what a value holds.** When a string or a number stands for something, name its form: "the
  ids of the commits, each the full hash in lowercase hexadecimal", not "commits".
- **Define a domain term once, where readers first meet it.** Explain the term in the type's doc
  comment, so its members can use the term without the definition. A term the whole project uses
  goes in the overlay's glossary.

### C#

- **A positional record gets a one-line summary above its `<param>` tags.**
- **Use `//` for a comment that a block of members shares, and `///` for a member with its own
  rule.** A `///` comment attaches to the first member below it alone.
- **Name an overload by its parameter types in a `<see cref>`**, as in
  `<see cref="Check(NotePath, NoteFile)"/>`. When the build writes a documentation file, the
  compiler warns on a `<see cref>` that names nothing, and on one that names an overloaded method
  without its parameters. In a file that more than one project compiles, write `<c>` for a type
  that only one of those projects holds.
- **`<inheritdoc cref="…"/>` may stand for a comment that another member already holds.**

## Tests

These rules cover the doc comments on test classes and test methods, and the comments in tests.

- **A test class summary opens with "Covers"** and names the behavior under test in one sentence. A
  test that scans the repository for an invariant opens with "Checks that". Neither lists the
  tests.
- **A test method's summary states the setup and the reason for it**, in the present tense and with
  no verb opener. It reads on its own, without the test above it. It keeps only what the test's
  name does not say, so delete a summary that restates the name.
- **Don't narrate the assertions or repeat an assertion's message.** When a test class's doc comment
  defines labels that assertion messages cite, that comment is the one home of those labels and
  keeps its length.
- **A test that pins a case of a production rule names the case in one clause.** It
  cross-references the member that keeps the rule, without that member's reasoning.
- **A regression test may say that a case once caught a fault**, without the story of the fault.
- **Rename a test whose name conflicts with the glossary.** Other identifiers keep their names and
  get a qualified glossary row, as [Wording](#wording) says, but a test name costs little to change.
  Until the rename, the comments beside the test use the glossary term.

## Wording

These rules borrow the parts of ASD-STE100 Simplified Technical English that make text easier to
read without making it much longer. Its approved dictionary and its ban on every "-ing" word are not
part of these rules.

- **One fact per sentence, of at most about 25 words.** Split a long sentence where its facts
  change. One colon may introduce a list of parallel items. A list of conditions gives each
  condition its own sentence.
- **Give every sentence after the first an explicit subject.** A doc comment's first sentence may
  open with a verb, as above. The sentences after it say what they are about: "It keeps the lock
  until the batch commits", not "kept until the batch commits". An inline comment may use the
  imperative instead: "Release the connection between batches, so other requests take turns." A
  doc comment may use the imperative for an instruction to the maintainer or to a caller: "Change
  this version when the rules change", or "Call it after `Initialize`."
- **Use the active voice: say who does it.** "The cache then does not replace a newer entry with an
  older one", not "a newer entry is not overwritten by an older one". Use the passive only when the
  actor is unknown or does not matter, as in an error message: "The file could not be read."
- **Keep the small words.** Don't drop articles and verbs to save space. "The row from the last
  database read or write", not "its row as the database last showed it".
- **Use a one-word verb, not a phrasal verb.** "Releases", not "gives back". "Continues", not "goes
  on". "Takes it again", not "takes it straight back". A phrasal verb that is an established
  technical term, or that an identifier holds, is fine: "looks up", "rounds down", "rolls back".
- **Avoid idioms with two readings.** "In any case" can also mean letter case. Write "in any letter
  case" for that, and "whatever happens" for the other. Don't follow an "unless" clause with
  "otherwise".
- **Avoid an "-ing" word that could be a noun, a verb or an adjective.** "The current imports",
  not "the imports running". "A queue with a flush in progress", not "a queue flushing". An "-ing"
  word with one clear reading is fine: "Returns whether the queue is flushing."
- **Say how sentences connect, with "so", "then", "if" or "because".** Don't chain clauses with
  colons and semicolons into one long sentence.
- **Use one word for each concept, and give each word one meaning.** Use the terms in the project's
  glossary. Once something is the "retry budget", don't also call it "its allowance" or "its
  remaining tries". When an identifier, a database column or a published doc already uses a
  glossary word in another sense, the glossary gives that sense a qualified row, such as "retry
  slot" beside "slot". Comments then use the qualified term, and the identifiers keep their names.
  The bare word keeps the sense of its own row. A word's one meaning binds only where its glossary
  sense could be meant, so an everyday sense is fine elsewhere.
- **Repeat the noun when "it" or "its" could mean more than one thing.** "Keeps its size at its
  limit, the value its parent set" has three "its". Name what each one means.
- **Don't use a glossary noun as a verb where the noun could also be meant.** Some terms are also
  everyday verbs: record, mark, check, lock. Pick another verb near them. "Writes the audit records
  and stores that the job has seen them", not "writes the audit records and records them as seen".
  The verb is fine in the glossary's own sense, such as "marks" for setting a mark.
- **Common words over coined ones.** "The current run", not "the run going". "In progress", not
  "going". "Searched", not "looked through".
- **American English**, unless the overlay says otherwise.
- **Wrap comments at the width of the code around them**, unless the overlay sets a width.

## Project overlay

`.decaf/conventions/comments.md` holds what only one project needs. It is committed with the code.
It usually holds:

- **A glossary**: a table of the domain terms that comments use with one fixed meaning. Add a term
  the first time a comment needs one.
- **A line width** for comments.
- **Scope**: which languages the doc-comment rules cover, and whether the project publishes
  rendered docs.
- **Local rules**: additions to this file, or exceptions to it.
- **Examples** from the project's own code.

```markdown
# Comments in <project>

Comments wrap at 120 characters. The doc-comment rules cover C# only.

## Glossary

| Term | Meaning |
|---|---|
| Tenant | One customer's isolated data and settings, named by its slug. |
```

## Examples

An interface summary that packs what, how and cost into one sentence, and never says what the
interface is for:

```typescript
// Before
/** What uploading is doing per bucket, as the uploader keeps it in memory, so reading it makes no network call. */

// After
/**
 * Provides the current upload activity of each bucket.
 *
 * @remarks The uploader keeps this in memory, so `read()` makes no network call.
 */
```

A rule placed on the type instead of the member that keeps it:

```csharp
// Before, on the record
/// <summary>How a sync ended. A sync never throws: a failure is logged and reported as <see cref="Failed"/>.</summary>

// After, on the record
/// <summary>How a sync ended.</summary>

// After, on SyncAsync
/// <returns>How the sync ended. A sync that fails is logged and returned as <see cref="SyncResult.Failed"/>, not thrown.</returns>
```

A long sentence with an implied subject, passive verbs and colon-chained clauses, rewritten with
the wording rules:

```go
// Before
// Store records the entry and keeps the import shares with it. A tenant that stops importing keeps its share at its
// whole size, the count its import reached, until no tenant is importing, so the shares added up do not fall when one
// tenant finishes first: an import that fit in one batch never recorded a target to take it from.

// After
// Store saves the entry and updates the tenant's import share to match.
//
// When a tenant finishes its import, its import share counts it as fully done, sized by the count its import reached,
// because an import that fit in one batch never stored a target. The tenant keeps this share until no tenant has an
// import in progress. So the summed progress does not drop when one tenant finishes before another.
```

A Python docstring in the imperative, with the absent value in a short clause at the end:

```python
def find_account(email: str) -> Account | None:
    """Return the account registered with this email, or None when no account has it."""
```
