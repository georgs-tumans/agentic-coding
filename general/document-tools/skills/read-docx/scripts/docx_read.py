"""Read a Word .docx the way Word shows it: outline, one section, text search, review comments.

    python docx_read.py <file.docx> outline [filter]                  # headings with numbers and sizes
    python docx_read.py <file.docx> section <number> [--full] [--images DIR]
    python docx_read.py <file.docx> search <regex>                    # matching paragraphs, rows, comments
    python docx_read.py <file.docx> comments [--open]                 # every review comment, by section

Output is Word's final view: tracked insertions in, tracked deletions out. Heading
and list numbers are rebuilt from Word's auto-numbering; a heading Word doesn't number gets a
"§" key from its outline position (§2.3). Tables print one row per line, cells joined by " | ",
merged cells once. Inline markers: [image: <file>] (--images saves them), [footnote 1: ...],
[endnote i: ...], [text box: ...], [hidden text: ...] (hidden in Word's normal view). Review
comments follow the paragraph or row they are attached to, marked [COMMENT ...].
Search ignores case, diacritics and dash/quote style.

Standard library only. Exit codes: 0 output, 1 nothing found or section too large, 2 could not read.
"""
from __future__ import annotations

import argparse
import posixpath
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
A_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
V_IMAGEDATA = "{urn:schemas-microsoft-com:vml}imagedata"
MC_FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
M_T = "{http://schemas.openxmlformats.org/officeDocument/2006/math}t"  # equation text


def tidy(text):
    """Collapse spaces but keep manual line breaks: code, addresses and verse depend on them."""
    return "\n".join(line for line in (" ".join(part.split()) for part in text.split("\n")) if line)


def w(tag):
    return f"{{{W}}}{tag}"


def val(element, path):
    found = element.find(path) if element is not None else None
    return found.get(w("val")) if found is not None else None


def on(element, path):
    """A Word on/off property: present and not switched off."""
    found = element.find(path) if element is not None else None
    return found is not None and found.get(w("val")) not in ("0", "false", "off")


# Deleted or moved-away text, property blocks (tab stops and change marks, no text) and the legacy
# duplicate Word stores next to every drawing.
NOT_TEXT = {w("del"), w("moveFrom"), w("pPr"), w("rPr"), w("sdtPr"), w("sdtEndPr"), MC_FALLBACK}
BREAKS = {w("tab"), w("br"), w("cr"), w("ptab")}
LINE_BREAKS = (None, "textWrapping")  # w:br types that start a new line; page and column breaks do not
HEADING_NAME = re.compile(r"heading (\d)", re.IGNORECASE)
ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
         (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
# Above this, `section` lists the subsections instead of printing: about 20k tokens of context.
SECTION_LIMIT = 60_000
PUNCTUATION = {"–": "-", "—": "-", "‒": "-", "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
               "‘": "'", "’": "'", "‚": "'", "\xa0": " "}


class Fold(dict):
    """str.translate table: each character to its base letter, so match positions stay valid."""

    def __missing__(self, code):
        char = chr(code)
        folded = self[code] = PUNCTUATION.get(char) or unicodedata.normalize("NFD", char)[0]
        return folded


FOLD = Fold()


@dataclass
class Paragraph:
    text: str
    heading: int | None  # outline level, 1-based
    label: str  # number Word shows before the paragraph, "-" for bullets
    depth: int  # list level
    toc: bool
    comments: list = field(default_factory=list)

    def inline(self):
        return f"{self.label} {self.text}".strip() if self.text else ""


@dataclass
class Row:
    cells: list
    comments: list


@dataclass
class Comment:
    author: str
    date: str
    text: str
    parent: str | None  # id of the comment this one replies to
    resolved: bool


class Package:
    """The .docx zip: XML parts and the relationships between them."""

    def __init__(self, path):
        self.zip = zipfile.ZipFile(path)
        self.names = set(self.zip.namelist())
        root_rels = self.relationships("")
        self.main = next(target for kind, target in root_rels.values() if kind == "officeDocument")
        self.rels = self.relationships(self.main)

    def xml(self, name):
        return ElementTree.fromstring(self.zip.read(name)) if name in self.names else None

    def relationships(self, part):
        folder, base = posixpath.split(part)
        rels = self.xml(posixpath.join(folder, "_rels", base + ".rels"))
        result = {}
        for rel in rels if rels is not None else []:
            if rel.get("TargetMode") == "External":
                continue
            target = rel.get("Target")
            target = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
            result[rel.get("Id")] = (rel.get("Type").rsplit("/", 1)[-1], target)
        return result

    def part(self, kind):
        return next((self.xml(target) for k, target in self.rels.values() if k == kind), None)


class Numbering:
    """Rebuilds the numbers Word shows for list and heading paragraphs, in document order."""

    def __init__(self, root, styles):
        self.styles = styles
        self.levels, self.abstract_of, self.overrides, style_links = {}, {}, {}, {}
        for abstract in root.findall(w("abstractNum")) if root is not None else []:
            abstract_id = abstract.get(w("abstractNumId"))
            self.levels[abstract_id] = {int(lvl.get(w("ilvl"))): lvl for lvl in abstract.findall(w("lvl"))}
            if (link := val(abstract, w("numStyleLink"))) is not None:
                style_links[abstract_id] = link
        for num in root.findall(w("num")) if root is not None else []:
            num_id = num.get(w("numId"))
            self.abstract_of[num_id] = val(num, w("abstractNumId"))
            for override in num.findall(w("lvlOverride")):
                self.overrides[(num_id, int(override.get(w("ilvl"))))] = (val(override, w("startOverride")),
                                                                          override.find(w("lvl")))
        # A numStyleLink abstract is an alias: the levels live in the abstract its style's list uses.
        for num_id, abstract_id in self.abstract_of.items():
            if abstract_id in style_links:
                self.abstract_of[num_id] = self.abstract_of.get(styles.get(style_links[abstract_id], {}).get("num_id"))
        # Lists sharing an abstractNum continue one sequence; a startOverride restarts it once.
        self.counters, self.restarted = {}, set()

    def level(self, num_id, ilvl):
        override = self.overrides.get((num_id, ilvl), (None, None))[1]
        return override if override is not None else self.levels.get(self.abstract_of.get(num_id), {}).get(ilvl)

    def label(self, properties, style_id):
        num_pr = properties.find(w("numPr")) if properties is not None else None
        num_id, ilvl = val(num_pr, w("numId")), val(num_pr, w("ilvl"))
        style = style_id
        while style in self.styles and (num_id is None or ilvl is None):
            num_id = self.styles[style]["num_id"] if num_id is None else num_id
            ilvl = self.styles[style]["ilvl"] if ilvl is None else ilvl
            style = self.styles[style]["based_on"]
        abstract_id = self.abstract_of.get(num_id)
        levels = self.levels.get(abstract_id)
        if not levels:
            return "", 0
        if ilvl is None:
            ilvl = next((i for i, lvl in levels.items() if val(lvl, w("pStyle")) == style_id), 0)
        ilvl = int(ilvl)
        level = self.level(num_id, ilvl)
        if level is None:
            return "", 0

        counters = self.counters.setdefault(abstract_id, [None] * 9)
        # A skipped parent level counts as used at its start value: "4." then "4.1.1." makes the next sibling "4.2.".
        for parent in range(ilvl):
            if counters[parent] is None and self.level(num_id, parent) is not None:
                counters[parent] = self.start(self.level(num_id, parent))
        start_override = self.overrides.get((num_id, ilvl), (None, None))[0]
        if start_override is not None and (num_id, ilvl) not in self.restarted:
            self.restarted.add((num_id, ilvl))
            counters[ilvl] = int(start_override)
        elif counters[ilvl] is None:
            counters[ilvl] = self.start(level)
        else:
            counters[ilvl] += 1
        for deeper in range(ilvl + 1, 9):
            deeper_level = self.level(num_id, deeper)
            restart = val(deeper_level, w("lvlRestart"))
            # lvlRestart n: restart after a level up to n (1-based) is used; 0: never. Default: after any higher level.
            if restart is None or (int(restart) != 0 and ilvl < int(restart)):
                counters[deeper] = None
        if val(level, w("numFmt")) == "bullet":
            return "-", ilvl
        legal = on(level, w("isLgl"))

        def number(match):
            index = int(match.group(1)) - 1
            index_level = self.level(num_id, index)
            if index_level is None:
                return ""
            value = counters[index] if counters[index] is not None else self.start(index_level)
            return self.format(value, "decimal" if legal else val(index_level, w("numFmt")))

        return re.sub(r"%(\d)", number, val(level, w("lvlText")) or ""), ilvl

    @staticmethod
    def start(level):
        return int(val(level, w("start")) or 1)

    @staticmethod
    def format(value, number_format):
        if number_format in ("lowerLetter", "upperLetter"):
            letters = ""
            while value > 0:
                value, rest = divmod(value - 1, 26)
                letters = chr(97 + rest) + letters
            return letters if number_format == "lowerLetter" else letters.upper()
        if number_format in ("lowerRoman", "upperRoman"):
            roman = ""
            for size, digits in ROMAN:
                count, value = divmod(value, size)
                roman += digits * count
            return roman if number_format == "lowerRoman" else roman.upper()
        if number_format == "decimalZero":
            return f"{value:02d}"
        return "" if number_format == "none" else str(value)


class Document:
    def __init__(self, path):
        self.package = Package(path)
        self.styles, self.default_style = {}, None
        styles = self.package.part("styles")
        for style in styles.findall(w("style")) if styles is not None else []:
            properties = style.find(w("pPr"))
            num_pr = properties.find(w("numPr")) if properties is not None else None
            self.styles[style.get(w("styleId"))] = {
                "name": val(style, w("name")) or "", "based_on": val(style, w("basedOn")),
                "num_id": val(num_pr, w("numId")), "ilvl": val(num_pr, w("ilvl")),
                "outline": val(properties, w("outlineLvl")), "hidden": on(style.find(w("rPr")), w("vanish"))}
            if style.get(w("type")) == "paragraph" and style.get(w("default")) in ("1", "true"):
                self.default_style = style.get(w("styleId"))
        self.numbering = Numbering(self.package.part("numbering"), self.styles)
        self.images = {rid: target for rid, (kind, target) in self.package.rels.items() if kind == "image"}
        self.anchors = {}  # comment id -> [range still open, text pieces the comment is attached to...]
        self.deleted_comments = set()  # referenced only from tracked-deleted text
        self.body = self.package.xml(self.package.main).find(w("body"))
        self.notes = {kind: self._notes(kind) for kind in ("footnote", "endnote")}
        self.note_numbers = {"footnote": 0, "endnote": 0}
        self.note_format = self._note_formats()
        self.comments = self._comments()
        self._blocks = None

    # #region Parts other than the body

    def _notes(self, kind):
        root = self.package.part(kind + "s")
        notes = {}
        for note in root.findall(w(kind)) if root is not None else []:
            if note.get(w("type")) in (None, "normal"):
                paragraphs = (" ".join(self._text(p, []).split()) for p in note.findall(w("p")))
                notes[note.get(w("id"))] = " / ".join(p for p in paragraphs if p)
        return notes

    def _note_formats(self):
        """(numFmt, start) per note kind: the body's last section properties, then settings, then Word's defaults."""
        settings = self.package.part("settings")
        formats = {}
        for kind, default in (("footnote", "decimal"), ("endnote", "lowerRoman")):
            properties = [self.body.find(f"{w('sectPr')}/{w(kind + 'Pr')}"),
                          settings.find(w(kind + "Pr")) if settings is not None else None]
            number_format = next((val(p, w("numFmt")) for p in properties if val(p, w("numFmt"))), default)
            start = next((int(val(p, w("numStart"))) for p in properties if val(p, w("numStart"))), 1)
            formats[kind] = (number_format, start)
        return formats

    def _hidden(self, run_properties):
        if on(run_properties, w("vanish")):
            return True
        style = val(run_properties, w("rStyle"))
        while style in self.styles:
            if self.styles[style]["hidden"]:
                return True
            style = self.styles[style]["based_on"]
        return False

    def _comments(self):
        root = self.package.part("comments")
        if root is None:
            return {}
        threads = {}
        extended = self.package.part("commentsExtended")
        for entry in extended.iter(f"{{{W15}}}commentEx") if extended is not None else []:
            threads[entry.get(f"{{{W15}}}paraId")] = (entry.get(f"{{{W15}}}paraIdParent"),
                                                     entry.get(f"{{{W15}}}done") == "1")
        # Comments are their own story in Word: their lists number separately from the body's.
        numbering = Numbering(self.package.part("numbering"), self.styles)
        comments, by_para_id = {}, {}
        for element in root.findall(w("comment")):
            comment_id, lines = element.get(w("id")), []
            paragraphs = element.findall(w("p"))
            for paragraph in paragraphs:
                properties = paragraph.find(w("pPr"))
                label, _ = numbering.label(properties, val(properties, w("pStyle")) or self.default_style)
                text = " ".join(self._text(paragraph, []).split())
                if text:
                    lines.append(f"{label} {text}".strip())
                # commentsExtended keys a comment by the paraId of its last paragraph.
                by_para_id[paragraph.get(f"{{{W14}}}paraId")] = comment_id
            parent, resolved = threads.get((paragraphs or [element])[-1].get(f"{{{W14}}}paraId"), (None, False))
            comments[comment_id] = Comment(re.sub(r" \[\d+\]$", "", element.get(w("author")) or ""),
                                           (element.get(w("date")) or "")[:10], " / ".join(lines), parent, resolved)
        for comment in comments.values():
            comment.parent = by_para_id.get(comment.parent)
        return comments

    # #endregion

    # #region Body

    def blocks(self):
        """Paragraphs and tables (lists of Rows) in document order."""
        # Built once: numbering counters and comment anchors advance as the body is read.
        if self._blocks is None:
            self._blocks = list(self._container(self.body))
        return self._blocks

    def _container(self, element):
        carried, carried_refs = "", []
        for child in element:
            if child.tag == w("p"):
                refs = list(carried_refs)
                text = carried + self._text(child, refs)
                for anchor in self.anchors.values():
                    if anchor[0]:
                        anchor.append(" ")
                # Word joins a paragraph whose mark is deleted to the next one, which keeps its own style.
                if child.find(f"{w('pPr')}/{w('rPr')}/{w('del')}") is not None:
                    carried, carried_refs = text, refs
                    continue
                carried, carried_refs = "", []
                yield self._paragraph(child, text, refs)
                continue
            if carried or carried_refs:
                yield Paragraph(tidy(carried), None, "", 0, False, carried_refs)
                carried, carried_refs = "", []
            if child.tag == w("tbl"):
                yield [self._row(row) for row in self._children(child, w("tr"))
                       if row.find(f"{w('trPr')}/{w('del')}") is None]
            elif child.tag in (w("sdt"), w("customXml")):
                yield from self._container(child.find(w("sdtContent")) if child.tag == w("sdt") else child)
        if carried or carried_refs:
            yield Paragraph(tidy(carried), None, "", 0, False, carried_refs)

    @staticmethod
    def _children(element, tag):
        """Direct children with this tag, looking through content-control and custom-XML wrappers."""
        for child in element:
            if child.tag == tag:
                yield child
            elif child.tag == w("sdt"):
                yield from Document._children(child.find(w("sdtContent")), tag)
            elif child.tag == w("customXml"):
                yield from Document._children(child, tag)

    def _row(self, row):
        # Each w:tc once: a merged cell is one w:tc spanning several grid columns or continued rows.
        cells, refs = [], []
        for cell in self._children(row, w("tc")):
            parts = []
            for block in self._container(cell):
                if isinstance(block, list):
                    parts.append(" / ".join(" | ".join(r.cells) for r in block))
                    refs += [ref for r in block for ref in r.comments]
                else:
                    parts.append(block.inline().replace("\n", " / "))
                    refs += block.comments
            cells.append(" ".join(part for part in parts if part))
        return Row(cells, refs)

    def _text(self, element, refs):
        parts = []
        for child in element:
            tag = child.tag
            if tag in NOT_TEXT:
                self.deleted_comments.update(ref.get(w("id")) for ref in child.iter(w("commentReference")))
                continue
            if tag == w("r") and self._hidden(child.find(w("rPr"))):
                # Word hides it on screen but keeps it in the file; show it, marked, rather than lose it.
                hidden = self._text(child, refs)
                if hidden and parts and parts[-1].startswith("[hidden text: "):
                    parts[-1] = parts[-1][:-1] + hidden + "]"
                elif hidden:
                    parts.append(f"[hidden text: {hidden}]")
                continue
            if tag in (w("t"), M_T):
                parts.append(child.text or "")
                for anchor in self.anchors.values():
                    if anchor[0]:
                        anchor.append(child.text or "")
            elif tag == w("cr") or (tag == w("br") and child.get(w("type")) in LINE_BREAKS):
                parts.append("\n")
            elif tag in BREAKS:
                parts.append(" ")
            elif tag in (w("noBreakHyphen"), w("softHyphen")):
                parts.append("-" if tag == w("noBreakHyphen") else "")
            elif tag == w("sym"):
                parts.append(chr(int(child.get(w("char")), 16)))
            elif tag in (A_BLIP, V_IMAGEDATA):
                rid = child.get(f"{{{R}}}embed") or child.get(f"{{{R}}}id")
                if rid in self.images:
                    parts.append(f" [image: {posixpath.basename(self.images[rid])}] ")
            elif tag in (w("footnoteReference"), w("endnoteReference")):
                kind = "footnote" if tag == w("footnoteReference") else "endnote"
                number_format, start = self.note_format[kind]
                mark = Numbering.format(start + self.note_numbers[kind], number_format)
                self.note_numbers[kind] += 1
                parts.append(f"[{kind} {mark}: {self.notes[kind].get(child.get(w('id')), '')}]")
            elif tag == w("txbxContent"):
                paragraphs = (" ".join(self._text(p, refs).split()) for p in child.iter(w("p")))
                parts.append(f" [text box: {' / '.join(p for p in paragraphs if p)}] ")
            elif tag == w("commentRangeStart"):
                self.anchors[child.get(w("id"))] = [True]
            elif tag == w("commentRangeEnd") and child.get(w("id")) in self.anchors:
                self.anchors[child.get(w("id"))][0] = False
            elif tag == w("commentReference"):
                refs.append(child.get(w("id")))
            else:
                parts.append(self._text(child, refs))
        return "".join(parts)

    def _paragraph(self, element, text, refs):
        properties = element.find(w("pPr"))
        style_id = val(properties, w("pStyle")) or self.default_style
        label, depth = self.numbering.label(properties, style_id)
        name = self.styles.get(style_id, {}).get("name", "")
        heading = self._heading_level(properties, style_id)
        return Paragraph(" ".join(text.split()) if heading else tidy(text), heading, label, depth,
                         name.lower().startswith("toc"), refs)

    def _heading_level(self, properties, style_id):
        outline = val(properties, w("outlineLvl"))
        style = style_id
        while outline is None and style in self.styles:
            outline = self.styles[style]["outline"]
            if outline is None and (match := HEADING_NAME.fullmatch(self.styles[style]["name"])):
                return int(match.group(1))
            style = self.styles[style]["based_on"]
        # Outline level 9 means body text.
        return int(outline) + 1 if outline is not None and int(outline) < 9 else None

    # #endregion

    def sections(self):
        """(key, title, level, block) for every block: the innermost heading above it ("" before the first)."""
        key, title, level, outline = "", "", 0, [0] * 9
        for block in self.blocks():
            if isinstance(block, Paragraph):
                if block.toc:
                    continue
                if block.heading:
                    outline[block.heading - 1] += 1
                    outline[block.heading:] = [0] * (9 - block.heading)
                    numbered = block.label and block.label != "-"
                    key = block.label.rstrip(".)") if numbered else "§" + ".".join(
                        str(n) for n in outline[:block.heading])
                    title, level = block.text, block.heading
            yield key, title, level, block

    def visible_comments(self, refs):
        """(id, comment) for each ref, minus threads that start on deleted text: accepting the deletion removes them."""
        visible = []
        for ref in refs:
            root = self.thread_root(ref)
            if ref in self.comments and root not in self.deleted_comments:
                visible.append((ref, self.comments[ref]))
        return visible

    def thread_root(self, ref):
        while ref in self.comments and self.comments[ref].parent in self.comments:
            ref = self.comments[ref].parent
        return ref

    def comment_lines(self, refs):
        lines = []
        for ref, comment in self.visible_comments(refs):
            anchor = " ".join("".join(self.anchors.get(ref, [False])[1:]).split())
            if len(anchor) > 120:
                anchor = anchor[:117] + "…"
            flags = (", reply" if comment.parent else "") + (", resolved" if comment.resolved else "")
            target = f' on "{anchor}"' if anchor else ""
            lines.append(f"[COMMENT by {comment.author}, {comment.date}{flags}]{target}: {comment.text}")
        return lines

    def image(self, name):
        return self.package.zip.read(next(t for t in self.images.values() if posixpath.basename(t) == name))


# #region Commands

def block_lines(document, block):
    """What `section` prints for a block, without headings."""
    if isinstance(block, list):
        lines = []
        for row in block:
            lines.append(" | ".join(row.cells))
            lines += [f"  {line}" for line in document.comment_lines(row.comments)]
        return lines
    indent = "  " * block.depth if block.label else ""
    lines = []
    if block.text and not block.heading:
        # Lines after a manual line break align under the text, not under the list number.
        continuation = indent + " " * (len(block.label) + 1 if block.label else 0)
        first, *rest = block.inline().split("\n")
        lines = [indent + first] + [continuation + line for line in rest]
    return lines + [f"{indent}  {line}" for line in document.comment_lines(block.comments)]


def outline_entries(document):
    """(key, title, level, characters) per heading; characters include the subsections."""
    entries, open_entries = [], []
    for key, title, level, block in document.sections():
        if isinstance(block, Paragraph) and block.heading:
            while open_entries and open_entries[-1][2] >= level:
                open_entries.pop()
            entries.append([key, title, level, 0])
            open_entries.append(entries[-1])
        size = sum(len(line) + 1 for line in block_lines(document, block))
        if isinstance(block, Paragraph) and block.heading:
            size += len(block.text) + 1
        for entry in open_entries:
            entry[3] += size
    return entries


def print_outline(document, entries):
    for key, title, level, size in entries:
        print(f"{key}\t{'  ' * (level - 1)}{title}  ({size / 1000:.1f}k chars)")


def command_outline(document, args):
    text_filter = (args.filter or "").translate(FOLD).lower()
    entries = [e for e in outline_entries(document) if text_filter in f"{e[0]} {e[1]}".translate(FOLD).lower()]
    if not entries:
        print("-- no headings" + (f" matching {args.filter!r}" if args.filter else ""))
        return 1
    print_outline(document, entries)
    return 0


def command_section(document, args):
    wanted = args.number.rstrip(".)")
    entries = outline_entries(document)
    keys = {entry[0] for entry in entries}
    if wanted not in keys and "§" + wanted in keys:
        wanted = "§" + wanted
    match = next((entry for entry in entries if entry[0] == wanted), None)
    if match is None:
        print(f"-- no section {args.number}; run `outline` for the numbers")
        return 1
    if match[3] > SECTION_LIMIT and not args.full:
        descendants = []
        for entry in entries[entries.index(match) + 1:]:
            if entry[2] <= match[2]:
                break
            descendants.append(entry)
        top = min((entry[2] for entry in descendants), default=None)
        subsections = [entry for entry in descendants if entry[2] == top]
        print(f"-- section {match[0]} is {match[3] / 1000:.0f}k characters. Read a subsection, or pass --full:")
        print_outline(document, subsections)
        return 1

    images, inside = [], False
    for key, title, level, block in document.sections():
        if isinstance(block, Paragraph) and block.heading:
            if key == wanted and title == match[1]:
                inside = True
            elif inside and level <= match[2]:
                break
        if not inside:
            continue
        if isinstance(block, Paragraph) and block.heading:
            print(f"\n{'#' * block.heading} {'' if key.startswith('§') else key + ' '}{block.text}".rstrip())
        for line in block_lines(document, block):
            print(line)
            images += re.findall(r"\[image: ([^\]]+)\]", line)
    if args.images and images:
        args.images.mkdir(parents=True, exist_ok=True)
        for name in dict.fromkeys(images):
            (args.images / name).write_bytes(document.image(name))
        print(f"\n-- {len(set(images))} images saved to {args.images}")
    return 0


def command_search(document, args):
    try:
        regex = re.compile(args.pattern.translate(FOLD), re.IGNORECASE)
    except re.error as error:
        print(f"-- invalid regex {args.pattern!r}: {error}")
        return 2
    hits, sections = 0, set()
    for key, title, _, block in document.sections():
        if isinstance(block, list):
            texts = [t for row in block for t in [" | ".join(row.cells)] + document.comment_lines(row.comments)]
        else:
            texts = [block.inline()] + document.comment_lines(block.comments)
        for text in texts:
            match = regex.search(text.translate(FOLD))
            if not match:
                continue
            start = max(0, match.start() - 150)
            snippet = ("…" if start else "") + text[start:start + 300] + ("…" if start + 300 < len(text) else "")
            snippet = snippet.replace("\n", " / ")
            print(f"{f'{key} {title}' if key else '(before the first heading)'}: {snippet}")
            hits += 1
            sections.add(key)
    print(f"-- {hits} matches in {len(sections)} sections" if hits else "-- no matches")
    return 0 if hits else 1


def command_comments(document, args):
    count = 0
    for key, title, _, block in document.sections():
        refs = [ref for row in block for ref in row.comments] if isinstance(block, list) else block.comments
        if args.open:
            refs = [ref for ref in refs if not getattr(document.comments.get(document.thread_root(ref)), "resolved", False)]
        for line in document.comment_lines(refs):
            print(f"{f'{key} {title}' if key else '(before the first heading)'}: {line}")
            count += 1
    print(f"-- {count} comments" if count else "-- no comments")
    return 0 if count else 1


# #endregion


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    outline = commands.add_parser("outline", help="headings with numbers and sizes")
    outline.add_argument("filter", nargs="?", help="only headings whose number or title contains this")
    section = commands.add_parser("section", help="text of one section and its subsections")
    section.add_argument("number", help="section number from `outline`, e.g. 2.4.1 or §3.2")
    section.add_argument("--full", action="store_true", help=f"print even above {SECTION_LIMIT:,} characters")
    section.add_argument("--images", type=Path, metavar="DIR", help="save the section's images into DIR")
    search = commands.add_parser("search", help="paragraphs, table rows and comments matching a regex")
    search.add_argument("pattern")
    comments = commands.add_parser("comments", help="every review comment with its section")
    comments.add_argument("--open", action="store_true", help="leave out resolved threads")
    args = parser.parse_args()

    try:
        document = Document(args.file)
    except (OSError, zipfile.BadZipFile, KeyError, StopIteration, ElementTree.ParseError) as error:
        print(f"-- cannot read {args.file} as a .docx: {error}")
        return 2
    handlers = {"outline": command_outline, "section": command_section, "search": command_search,
                "comments": command_comments}
    return handlers[args.command](document, args)


if __name__ == "__main__":
    sys.exit(main())
