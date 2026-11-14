# Coding practices

Applies to every project. A repo's own `AGENTS.md`/`CLAUDE.md` adds to this and wins on conflict.

## Principles

- **Correct and secure over fast.** Treat code as long-lived unless told it's throwaway.
- **Minimal.** Simplest logic that solves the actual problem. Write three lines of native code instead of adding a dependency. Three similar lines beat a premature abstraction; apply SOLID/DRY only where the scope needs it.
- **Readable.** Clear names and structure over cleverness.
- **Match the codebase.** Follow its existing style, conventions and architecture; extend its patterns. If you think a different approach is better, propose it — don't apply it.
- **Stay in scope.** Do exactly what was asked, don't quietly expand or narrow it. Finish what you start; no feature flags or compatibility shims unless asked. Don't touch lines the task doesn't need: no reformatting, renaming, rewriting test data, or deleting existing comments, type hints or docs your change didn't make wrong.
- **Don't loop.** If the same fix fails twice, stop and report what you tried and the error instead of trying variations.

## Before and while writing code

- **Look it up, don't guess.** For any library, API, flag or spec, read the installed version's docs/source/types first (API-check commands below). Use the current API, not a deprecated one.
- **Web front-end: check modern-web-guidance first.** For HTML, CSS or client-side JS (UI components, forms, layout, animation, accessibility, performance, browser APIs — also inside React/Vue/etc.), use the `modern-web-guidance` skill before writing code and follow the guides it returns. Without the skill loaded, run it directly: `npx -y modern-web-guidance@latest search "<2-5 word query>"`, then `npx -y modern-web-guidance@latest retrieve "<id>"`. For Chrome extensions, use the `chrome-extensions` skill. Not for backend, build tooling, CI or tests. This command is the one exception to the `--no-install` / no-global-tools rules below.
- **Read before editing.** Read a file (and existing handoff notes, changelogs, plans) before changing or re-solving it.
- **Dry-run the logic:** null/empty input, off-by-one, timeouts, races, the error path.
- **Check security:** injection, path traversal, unsafe deserialization, auth bypass.
- **No secrets** in code, logs, output or commits — read them from config or a secret store. Flag any already committed (deleting it later doesn't remove it from history).
- **Validate at trust boundaries** (user input, external APIs, network). Skip checks for conditions the surrounding code already makes impossible.
- **Parse strictly to the spec.** Reject malformed input with an error that quotes the original input; never silently round, pad, truncate or guess.
- **Fail closed.** A clear startup error beats silently degraded behavior that reports success.
- **Money and other exact amounts:** integer minor units (cents) or a decimal type, never floating point.
- **Dates and time zones:** use the platform's time zone API, not hand-rolled offset math; test both DST transition days.
- **Concurrency:** for every goroutine, thread or channel, know who closes it and how it stops on cancel or error. No busy-waiting; don't read shared state without its lock.
- **Contract changes** (field, enum, wire format, config key): grep the old and new name across every project and update all producers, consumers, doc examples and fixtures.

## Comments and file layout

- Names and structure say WHAT; a comment says WHY, only where it isn't obvious: a hidden constraint, the reason for a value (limit, interval, default), a workaround, a surprising behavior.
- Never restate the code or the name below the comment. Wrong: `// queueAttendancePrivileges are the territories where...` Right: `// Territories where...`
- One line where possible. Almost never comment model/type properties.
- In long files, group related code into foldable regions using syntax the language really has (`#region` in C#, `// #region` in JS/TS). Not in short files. In C/C++, `#pragma region` warns on GCC/Clang (fatal with `-Werror`) — check first. A file needing many regions should be split instead.

## Testing

- **Ask once per repo whether tests are wanted** and which framework — unless the repo already has tests or its own instructions say. Then follow that answer for the whole repo.
- **Test-first when tests are in scope:** write the test, run it and see it fail for the expected reason, then write the minimal code to pass.
- **Tests don't replace the fix.** A change that adds tests but leaves the code broken isn't done.

Every new test must pass all of these:

1. **It fails without your change.** Once it passes, prove it: `git stash push -- <changed source files>`, run the new tests, check they fail for the reason you expect, then `git stash pop`. A test that still passes tests nothing: fix it or delete it.
2. **It goes through the changed code.** Call the entry point that had the bug (the client, the CLI command, the service method), not a helper next to it. Fakes may replace only what's outside the change (network, clock, disk), never the code under test.
3. **It asserts the exact expected value**: the whole error message, the whole CSV row, the exact amount. Not `!= nil`, `NotEmpty`, "contains 'error'", or "A or B". Assert on outputs, not just exit codes or "no exception".
4. **Its expected values come from the spec**, never from running your code and copying its output. Read values the code owns (limits, defaults, names, routes) from the production constant; literals only for external contracts (wire formats, file formats, user-facing text).
5. **Its inputs tell right from wrong:** pick inputs where the likely wrong implementation gives a different result — an odd amount for half-up rounding, numbers where rounding per line and per group differ, both DST transition days, the boundary and one step past it, the failing item in the middle with more than one worker. Cover the negative case.
6. **One test per requirement or bug**, named after it (`TestShortPageDoesNotEndSync`). Several inputs for the same rule go in one table test, not in copies of the same test.
7. **It's deterministic.** No real clock, network or sleeps: pass the date in, use fakes or `httptest`, and put a timeout around anything that could hang.
8. **Its test data obeys the business rules** (an express shipment has the express price). Reuse the project's fixtures and helpers; don't touch fixtures you don't need.

Existing tests: change them only where the requested behaviour changed, and then only the expected value. Never loosen an assertion to make a test pass. Tests are code: no debug prints, no notes to yourself ("wait, actually…"), no tests for behaviour you didn't change.

## Verify before you say "done"

Code that has not been built and checked is not finished. "Done" means: it builds, the type checker and linters the project uses pass, and the tests pass. A failing build is never done, however small the remaining error.

- **Build after every edit**, not only at the end, so the code compiles at every point where you could be stopped (time limit, context limit, crash). Take the next step only from a building state; if an edit breaks the build, fix that first.
- **If you can't get it green**, don't call it done or "complete": say it's unfinished, which check fails, and show the error lines.

After every change:

1. **Run the checks.** Prefer the project's own commands (Makefile, `package.json` scripts, CI config, README), otherwise the defaults below. Run the ones that apply to the changed files, plus the tests that cover the affected code (not just the new test). Format the changed files after your last edit (`gofmt -w`, `dotnet format`, `ruff format`); a passing linter doesn't prove formatting.
2. **Report honestly.** Say which commands you ran and whether they passed; show the relevant error lines on failure, including failures that existed before your change. Never claim a check passed without running it, and never report an action you didn't perform.
3. **Fix, then re-run.** A fix is done only when the same check passes again. Never delete tests, add ignores, weaken types or loosen thresholds to make a check pass — fix the code or input instead.
4. **Prove APIs exist.** Before using a function, method, field, flag or package not already seen in this project, confirm it exists in the installed version. Don't guess signatures.
5. **Prove it's wired in.** A feature with no caller in the real execution path doesn't work. `grep` for the call site.
6. **Clean up.** Experiments and scratch files go in `/tmp`, never the repo. Remove what your change left unused (helpers, imports, parameters, constants).
7. **Review your diff and the request.** Run `git status` and `git diff`: every file and hunk must belong to the change; revert the rest. Re-read the request or plan and tick off every item, including docs and test steps.
8. **Missing tools:** if a linter or tool isn't installed, say so and skip it. Don't install tools globally or add dependencies without asking.
9. **Expensive checks** (launching a browser, long runs): ask first.

## Git

- Commit only when asked or the repo says so. Then: one branch per feature/fix (`feat/<short-description>`, `fix/<short-description>`; include an issue ID if one exists), small logically-scoped commits.
- Commit message: subject line, a sentence of reasoning only if non-obvious, a short list of changes; ~10 body lines max. Use a user-given message verbatim.
- Never add `Co-Authored-By` or any AI-attribution trailer to commits or PRs.
- Before `reset --hard`, `checkout --`, `clean -f` or force-push: run `git status` and make sure nothing uncommitted is lost.

## Plans and docs

- Plans: short — what, how, why. Simple wording, mermaid diagrams for flows, exact function names in code traces. Name the plan file after the job (e.g. `plans/export-csv-refactor.md`), never randomly.
- When referencing docs, cite heading numbers/names, not line numbers.
- Update docs a change invalidates as part of that change. If an earlier claim was wrong, say so explicitly — what was claimed and what's true — don't silently edit it away.

## Output

- Direct and technical. No filler, hedging or "Great question!". Match length to the question.
- New file: full contents. Changed file: a diff, unless the file is short or most of it changed.
- Many similar items: compact table or list, not a bullet essay.

## Check commands by language

### Go
```bash
gofmt -l .                # must print nothing
go build ./...
go vet ./...
go test ./...
go test -race ./...       # when the change touches goroutines, channels or locks; needs cgo (gcc)
golangci-lint run         # if installed or .golangci.yml exists (else: staticcheck ./...)
go doc <pkg>.<Symbol>     # API check, e.g. go doc net/http.Client.Do
```
If you changed dependencies, run `go mod tidy` and check the `go.mod` diff.

### C# / .NET
```bash
dotnet build              # treat new warnings as problems to fix
dotnet test
dotnet format --verify-no-changes
```
API check: a successful `dotnet build` is the proof. Check package versions in the `.csproj` before relying on newer APIs.

### JavaScript / TypeScript
Use the package manager that matches the lockfile (`package-lock.json` = npm, `pnpm-lock.yaml` = pnpm, `yarn.lock` = yarn, `bun.lock` = bun). Prefer the `package.json` scripts (`lint`, `typecheck`, `test`, `build`).
```bash
npx --no-install tsc --noEmit             # TypeScript type check
npx --no-install eslint .                 # if configured
npx --no-install prettier --check .       # if configured
npm test
node --check <file>.js                    # plain JS syntax check
```
`--no-install` stops npx from downloading packages. API check: confirm the package is in `package.json`, then read its types in `node_modules/<pkg>` (`.d.ts`).

### Python
Use the project's environment: prefix commands with `uv run` (uv), `poetry run` (Poetry), or activate `.venv`.
```bash
ruff check .
ruff format --check .
mypy .                    # or pyright, if configured
pytest -q
python -m compileall -q . # syntax check when no linters are set up
python -c "from pkg import name; help(name)"   # API check
```
