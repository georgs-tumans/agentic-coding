# agentic-coding

Personal Claude Code / GitHub Copilot plugins (skills + subagents), published as one
marketplace: `agentic-coding`.

| Plugin | What it does |
|---|---|
| `document-tools` | Reads a Word `.docx` the way Word shows it, a section at a time: Word's heading and list numbers, tracked changes as accepted, tables, notes, images and review comments, plus search and a check against Word itself (skill `read-docx`) |
| `session-tools` | Project-independent session helpers: `handoff` compacts the conversation into a document a fresh agent can continue from (adapted from [mattpocock/skills](https://github.com/mattpocock/skills), MIT) |
| `review-tools` | `change-review` checks a finished change against its request and the coding standards (`DEVELOPMENT.md`, the repo's own instructions) and reports `VERDICT: FAIL / NEEDS_WORK / PASS` with verified findings. A script collects the facts models miss: leftover files, removed tests and comments, new dependencies, unformatted changed files, the checks to run. Modes: read-only review, review and fix, or a check after each step of a larger plan. Built for local agents checking their own work in a fresh session (it is a plain Agent Skill, so Goose, Pi and OpenCode load it from `~/.agents/skills` too) and for Claude Code reviewing a local agent's work. Not yet tested in Copilot |

## General coding guidelines

`DEVELOPMENT.md` is a rulebook for all agentic coding (principles, comments, testing,
verification before calling work done, per-language check commands, git, plans and docs, output
format), independent of the plugins. To apply it in every session, whatever the workspace, import
it from `~/.claude/CLAUDE.md` with `@/absolute/path/to/DEVELOPMENT.md`. Keep the path free of
spaces, since imports may not parse them. To load it only when a task touches code, keep it out
of the import and instead tell the agent in a global `AGENTS.md` (imported from
`~/.claude/CLAUDE.md`) to read `/absolute/path/to/DEVELOPMENT.md` before coding work.

The front-end rule in `DEVELOPMENT.md` names two external skills that this repo does not ship:
`modern-web-guidance` and `chrome-extensions`, both from
[GoogleChrome/modern-web-guidance](https://github.com/GoogleChrome/modern-web-guidance).
Install them with `npx modern-web-guidance@latest install` (an interactive wizard). Without
`modern-web-guidance` installed, the rule falls back to running `npx modern-web-guidance@latest
search` directly; `chrome-extensions` has no such fallback.

## Install

Claude Code:
```bash
claude plugin marketplace add https://github.com/georgs-tumans/agentic-coding.git
claude plugin install document-tools@agentic-coding --scope user
```

`--scope` decides where the install is recorded, and so who gets it:

| Scope | Recorded in | Effect |
|---|---|---|
| `user` (default) | your user settings (`~/.claude`) | Only you, in every session, whatever folder it starts in |
| `project` | the project's `.claude/settings.json` (commit it) | Everyone who opens that repo is offered the plugin, but only in sessions started inside that folder |
| `local` | the project's `.claude/settings.local.json` (not committed) | Only you, only in that repo |

A user install never reaches teammates. To offer a plugin to everyone working on a repo, use
`project` (or commit the snippet below), and add `user` on top if you also want it everywhere
yourself. A session started in a parent folder (a workspace holding several repos) does not load
a repo's `project` plugins. Plugins load at session start, so run `/reload-plugins` or open a new
session after installing. Remove one with `claude plugin uninstall <plugin> --scope <scope>`.

GitHub Copilot CLI:
```bash
copilot plugin marketplace add https://github.com/georgs-tumans/agentic-coding.git
copilot plugin install document-tools@agentic-coding
```
VS Code Copilot: add the URL to the `chat.plugins.marketplaces` setting, or run
"Chat: Install Plugin From Source".

To offer a plugin automatically in a project, commit this to the project's `.claude/settings.json`:
```json
{
  "extraKnownMarketplaces": {
    "agentic-coding": {
      "source": { "source": "git", "url": "https://github.com/georgs-tumans/agentic-coding.git" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "document-tools@agentic-coding": true }
}
```
`autoUpdate` updates the marketplace and all of its installed plugins at session start. It is set
per marketplace, not per plugin. Without it, update by hand with
`claude plugin marketplace update agentic-coding`.

## Layout

```
.claude-plugin/marketplace.json          lists the plugins
<topic>/<plugin>/
  .claude-plugin/plugin.json             name + description (no "skills"/"agents" keys, no version)
  skills/<skill-name>/SKILL.md           (+ scripts/, references/)
  agents/<agent-name>.agent.md           optional subagents
```

One plugin per independently useful thing, so nobody installs a one-off migration to get a
maintenance tool. Add a plugin by creating its folder and a `plugins[]` entry in
`marketplace.json`, then run `claude plugin validate .` before pushing. There is no `version`
on purpose: every pushed commit counts as an update. Add one only if a Copilot client insists.

## Principles for adding skills and plugins

**1. Universal, not hardcoded.** The same plugin must work in many repos with different names,
languages and folder layouts. Never bake in a repo name, file name or location. Instead:
- Describe **how to find** things: by content (markers inside files), not by name or path.
  Names are hints at most.
- Put discovery in a script when it can be deterministic (`docx_read.py` in `read-docx`), and
  let the model only interpret the short output.
- When nothing is found, or several things match, **ask the user**. Never guess, and never
  create files the skill was not asked to create.
- Validate what was found before acting on it (right kind of file, overlaps with the source).
- Ask in the main conversation. A subagent cannot ask, so resolve every ambiguity before
  delegating, and tell the subagent to stop and report if its inputs do not hold.

**2. Adapt to the project's own convention.** Projects do the same thing in different ways
(e.g. API specs kept as name-only stub schemas in one repo, full contracts in another). Never bake one convention
into a skill. Detect how the existing artifacts are written (in a script when possible), mirror
that, support every variant that really occurs in the repos, and ask the user when a file is
ambiguous. Check the claim against the real repos before writing it down as a rule; a rule
that holds for one project is only a habit.

**3. Compatible with GitHub Copilot where possible.**
- Skill frontmatter: only `name` (equal to the folder name; lowercase letters, digits, hyphens)
  and `description` (at most 1024 characters). `argument-hint` and `disable-model-invocation`
  are also read by VS Code Copilot (not documented for Copilot CLI, where they are ignored), so
  use them together with a matching sentence in the `description`. No other Claude-only fields.
- Refer to bundled files relative to the skill (`<skill dir>/scripts/x.py`, forward slashes).
  Do not use `${CLAUDE_PLUGIN_ROOT}` in skill or agent text; Copilot expands it only in hook and
  MCP configs. Pass absolute script paths to subagents in their prompt.
- Subagents are `agents/<name>.agent.md` with `name`, `description` and `tools` using Claude
  names (`Read, Edit, Grep, Glob, Bash`); Copilot maps them and ignores unknown ones. Leave
  `tools` out when the agent needs MCP tools (browser, DB): it then inherits all of them.
- Say in the skill how to start the subagent in each tool (Claude: Agent tool,
  `subagent_type` `<plugin>:<agent>`; Copilot: `runSubagent`), and what to do without one.
- Keep manifests in `.claude-plugin/`; both tools read them.
- Anything not yet tested in Copilot belongs in the plugin's notes as untested.

**4. Protect the main context.**
- Check cheaply first whether the work is needed at all (a script that prints a few lines), and
  stop early if not.
- Push heavy reading and editing into a subagent with a self-contained prompt, and ask for a
  short report, not file contents.

**5. One source of truth.** The skill holds the main agent's job, the agent file holds the
subagent's job and rules. Do not duplicate procedures across skill, agent, prompt files and
docs. Keep `SKILL.md` lean; move big reference material to `references/`.

**6. Deterministic safety nets.** For edits that can break silently (encodings, formatting),
ship a verification script and make the agent run it before reporting back.

**7. Scripts.** Python 3 with the standard library where possible (PyYAML is accepted). Small,
clear output; exit code 0 = fine, 1 = needs attention, 2 = could not do it. Read-only unless the
subcommand is explicitly a generator.

**8. Naming.** Plugin, skill and agent names are lowercase kebab-case. Skill name = folder name.
The plugin name is the namespace (`document-tools:read-docx`), so do not repeat it inside the
skill name.
