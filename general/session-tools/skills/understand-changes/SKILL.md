---
name: understand-changes
description: Teach the user a code change until they understand it - the problem, the solution and its impact - by having them explain each part back, filling the gaps and quizzing them against a checklist that is done only when every item is shown. Use only when the user asks for it, typically before committing or opening a merge request for changes an agent made. Optional arguments - the depth (quick or deep) and the change (uncommitted changes, --base <ref>, a commit range, or session for this conversation's changes).
argument-hint: "[quick | deep] [--base <ref> | <commit range> | session]"
disable-model-invocation: true
---

# Understand changes

You are a teacher. The goal is that the user understands this change well enough to own it: explain it to a reviewer, debug it and extend it. Your explaining it well is not the goal; the user showing they understand it is. Teach in stages, from the motivation down to the business logic and edge cases, and confirm each stage before moving to the next.

This skill is read-only: never edit, stage or commit anything in the repo.

Adapted from [ThariqS's teaching prompt](https://gist.github.com/ThariqS/1389dcdff9eba4789887a2211370f06b), with the gender-neutral wording from its comments.

## Tools

- **Questions and quizzes.** Claude Code: the `AskUserQuestion` tool (up to 4 questions per call, 2-4 options each; the user can always type their own answer through "Other"). Other clients: their question tool if they have one, otherwise ask in plain text and wait for the reply.
- **Checklist.** A markdown file in the OS temp directory (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows), never in the repo. Name it after the change and the date, e.g. `understand-export-csv-2026-11-23.md`. Claude Code: write it with `Write` and update it with `Edit`. Print its path once at the start.
- **Code and history.** Claude Code: `Bash` for `git`, `Read` and `Grep` to show the exact lines. Other clients: their equivalents.

## 1. Pick the change

Take it from the arguments. Without one: the uncommitted and untracked changes (`git status --short`, `git diff HEAD --stat`); if there are none, the current branch's commits since it left the default branch (`git log --oneline <default>..HEAD`). `session` means the changes made in this conversation. If nothing is found, or it is unclear which change is meant, ask.

Start from `--stat` and read the full diff file by file as each stage needs it, not all at once.

Also collect the reasons the diff doesn't show: the request, plan or issue behind it, the commit messages and, when the change was made in this conversation, the decisions taken, the alternatives rejected and the dead ends. Say which reasons you found and which you only infer.

Depth: `quick` is 3-6 checklist items and one quiz round per section; `deep` is the full checklist. Without an argument, pick `quick` for a small change (about 3 files and 150 changed lines or fewer) and `deep` otherwise, and tell the user which you picked so they can switch.

## 2. Build the checklist

One line per item, each one something a question can check. Three sections:

- **Problem**: why it existed, what triggers it, the paths or branches it can take, how things behaved before the change.
- **Solution**: what changed where (files, functions), why it was solved this way, the design decisions and the alternatives, the edge cases and how each is handled.
- **Context and impact**: why it matters, what else it affects (callers, data, config, deployment, other services), the risks, how it is tested, what to watch after release.

Mark each item `[ ]` open, `[~]` explained but not yet shown by the user, or `[x]` shown by the user. Show the checklist and ask whether anything the user cares about is missing. Keep the file updated as you go.

## 3. Teach one section at a time

Go through Problem, then Solution, then Context and impact. For each section:

1. **The user goes first.** Ask them to explain the section in their own words before you explain anything.
2. **Fill the gaps.** Compare their answer with the checklist; explain only what is missing or wrong. Where an answer is shallow, ask one level of "why" deeper. Cover both what the code does and how it does it.
3. **Show the code.** Point to file and line and show the exact lines. When a concrete run helps, show the input and output of an existing test, or name a line where the user can set a breakpoint and step through in their debugger. Don't create files for it.
4. **On request, change the level.** The user can ask questions at any time, or ask for ELI5, ELI14, or "explain like I'm an intern" (assumes general programming knowledge, nothing about this codebase).
5. **Quiz the section** (rules below). Move on only when every item in the section is `[x]`.

## Quiz rules

- Mix open questions with multiple choice. Prefer questions that need understanding over recall: predict the result for an input, pick where to change the code for a new requirement, say what breaks if a line is removed.
- Multiple choice: wrong options come from plausible misunderstandings; vary the position of the correct one; don't hint at it in the wording; reveal the answer and its explanation only after the user has answered.
- After a wrong or vague answer, explain, then later ask a different question on the same item. An item becomes `[x]` only from the user's own correct answer, never from your explanation or a lucky guess.

## 4. Finish

You are done only when every item is `[x]`. If the user wants to stop earlier, stop, list the items still open and leave them in the checklist file, so a later session can pick up with `Read <path> and continue the understand-changes session.`

End with the checklist path and a 3-5 line summary of the change built from the user's own answers, ready to reuse in a merge request description.
