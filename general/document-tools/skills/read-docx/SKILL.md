---
name: read-docx
description: Read, search and cite a Word .docx the way Word shows it, without loading the whole file into context. A script prints the outline with Word's own heading numbers and section sizes, one section at a time, or search hits with their section, and covers tracked changes (as if accepted), auto-numbered headings and lists, tables with merged cells, footnotes, text boxes, images and review comments. Use when you need content from a .docx (specification, requirements, contract, manual, handbook), above all a long one or one you will cite by chapter number. Not for creating or editing Word files.
---

# Read a .docx

A `.docx` stores much of what Word shows only as instructions: chapter and list numbers are
computed from numbering definitions, tracked changes sit next to each other unaccepted, comments
live in a separate part. A plain text conversion loses those, and a long document does not fit in
context anyway. `scripts/docx_read.py` rebuilds what Word shows and lets you read it a section at a
time. It needs only Python 3.9+ (`python`, or `python3` where that is the name).

`<skill dir>` is the folder containing this SKILL.md; resolve it to an absolute path once.

## Read in three steps

```bash
python <skill dir>/scripts/docx_read.py <file.docx> outline [filter]
python <skill dir>/scripts/docx_read.py <file.docx> search "<regex>"
python <skill dir>/scripts/docx_read.py <file.docx> section <number> [--images <dir>]
```

1. **`outline`** lists every heading with its key and size, e.g. `2.4.1  Iestāžu klasifikators
   (10.3k chars)`. A filter narrows it by number or title. Start here unless you already know
   the section.
2. **`search`** finds where something is described. It prints each matching paragraph, table row
   or comment with its section key and title. It ignores case, diacritics and dash/quote style;
   in inflected languages search for word stems.
3. **`section`** prints one section with its subsections. Pick the narrowest one that answers the
   question. Above 60k characters (about 20k tokens) it refuses and lists the subsections instead;
   pass `--full` only when you really need all of it.

`comments [--open]` lists every review comment with its section; `--open` leaves out resolved
threads. Use it to see what the authors still consider unsettled.

Exit codes: 0 output, 1 nothing found or section too large (read the message), 2 the file could
not be read. Old binary `.doc` files are not supported; ask the user for a `.docx`.

## Reading the output

- **Final view.** Tracked insertions are in, tracked deletions are out, as if all changes were
  accepted. Comment threads on deleted text are left out, as Word does on accepting.
- **Numbers are Word's.** Heading and list numbers (`4.2.1.`, `a)`, `iv.`) are the ones Word
  displays. A heading Word does not number gets a key from its outline position, prefixed with
  `§` (`§2.3`). That key works with `section` but is not in the document: cite such a heading by
  its title, not by the key.
- **Structure.** Headings print as `## 2.4 Title`. List items are indented by level and bullets
  print as `-`. Tables print one row per line with ` | ` between cells; a merged cell prints once,
  and continued cells of a vertical merge are empty.
- **Inline markers**: `[image: image12.png]` (pass `--images <dir>` to save the section's images
  and open them to see mockups and diagrams), `[footnote 1: ...]`, `[endnote i: ...]`,
  `[text box: ...]`, and `[hidden text: ...]` for text Word hides on screen.
- **Comments** print right after the paragraph or table row they are attached to:
  `[COMMENT by <author>, <date>, reply, resolved] on "<commented text>": <text>`. They are the
  authors' notes and questions, **not part of the content**. An open comment on a passage you rely
  on means it may not be final: say so.
- Not extracted: text inside charts and SmartArt, embedded objects (spreadsheets, Visio).
  Headers and footers are left out.

Cite as `<number> <title>` (e.g. `2.4.1 Iestāžu klasifikators (KLASIF-01)`) and name the file you
read, since documents are revised.

## Check the reading against Word

```bash
python <skill dir>/scripts/docx_verify.py <file.docx>
```

Has Word itself (Windows with Word installed) open a copy, accept all changes and save it as
text, then compares every heading's number, title and order, every section's words, and the
words of all notes and comments. It takes about a minute for a 700-page document. Run it when the
exact reading matters (a document you will cite or audit against) and Word is available; it only
has to pass once per document version. It does not cover text-box content, which Word's export
leaves out.

- Exit 0 (`OK`): the reading matches Word.
- Exit 1 (`FAILED`): it lists the sections that differ. Tell the user which parts may be misread
  and treat them with care; do not hide the result.
- Exit 2: it could not run (no Word, not Windows). Say the check was not possible.
