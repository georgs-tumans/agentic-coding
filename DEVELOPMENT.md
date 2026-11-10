# Global working rules

These apply across every project. A repo's own `CLAUDE.md` can add to these; where the two
conflict, the repo-specific file wins for that repo.

## Philosophy

- **Production-grade by default.** Optimize for stability, security, and correctness over speed
  of typing. Treat code as long-lived unless it's explicitly stated to be throwaway.
- **Minimalism.** Less code is fewer bugs. Use the simplest logic that solves the actual problem,
  and write the three lines of native code instead of adding a dependency for them.
- **Write for the next engineer.** Prioritize readability over cleverness. Prefer native language
  features over a library. Make code self-explanatory through naming and structure.

## Architecture and style alignment

- **Match the codebase you're in.** Adhere strictly to the established coding style, conventions,
  and architectural paradigms already present. When expanding functionality, extend the existing
  patterns and system design rather than introducing a non-conforming approach.
- **Propose divergence, don't apply it.** When you identify an improvement or an alternative
  paradigm that departs from those patterns, raise it explicitly as a suggestion for review first
  instead of implementing it directly.
- **SOLID.** When planning refactorings or designing features/software from scratch keep the SOLID
  principles in mind. Do not employ patterns or extra structuring by default for the sake of itself,
  either ask the user or consider the scope from available data such as PPA documents to weigh the
  necessity of adding pattern overhead. Keep the best practices and patterns of the given language in mind.

## Comments

- Default to small and purposeful comments. Let names and structure say WHAT the code does, and 
  never write a comment that restates the code — it's noise, not documentation ("// loop through users",
  "// return the result").
- Reserve more detailed comments for a genuine edge case: a hidden constraint, a non-obvious invariant, the
  reason behind a chosen value (a limit, interval or default), a workaround for a specific bug, a
  reason a naive approach would be wrong, or behavior that would otherwise surprise a reader.
  Delete any comment whose removal wouldn't confuse anyone.
- Keep the comments you do write to one line where possible — one point, stated once, instead of a
  multi-paragraph block.
- Put task, ticket, and PR context in the commit message, never in a comment ("fixed for issue
  #123", "added for the X feature") — in the code it rots as the code evolves.
- Where available and necessary (complex business logic, unclear why something is done the way it is,
  specific pattern due to invocations from multiple possible callers, etc.) comment concrete
  chapter/subchapter identifiers from PPA or other specification document.
- Avoid commenting object/type properties instead opting for descriptive names when creating new ones
  (unless a comment would really help understand an ambiguous situation). 
- Never restate property/function/block name in the comment if it is right above the name:
  wrong - // queueAttendancePrivileges are the territories where stuff happens...
  correct - // Territories where stuff happens...

## Code organization

- In a long file, group logically related code into named, collapsible regions so it can be
  navigated and folded in an IDE. Use the syntax the actual language/toolchain supports —
  `#region Name` / `#endregion` in C#, `#pragma region Name` / `#pragma endregion` in MSVC-flavor
  C++, `// #region Name` / `// #endregion` for editor-based folding in JS/TS and similar — and
  never invent one a language doesn't have.
- Add regions only once a file is long enough that sections genuinely help. Don't wrap a short
  file with one obvious purpose in a single region — that's structure for its own sake.
- Check the toolchain first in C/C++: GCC and Clang warn on unknown pragmas under `-Wall`
  (`-Wunknown-pragmas`), so `#pragma region` on a GCC target built with `-Werror` will break the
  build. If a codebase compiles on both MSVC and GCC, confirm the warning is suppressed or skip
  regions there — never guess.
- Split a file that has outgrown itself instead of papering over it with regions. If a file needs
  ten regions to stay readable, treat that as the signal to split it into files.

## Planning approach during plan mode

- **Concise and clear explanations.** Do not overload plans with wordiness, very deep context and
  too many details. Just enough to understand what, how and why.
- **Simple to understand.** Prefer simple terms in the writeup, utilize mermaid diagrams to illustrate
  current or potential flows, name exact functions/calls in code traces if relevant.
- **Logical plan file names.** Instead of generating random names for the plan files, build the name
  so that it reflects the job being done so these files can be distinguished and recognized without 
  opening them first. Also use redmine task identifiers in the name if they are available (you can aks user).
- **Reference documentation if available.** If documentation is available, reference it when describing 
  changes or existing functionality flows in plans. Important - use document heading numbering system
  when referencing and do not use plaintext file row numbers - that doesn't help users at all. You
  can also include short citations from the available documentation when proposing changes.

## Engineering discipline

- **Confirm integration, not just implementation.** A capability with no caller in the code that
  actually ships is not a working feature, no matter how correct the implementation or how green
  the unit test. Before claiming something works, `grep` for its call site in the real execution
  path instead of assuming one exists.
- **Look it up before reasoning about it.** For anything owned by someone else — a library, an
  API, a protocol, a spec, a datasheet, a piece of physics — read the actual documentation or
  source first; reasoning from plausibility produces confident wrong answers. Prefer an
  authoritative oracle (official schema, spec, vendored source) to your own derivation whenever
  one exists. Check a remembered API property against the pinned version in use, and whenever a
  current alternative exists, use it instead of a deprecated method, library or API.
- **Back every claim with evidence.** "It should work now" is not a result. After a fix, show the
  output that proves it changed; test a suspected cause before reporting it as the cause. If the 
  check is very involved and potentially token-expensive (such as running a browser to run a webapp)
  ask the user beforehand.
- **Confirm a result reproduces before quoting it.** One measurement can be noise, luck, or an
  unrepresentative path; establish whether a number is reproducible before presenting it as a
  finding.
- **Fail closed, and report only what actually happened.** A component that refuses to start with
  a clear reason beats one that silently degrades and reports success — the failure mode that
  looks healthy is the dangerous one. Never log or report an action that was not performed.
- **Keep the goalposts fixed.** Never loosen a threshold, a gate, or a check specifically to make
  a stuck experiment pass. A refusal from a well-designed check usually means the experiment or
  the input was inadequate, so fix that rather than the check.
- **Read existing context before re-deriving it.** Check for a handoff doc, changelog, or prior
  decision before re-solving something already settled. Don't re-audit work already marked done
  without a specific reason to doubt it.

## Testing

- **Ask whether tests are wanted before writing any.** Testing is decided per workspace, not
  assumed. The first time testing comes up in a repo, ask whether tests are in scope there and
  which framework it uses — unless the repo already has a test suite or its own `CLAUDE.md` answers
  it or there are available skills defining the testing approach in the given framework/language
  (the azugo-framework skill for instance), in which case follow that. Once answered, the answer
  holds for the rest of that workspace's work; don't re-ask on every task.
- **Where tests are in scope, work test-first (TDD).** Write the test cases first and run them to
  confirm they fail for the expected reason before writing any implementation. Then write the
  minimal implementation that makes them pass. Every piece of functional code lands with a
  corresponding test that existed before it.
- **Make each test assert real behavior.** Write the test against what the code MUST DO, then make
  the code satisfy it — never loosen a test to turn it green. A test that can't fail is worse than
  no test. When practical: establish the precondition (show it fails without the fix), assert the
  negative case too, and mutation-test guards you add (break them on purpose and confirm the test
  fails for the right reason).
- **Run the suite, not just the new test.** Before reporting a change done, run the tests that
  cover the affected code and report failures with their output, including ones that were
  already failing before your change.
- **Read checked behavior from the code; never hardcode it in the test.** Read a value the code
  owns (a limit, interval, default, name or route) from its production symbol, exposed as
  `internal` (or the language's test-visible equivalent) if needed, and put the reason for the
  value in a comment on that constant. Don't copy the logic under test into the test either: no
  duplicated configuration or registrations, no exemption lists taken on trust, no fixture values
  that equal a type's default. Test a boundary at the boundary and one step past it. Have a
  convention or scan test discover its set (projects, controllers, files) and assert it found
  something. Use a literal only where it is the specification: an external contract such as a
  wire format, a header another system sends, a file format or user-facing text.

## Quality control, before and during writing code

- **Think before writing.** Dry-run the logic mentally first: null/empty inputs, race conditions,
  timeouts, off-by-one boundaries, what happens on the error path.
- **Hunt for the bug, not just the feature.** Explicitly check the proposed solution for security
  vulnerabilities (injection, unsafe deserialization, path traversal, auth bypass) and logic flaws
  before presenting it as finished.
- **Keep secrets out of code, logs and history.** Read credentials, tokens and keys from
  configuration or a secret store; never hardcode, log, echo or commit them. If one is already
  committed, flag it — deleting it in a later commit doesn't remove it from history.
- **Handle errors appropriately for where the code runs.** Validate at trust boundaries (user
  input, external APIs, network responses). Don't add defensive checks for conditions the
  surrounding code makes structurally impossible — rely on those guarantees; such checks are
  noise, not safety.

## Git discipline

- When committing is in scope (asked for, or the repo's `CLAUDE.md` says so), make small,
  logically-scoped commits — commit each coherent piece as it lands rather than batching them.
- Put every feature or fix on its own new branch rather than committing it to the default branch.
  Name it `feat/<redmine-id>-<short-description>` for a feature or
  `fix/<redmine-id>-<short-description>` for a fix (e.g. `feat/12345-export-csv`); ask for the
  Redmine issue ID if it isn't known rather than inventing one.
- Write commit messages that describe the change and the reasoning, and end there. Never add
  `Co-Authored-By` or any other trailer naming an AI model to a commit message or PR body, even
  when a default or harness convention suggests one. Use an "exact commit message" from the user
  literally; don't append anything to it. If a trailer slipped into an unpushed commit, amend it
  out.
- Keep commit messages short: a subject line, a sentence or two of reasoning only if the change
  is non-obvious, and a brief list of what changed, roughly 10 body lines at most. Put
  verification results and trade-offs in the chat or PR discussion, not `git log`.
- Before any destructive git operation (`reset --hard`, `checkout --`, `clean -f`, force-push),
  run `git status` and make sure nothing uncommitted is about to be lost.

## Documentation

- Update the docs a change invalidates as the last step of that same change, not in a follow-up.
  A doc describing last week's behavior is worse than no doc — the next reader trusts it and
  either re-derives what's already known or acts on something false.
- When a previously published claim turns out to be wrong, retract it explicitly: state what was
  claimed, that it was wrong, and what replaced it — never silently edit it away. Do this equally
  for a claim that was too pessimistic and one that was too optimistic; understating a status is
  just as damaging as overstating it once someone checks it against reality.

## Communication and output format

- Be direct and technical, and state results plainly. Don't pad a technical answer with filler,
  hedging, unearned enthusiasm, or politeness tokens ("Great question!", "I'd be happy to...").
- For a new file, give full contents. For a change to an existing file, prefer a diff/patch view
  over reprinting the whole file, unless the whole file is short or the changes are pervasive.
- For large structured listings (many files, rows, or repeated-shape records) where density
  matters more than prose, prefer a compact tabular or count-prefixed list form over one bullet
  per item — it's easier to scan and cheaper to produce.
- Match response length to the question. Answer a simple question directly, not with a
  structured essay.

## Constraints

- Apply SOLID and DRY as defaults, not mandates: don't let them force an abstraction the problem
  doesn't need yet. Three similar lines beat a premature interface.
- Finish every implementation you start. Don't add feature flags or backward-compatibility shims
  for code that could just be changed directly — change it — unless backward compatibility is an
  explicit requirement.
- Match the scope of an action to what was actually asked — never quietly expand or narrow it.
