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
- **State a rule that spans files once, then point at it.** Give the rule one home, and have every
  other site say "see X". If each site explains the rule again, the explanations go stale together.
- **Check a claim before you write it.** A comment that names a mechanism, such as what a check
  catches, what a call refuses or how a type behaves, has no compiler behind it. Confirm it in the
  code or by running it, or write less. Prefer a guard or a test that makes the claim checkable.
  When you change behavior, search for the comments that describe it.

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
  phrase: "A snapshot of…". A Boolean member opens with "Whether…" or "Returns whether…". Go opens
  with the declared name: "Find returns…". Python docstrings use the imperative: "Return the…".
- **Cost, mechanism and reasons come after the what.** Put them in a later sentence, a later
  paragraph, or the format's remarks section. Don't fold them into the summary's first sentence.
- **Put a rule on the member that keeps it.** A promise about what a method does goes on that
  method, not on the types it uses.
- **Use the format's fields for what they are for.** Inputs go in the parameter field, results in
  the return field, and failures in the error field: `<param>`, `<returns>` and `<exception>` in C#,
  `@param`, `@returns` and `@throws` in JSDoc, `Args:`, `Returns:` and `Raises:` in Python, and
  `# Errors` in Rust. A format without fields, such as Go's, gives each its own sentence after the
  summary.
- **Document each member of an interface.** Don't rely on the interface's summary to describe its
  members. The same applies to traits and protocols.
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

## Wording

These rules borrow the parts of ASD-STE100 Simplified Technical English that make text easier to
read without making it much longer. Its approved dictionary and its ban on every "-ing" word are
left out.

- **One fact per sentence, of at most about 25 words.** Split a long sentence where its facts
  change.
- **Give every sentence after the first an explicit subject.** A doc comment's first sentence may
  open with a verb, as above. The sentences after it say what they are about: "It keeps the lock
  until the batch commits", not "kept until the batch commits". An inline comment may use the
  imperative instead: "Release the connection between batches, so other requests take turns."
- **Use the active voice: say who does it.** "The cache then does not replace a newer entry with an
  older one", not "a newer entry is not overwritten by an older one".
- **Keep the small words.** Don't drop articles and verbs to save space. "The row from the last
  database read or write", not "its row as the database last showed it".
- **Use a one-word verb, not a phrasal verb.** "Releases", not "gives back". "Continues", not "goes
  on". "Takes it again", not "takes it straight back".
- **Avoid an "-ing" word that could be a noun, a verb or an adjective.** "The current imports",
  not "the imports running". "A queue with a flush in progress", not "a queue flushing". An "-ing"
  word with one clear reading is fine: "Returns whether the queue is flushing."
- **Say how sentences connect, with "so", "then", "if" or "because".** Don't chain clauses with
  colons and semicolons into one long sentence.
- **Use one word for each concept, and give each word one meaning.** Use the terms in the project's
  glossary. Once something is the "retry budget", don't also call it "its allowance" or "its
  remaining tries".
- **Repeat the noun when "it" or "its" could mean more than one thing.** "Keeps its size at its
  limit, the value its parent set" has three "its". Name what each one means.
- **Don't use a glossary noun as a verb where the noun could also be meant.** Some terms are also
  everyday verbs: record, mark, check, lock. Pick another verb near them. "Writes the audit records
  and stores that the job has seen them", not "writes the audit records and records them as seen".
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
