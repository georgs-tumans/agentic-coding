# Global agent instructions

## Coding tasks
If your task involves writing, changing, reviewing or planning code, run `cat /home/georgs/.agents/DEVELOPMENT.md` before your first edit and follow it. It covers coding style, testing, git, plans, and how to verify code before calling the work done. Skip it for tasks that don't touch code.

The essentials, in case you read nothing else:
- You are done only when the code builds and the tests pass. Build after every edit (`go build ./...` / `go vet ./...`, `dotnet build`, `tsc --noEmit`, `python -m compileall -q .`) so the code compiles at every point you could stop. If you can't make the build or tests pass, don't say "done": say what is unfinished and show the error.
- Fix the cause the task describes. Adding tests alone is not a fix.
- Every new test must fail without your change: stash your source changes, run the test, see it fail, unstash.
- Assert exact values taken from the spec. Never loosen or rewrite existing tests to make them pass.
- Money in integer cents or a decimal type, never floating point. Dates through the time zone API.
- Every error path returns or reports the error; never report success after a failure.
- Do every item of the request or plan, including README and docs steps. Then run the tests and the formatter, and check `git diff` for leftovers.
