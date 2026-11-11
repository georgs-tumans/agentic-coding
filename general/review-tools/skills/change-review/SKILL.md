---
name: change-review
description: Review a finished code change in a git repo against the request and the coding standards, and give a verdict (PASS / NEEDS_WORK / FAIL) with verified findings. Use after implementing something and before reporting it done, when asked to review, check or verify changes made by an agent or a person, or as the check step after each part of a larger task. Optional arguments - the mode (review, fix or step), what to check against (the request, a plan or issue file) and a base branch or commit.
argument-hint: "[review | fix | step] [request, plan or issue] [--base <ref>]"
---

# Change review

You check a change that is already written. Goal: find real problems before a human does. A short review with three true findings is worth more than a long one with guesses.

Modes (the caller or the arguments say which; default is **review**):
- **review**: read-only. Don't edit any file. Report.
- **fix**: report, fix the blockers and majors, then review again. At most 2 rounds; then report what is still open.
- **step** (part of a larger task): review only what this step had to do, against the plan's step text.

## 1. Collect the facts

Run the script in this skill's folder (`<skill dir>`: where this SKILL.md is, e.g. `~/.agents/skills/change-review` or the plugin's install folder), from inside the repo (`python`, or `python3` where that is the name; Python 3.9+):

```bash
python <skill dir>/scripts/review_facts.py              # uncommitted changes + untracked files
python <skill dir>/scripts/review_facts.py --base main  # or: everything since a branch/commit
```

It lists the changed files, flags leftovers, removed tests/comments, new dependencies, TODOs and debug output, checks formatting of the changed files, and prints the checks to run and the instruction files to read. Its flags are hints: confirm each by reading the code. `--quick` skips the slow `dotnet format`. Exit code 0 = nothing flagged, 1 = something to look at, 2 = it couldn't run (not a git repo, unknown base); the output says which.

## 2. Find the request

You must know what the change was supposed to do. In this order: the text the caller or the arguments gave you; the plan or issue it names; a plan file that the change itself references or edits; the commit messages (`git log`). Write the request as a numbered list of requirements, including docs, tests and "don't change X" items. If you find nothing, or several candidates, ask the user which one. If nobody can answer (an unattended run), say so in the report and review only correctness and standards.

## 3. Read

- The instruction files from the facts (`AGENTS.md`, `CLAUDE.md`, `README.md`), plus any global coding guidelines your session's instructions point to (e.g. a `DEVELOPMENT.md` named in a global `AGENTS.md`). The repo's own rules win on conflict.
- The whole diff (`git diff <base>`), every untracked file, and for each changed function its callers and the tests that cover it. Don't judge a hunk without its surrounding code.

## 4. Run the checks

Run the project's own commands (from instruction files, Makefile, CI), otherwise the ones the facts suggest: build, format, lint, tests. Record each command and its result. A failing build or failing test is a blocker; quote the first error lines. If a tool is missing, write that down; don't install anything.

## 5. Go through the checklist

Every item comes from real mistakes agents made. Check each one that applies.

**Request coverage**
- Every requirement done? Mark each done / partial / missing, with the file:line or check that shows it.
- Nothing extra: no features, refactors or "improvements" the request didn't ask for.
- Docs and tests that the request asked for are there (plans often have them as the last step, and they get skipped).

**Correctness**
- Edge cases: empty/null input, zero, negative, boundary values (at the limit and one past), the error path.
- Parsing is strict: malformed input is rejected with an error that shows the original input, not silently rounded, padded, truncated or guessed.
- Money is integer minor units (cents) or a decimal type, never float.
- Dates/time zones use the platform's time zone API; DST transition days work (no hard-coded hours or offsets, no probing loops).
- Concurrency: every goroutine/thread/channel has an owner that closes it and stops it on cancel or error; no busy-waiting; shared state read under its lock; unbuffered channels can't deadlock when there are more items than workers.
- Contract changes (field, enum, wire format, config key) reach every producer, consumer, doc example and fixture; required/optional markers still right.
- Errors: the message names the right operation; errors are not swallowed by a catch-all.
- Special-casing: the code must work for inputs other than the ones in the tests.

**Scope and cleanliness**
- No leftover files: debug scripts, scratch projects, `.orig`/`.bak`, logs, binaries. An extra `.csproj` or `go.mod` in the repo can break the build for everyone.
- No unrelated edits: reformatted lines, renamed things, rewritten test data, deleted comments, doc comments or type hints the change didn't make wrong.
- Nothing left unused: helpers only their own test calls, unused imports, parameters, constants or variables.
- No commented-out code, no new TODO without a reason, no debug output.
- No new dependency unless the request allows it.
- Fits the codebase: same patterns, naming, layering and style as the surrounding code. Judge against the project's way, not your own taste.

**Tests**
- New behaviour has tests; a bug fix has a test that fails without the fix.
- Tests can actually fail: inputs chosen so a plausible wrong implementation gives a different result (e.g. "round once" vs "round per line" need numbers where they differ).
- Assertions check outputs, not only exit codes or "no exception".
- Expected values are right (recompute one by hand).
- Uses the project's fixtures and helpers; no duplicate tests; no debug "tests" that only print.
- No existing test deleted or loosened to make things pass.

**Docs**
- User-visible changes (commands, flags, config, API fields, storage format) are in the README/docs, and examples match the new behaviour.
- Comments next to changed code are still true.

## 6. Verify every finding

Before you write a finding, check that:
1. You can point to a file and line in the change (or a missing file/line the request needed).
2. You can state a concrete failure: "input X → result Y, expected Z", "Run() never returns when ...", or a quoted rule from the instruction files that is broken.
3. It is caused by this change, not something that was already there. Pre-existing problems go under *Notes*, only if they matter.

If you can't do 1 and 2, it's a question, not a finding: put it under *Questions*. Don't report style that the formatter or linter already accepts. Don't propose rewrites of code the change didn't touch.

Severity:
- **blocker**: doesn't build, a test fails, a requirement is missing, a wrong result for a normal input, data loss, a hang or deadlock, a security hole, a deleted test.
- **major**: wrong for an edge case the request or spec covers, a contract not updated everywhere, a leftover file, a test that can't fail, docs the request asked for are missing, a new dependency.
- **minor**: unused code, an unrelated edit, a weak test name, a misleading comment, noise.

Verdict: **FAIL** if any blocker; **NEEDS_WORK** if any major; otherwise **PASS** (minors may remain).

## 7. Report

Print this, nothing before it. Don't write the review into the repo. If the caller wants a file, write it where they say, by default in the OS temporary directory (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows), e.g. `review-step-3.md`.

```
VERDICT: FAIL | NEEDS_WORK | PASS
SUMMARY: <one sentence: what the change does and the biggest problem>

## Requirements
1. <requirement> — done | partial | missing — <file:line or check>

## Findings
| # | Severity | Where | Problem | Failure / rule | Fix |
|---|---|---|---|---|---|
| 1 | blocker | path/file.go:42 | ... | input X → Y, expected Z | ... |

## Checks run
- `<command>` — passed | FAILED: <first error line> | not run: <why>

## Questions
- <things you couldn't verify, and what would settle them>
```

Write "none" under an empty section. Keep each finding to one or two sentences.

## Using it in a larger task

For a plan with several steps: implement a step, run this review in **step** mode against that step's text, fix blockers and majors, then move on. Don't fix the same finding more than twice: if it still fails, stop and report it. At the end, run one **review** over the whole change against the whole plan.

A review in a fresh session (or by another model) catches more than a self-review in the same session, because it doesn't share the implementer's assumptions. When reviewing someone else's work, the same rules apply: judge it against the request and the project's conventions, not against how you would have written it.
