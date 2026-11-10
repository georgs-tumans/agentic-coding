---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up. Use only when the user explicitly asks for a handoff; any arguments describe what the next session will be used for.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS (`$TMPDIR`, else `/tmp`; `%TEMP%` on Windows) - not the current workspace. Give the file a descriptive name reflecting the work and the date (e.g. `handoff-export-csv-2026-10-12.md`), not a generic one.

Mark every claim in the document as verified or unverified. State what evidence backs a verified claim (the command run and its result); label anything assumed or not checked as unverified, so the next agent re-checks it instead of trusting it.

Include a "suggested skills" section in the document, naming which skills the next agent should call the Skill tool for.

Prioritize what exists only in this conversation and would otherwise be lost: the user's decisions (with their reasons), corrections, preferences and constraints ("don't touch X", "use approach Y because Z"), and dead ends already tried (what failed and why), so the next agent does not repeat them or re-ask settled questions.

Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

When done, print the full path of the file and a ready-to-paste starter prompt for the next session, such as `Read <path> and continue the work.`
