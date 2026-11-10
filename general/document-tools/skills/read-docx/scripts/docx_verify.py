"""Check docx_read.py against Microsoft Word's own reading of a .docx.

    python docx_verify.py <file.docx>

Word opens a copy, accepts all tracked changes, turns list numbers into text and saves it as plain
text. The script then compares, in order, every heading's number and title, the words of every
section, and the words of all footnotes, endnotes and comments. Use it when a document's reading
matters (a spec you will cite) or after changing docx_read.py.

Needs Windows with Word installed. Exit codes: 0 same as Word, 1 differences, 2 could not run.
"""
from __future__ import annotations

import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ next to the skill
sys.path.insert(0, str(Path(__file__).resolve().parent))
import docx_read as D  # noqa: E402

WORD_EXPORT = r"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($env:DOCX_SOURCE, $false, $false, $false)
    $doc.TrackRevisions = $false
    $doc.Revisions.AcceptAll()
    $doc.ConvertNumbersToText()
    $doc.SaveAs2($env:DOCX_TEXT, 2, $false, '', $false, '', $false, $false, $false, $false, $false, 65001)
    $doc.Close(0)
} finally { $word.Quit() }
"""
COMMENT_MARKER = re.compile(r"\[[^\]\s]{1,9}\d+\]")  # Word writes comment anchors as [AK118]
TOC_LINE = re.compile(r"\t\d+\s*$")  # table of contents: title<TAB>page
NUMBER_ONLY = re.compile(r"[\w.()]+\t\s*")
NOTE = re.compile(r"\[(?:footnote|endnote) ([^:\]]+): ([^\]]*)\]")


def word_text(docx_path):
    with tempfile.TemporaryDirectory() as work:
        source, text = Path(work, "source.docx"), Path(work, "word.txt")
        shutil.copyfile(docx_path, source)
        env = dict(os.environ, DOCX_SOURCE=str(source), DOCX_TEXT=str(text))
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", WORD_EXPORT],
                       env=env, check=True, capture_output=True)
        return text.read_text(encoding="utf-8-sig")


def tokens(text):
    text = re.sub(r"\[image: [^\]]+\]", " ", text)
    # Word's text export leaves text boxes out and keeps hidden text, unmarked.
    text = re.sub(r"\[text box: [^\]]*\]", " ", text)
    text = re.sub(r"\[hidden text: ([^\]]*)\]", r"\1", text)
    text = COMMENT_MARKER.sub("", text)
    # Word's export writes "…" as "..." and drops the space after numbers whose suffix is "nothing".
    text = re.sub(r"(?<![\w.])((?:\d+\.)+)(?=[^\W\d])", r"\1 ", text.replace("…", "..."))
    text = text.translate(D.FOLD).replace("|", " ").lower()
    # Bullets: docx_read prints "-", Word's export prints the glyph: "o", a symbol-font character, or
    # "==>" for the Wingdings arrow.
    return [t for t in text.split()
            if not (len(t) == 1 and not t.isalnum()) and t not in ("o", "==>") and not "" <= t[0] <= ""
            and t.strip("-_")]  # Word separates the notes from the body with lines of dashes


def page_furniture(docx_path):
    """Header and footer paragraphs, which Word's export repeats near the end."""
    lines = set()
    with zipfile.ZipFile(docx_path) as package:
        for name in package.namelist():
            if re.fullmatch(r"word/(header|footer)\d*\.xml", name):
                for paragraph in re.findall(r"<w:p[ >].*?</w:p>", package.read(name).decode("utf-8"), re.S):
                    lines.add(" ".join("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", paragraph)).split()))
    return lines - {""}


def fold(line):
    return " ".join(COMMENT_MARKER.sub("", line).translate(D.FOLD).split()).lower()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    docx_path = Path(sys.argv[1])
    try:
        document = D.Document(docx_path)
        export = word_text(docx_path)
    except (OSError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        print(f"-- could not run the check: {error}")
        return 2
    print(f"Checking docx_read.py against Word for {docx_path.name}")

    # Our side: headings in order, and each heading's text up to the next heading.
    headings, sections, notes, refs = [], [[]], [], []
    for _, _, _, block in document.sections():
        if isinstance(block, list):
            lines = [" | ".join(row.cells) for row in block]
            refs += [ref for row in block for ref in row.comments]
        else:
            if block.heading:
                label = block.label if block.label != "-" else ""
                headings.append(f"{label} {block.text}".strip())
                sections.append([])
            # Word also shows list numbers with no text after them.
            lines = [f"{block.label} {block.text}"]
            refs += block.comments
        for line in lines:
            # Word shows the note's mark in the text and the note itself after the body.
            notes += [f"{mark} {text}" for mark, text in NOTE.findall(line)]
            sections[-1].append(NOTE.sub(lambda match: match.group(1), line))

    # Word's side: body lines without the table of contents, then what it appends after the body.
    # A table of contents can sit anywhere, not only at the top; docx_read skips its paragraphs too.
    lines = [line for line in re.split(r"[\r\n\x07\x0c]", export) if line.strip() and not TOC_LINE.search(line)]
    merged = []
    for line in lines:
        # A heading that starts with a page break: Word puts its number on a line of its own.
        if merged and NUMBER_ONLY.fullmatch(merged[-1]) and not NUMBER_ONLY.match(line):
            merged[-1] += " " + line
        else:
            merged.append(line)
    lines = merged

    problems, starts, position = 0, [], 0
    for heading in headings:
        wanted = fold(heading)
        found = next((i for i in range(position, len(lines))
                      if (fold(lines[i]) == wanted if len(wanted) < 60 else fold(lines[i]).startswith(wanted[:60]))
                      or fold(lines[i]).startswith(wanted + " ")), None)
        if found is None:
            print(f"  heading not found in Word's order: {heading!r}")
            problems += 1
            starts.append(None)
            continue
        starts.append(found)
        position = found + 1
    print(f"headings matching Word's number, title and order: {sum(s is not None for s in starts)}/{len(headings)}")

    # Everything after the last section's own text is Word's appendix: notes, comments, page furniture.
    found_starts = [s for s in starts if s is not None]
    tail_words = collections.Counter(tokens("\n".join(lines[found_starts[-1]:]))) if found_starts else collections.Counter()
    last_section = collections.Counter(tokens("\n".join(sections[-1]))) if found_starts else collections.Counter()
    boundaries = [0] + [s if s is not None else None for s in starts]
    total = 0
    for index, section in enumerate(sections):
        begin = boundaries[index]
        if begin is None:
            continue
        later = [b for b in boundaries[index + 1:] if b is not None]
        end = later[0] if later else len(lines)
        ours = collections.Counter(tokens("\n".join(section)))
        word = collections.Counter(tokens("\n".join(lines[begin:end])))
        if index == len(sections) - 1:
            word = word & ours  # the rest of the last region is Word's appendix, compared below
        total += sum(ours.values())
        if word != ours:
            problems += 1
            name = headings[index - 1] if index else "(before the first heading)"
            print(f"  {name[:60]}: missing {dict(list((word - ours).items())[:8])} extra {dict(list((ours - word).items())[:8])}")
    print(f"section words compared: {total:,}")

    furniture = page_furniture(docx_path)
    appendix = tail_words - last_section
    appendix -= collections.Counter(tokens("\n".join(furniture)))
    appendix = collections.Counter({t: n for t, n in appendix.items() if not t.isdigit()})  # page numbers
    extra = collections.Counter(tokens("\n".join(notes + [c.text for _, c in document.visible_comments(refs)])))
    extra = collections.Counter({t: n for t, n in extra.items() if not t.isdigit()})
    if appendix != extra:
        problems += 1
        print(f"  notes and comments: missing {dict(list((appendix - extra).items())[:8])} "
              f"extra {dict(list((extra - appendix).items())[:8])}")
    print(f"note and comment words compared: {sum(extra.values()):,}")

    print("OK: docx_read.py reads this .docx the way Word does." if not problems else f"FAILED: {problems} differences.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
