#!/usr/bin/env python3
"""Facts about the current change in a git repo, for the change-review skill: changed files, things worth
a look (leftovers, TODOs, removed tests or comments, new dependencies, debug output), a format check of the
changed files, the checks to run and the instruction files to read. Read-only: never changes the repo.

Usage: python review_facts.py [--base REF] [--quick] [--repo DIR]
  --base REF  compare with REF (e.g. main or a commit) instead of HEAD; committed work since REF counts too
  --quick     skip the slow format check (dotnet format)
Exit code: 0 = nothing flagged, 1 = something to look at, 2 = could not run.
"""
from __future__ import annotations  # Python 3.9: `X | None` and `list[str]` in annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

MAX_ITEMS = 12  # per list, so the output stays small in a local model's context
SLOW_TIMEOUT_S = 300
PYTHON = "python3" if shutil.which("python3") else "python"  # Windows has only `python`

LANG_EXT = {".go": "go", ".cs": "csharp", ".py": "python", ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
            ".mjs": "js", ".cjs": "js"}
TEST_PATH = re.compile(r"(_test\.go|_test\.py|\.(test|spec)\.[cm]?[jt]sx?|(?-i:Tests?\.cs))$|(^|/)test_[^/]*\.py$|"
                       r"(^|/)(tests?|__tests__|[^/]*\.Tests?)/", re.I)
DOC_PATH = re.compile(r"\.(md|rst|txt|adoc)$|(^|/)docs?/", re.I)
LEFTOVER = re.compile(r"(^|/)(debug|tmp|temp|scratch|repro|out)[^/]*$|"
                      r"\.(orig|rej|bak|tmp|log|out|swp|pyc|exe|dll|so|test)$|~$", re.I)
ROOT_SCRIPT = (".sh", ".py", ".go", ".cs", ".csx", ".csproj", ".js", ".ts", ".txt")
TODO = re.compile(r"(//|#|/\*|^\s*\*|<!--|--)[^\"'`]*\b(TODO|FIXME|XXX|HACK)\b")  # in a comment, not in code
DEBUG = re.compile(r"\b(fmt\.Print(ln|f)?|println!?|Console\.Write(Line)?|Debug\.Write(Line)?|console\.(log|debug)|"
                   r"pprint|breakpoint\(\)|debugger;)|^\s*print\(")
COMMENT = re.compile(r"^\s*(//+|#(?!region|endregion|!|pragma|nullable|if|else|endif|define)|/\*+|\*(?!/))\s?(.*)$")
CODE_KEYWORD = re.compile(r"^(if|for|while|switch|return|var|const|func|def|class|import|from|try|except|else|"
                          r"elif|case|using|public|private|await)\b")
TEST_NAME = [re.compile(r"\bfunc\s+((?:Test|Benchmark|Fuzz)\w*)\s*\("),
             re.compile(r"\bdef\s+(test_\w+)\s*\("),
             re.compile(r"\b(?:it|test)\(\s*['\"`]([^'\"`]+)")]
CS_TEST_METHOD = re.compile(r"\b(?:public|internal|private)\s+(?:async\s+)?(?:Task|ValueTask|void)\s+(\w+)\s*\(")
DEP_LINE = {"go.mod": re.compile(r"^\s*(?:require\s+)?([\w-]+\.[\w.-]+/\S+)\s+v\d"),
            "csproj": re.compile(r'<PackageReference\s+Include="([^"]+)"'),
            "requirements": re.compile(r"^\s*([A-Za-z][\w.-]*)"),
            "pyproject.toml": re.compile(r'^\s*"([A-Za-z][\w.-]*)\s*(?:[<>=!~;\[][^"]*)?",?\s*$'),
            "package.json": re.compile(r'^\s*"((?!version|name|node|npm|main|type|license)[@\w/.-]+)":\s*"[\^~>=<]*\d')}
# Printing is these files' job: CLI entry points and scripts.
CLI_PATH = re.compile(r"(^|/)(cmd/|scripts?/|bin/|tools/|cli[^/]*$|main\.\w+$|program\.cs$|__main__\.py$)", re.I)
CONCURRENCY = re.compile(r"\bgo\s+(func\b|\w+\()|\bchan\b|\bsync\.|\batomic\.")
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", ".goosehints", "CONTRIBUTING.md", "README.md")
PROJECT_MARKERS = {"go": ("go.mod",), "csharp": ("*.sln", "*.slnx", "*.csproj"), "python": ("pyproject.toml", "setup.py",
                   "setup.cfg", "requirements.txt"), "js": ("package.json",)}


# region git
def fail(msg: str) -> NoReturn:
    print(f"review_facts: {msg}", file=sys.stderr)
    sys.exit(2)


def git(root: Path, *args: str) -> str:
    # --no-optional-locks: works on a read-only .git (sandbox) and doesn't touch the index.
    result = subprocess.run(["git", "--no-optional-locks", *args], cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def changed_files(root: Path, base: str) -> dict[str, dict]:
    """path -> {status, added, removed, lines: [(lineno, text)], gone: [text], binary} for tracked changes
    since base and untracked files (all their lines count as added)."""
    files: dict[str, dict] = {}
    for line in git(root, "diff", "--name-status", "-M", base).splitlines():
        parts = line.split("\t")
        files[parts[-1]] = {"status": parts[0][0], "added": 0, "removed": 0, "lines": [], "gone": [], "binary": False}
    cur, old_path, new_line = None, "", 0
    for line in git(root, "diff", "-M", "-U0", "--no-color", base).splitlines():
        if line.startswith("diff --git "):
            cur = None
        elif line.startswith("--- "):
            old_path = line[6:] if line.startswith("--- a/") else ""
        elif line.startswith("+++ "):
            # A deleted file has no b/ side; its removed lines still count (e.g. a deleted test file).
            cur = files.get(line[6:] if line.startswith("+++ b/") else old_path)
        elif line.startswith("Binary files") and " and b/" in line:
            path = line.rsplit(" and b/", 1)[-1].removesuffix(" differ")
            if path in files:
                files[path]["binary"] = True
        elif m := re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line):
            new_line = int(m[1])
        elif cur is None:
            continue
        elif line.startswith("+"):
            cur["added"] += 1
            cur["lines"].append((new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            cur["removed"] += 1
            cur["gone"].append(line[1:])
    for path in git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if not path:
            continue
        info = {"status": "?", "added": 0, "removed": 0, "lines": [], "gone": [], "binary": False}
        data = (root / path).read_bytes() if (root / path).is_file() else b""
        if b"\0" in data[:8000]:
            info["binary"] = True
        elif len(data) <= 1_000_000:
            text = data.decode(errors="replace").splitlines()
            info["lines"] = list(enumerate(text, start=1))
            info["added"] = len(text)
        files[path] = info
    return files
# endregion


# region heuristics
def kind(path: str) -> str:
    if TEST_PATH.search(path):
        return "test"
    if DOC_PATH.search(path):
        return "doc"
    return "code" if Path(path).suffix in LANG_EXT or path.endswith((".csproj", ".sql", ".sh")) else "other"


def is_commented_code(line: str) -> bool:
    """A comment whose text reads like a statement rather than prose (approximate)."""
    m = COMMENT.match(line)
    if not m:
        return False
    text = m[2].strip()
    if "→" in text or "->" in text and "=" in text or len(re.findall(r"(?<![=!<>:+\-])=(?!=)", text)) > 1:
        return False
    return bool(re.search(r":=|\+=|-=|==|!=", text) and not text.endswith(".")
                or CODE_KEYWORD.match(text) and text.endswith(("{", ":", ";", ")"))
                or re.match(r"^[\w.\[\]]+\s*=\s*[^\s=]", text) and not text.endswith(".")
                or re.match(r"^[\w.]+\(.*\)\s*;?$", text)
                or text.endswith(("{", ";")) or text == "}")


def test_names(path: str, lines: list[str]) -> set[str]:
    names = {m[1] for line in lines for pattern in TEST_NAME if (m := pattern.search(line))}
    if path.endswith(".cs") and kind(path) == "test":
        names |= {m[1] for line in lines if (m := CS_TEST_METHOD.search(line))}
    return names


def dependency_kind(path: str) -> str | None:
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".csproj"):
        return "csproj"
    if name.startswith("requirements") and name.endswith(".txt"):
        return "requirements"
    return name if name in DEP_LINE else None


def flags(files: dict[str, dict]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {k: [] for k in ("leftovers", "todos", "commented_code", "debug_output",
                                                   "tests_removed", "comments_removed", "dependencies_added")}
    all_added = {text.strip() for f in files.values() for _, text in f["lines"]}
    all_added_tests = set().union(*(test_names(p, [t for _, t in f["lines"]]) for p, f in files.items()))
    for path, f in sorted(files.items()):
        k = kind(path)
        new = f["status"] in ("A", "?")
        if new and (LEFTOVER.search(path) or f["binary"] or ("/" not in path and path.endswith(ROOT_SCRIPT))):
            found["leftovers"].append(f"{path} ({'untracked' if f['status'] == '?' else 'new'})")
            continue  # its contents would only repeat the same finding
        if k == "doc":
            continue
        for n, text in f["lines"]:
            if TODO.search(text):
                found["todos"].append(f"{path}:{n}: {text.strip()[:100]}")
            if k in ("code", "test") and is_commented_code(text):
                found["commented_code"].append(f"{path}:{n}: {text.strip()[:100]}")
            if k == "code" and not CLI_PATH.search(path) and DEBUG.search(text):
                found["debug_output"].append(f"{path}:{n}: {text.strip()[:100]}")
        removed_tests = test_names(path, f["gone"]) - all_added_tests
        found["tests_removed"] += [f"{path}: {name}" for name in sorted(removed_tests)]
        if k in ("code", "test"):
            gone_comments = [t.strip() for t in f["gone"] if COMMENT.match(t) and t.strip() not in all_added
                             and not is_commented_code(t)]
            if gone_comments:
                found["comments_removed"].append(f"{path}: {len(gone_comments)} line(s), e.g. \"{gone_comments[0][:80]}\"")
        if dep := dependency_kind(path):
            pattern = DEP_LINE[dep]
            added = {m[1] for _, t in f["lines"] if (m := pattern.search(t))}
            gone = {m[1] for t in f["gone"] if (m := pattern.search(t))}
            found["dependencies_added"] += [f"{path}: {name}" for name in sorted(added - gone)]
    return found
# endregion


# region checks
def run(cmd: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout} s"


def project_dirs(root: Path, paths: list[str], lang: str) -> list[Path]:
    """The nearest folder with a project marker (go.mod, pyproject.toml, package.json) for each changed file of
    the language, so multi-project repos get one entry per project. C#: the nearest solution folder, else the
    nearest .csproj folder (build, test and format run per solution)."""
    def nearest(start: Path, markers: tuple[str, ...]) -> Path | None:
        d = start
        while d.is_relative_to(root):
            if any(any(d.glob(marker)) for marker in markers):
                return d
            if d == root:
                return None
            d = d.parent
        return None

    dirs = []
    for path in paths:
        start = (root / path).parent
        d = (lang == "csharp" and nearest(start, ("*.sln", "*.slnx"))) or nearest(start, PROJECT_MARKERS[lang]) or root
        if d not in dirs:
            dirs.append(d)
    return dirs


def format_check(root: Path, by_lang: dict[str, list[str]], quick: bool) -> list[str]:
    out = []
    if go := by_lang.get("go"):
        if shutil.which("gofmt"):
            code, text = run(["gofmt", "-l", *go], root)
            out.append("gofmt -l (changed .go files): " + ("clean" if code == 0 and not text else
                                                            f"NOT clean: {', '.join(text.split())[:400]}"))
        else:
            out.append("gofmt: not installed, not checked")
    if py := by_lang.get("python"):
        if shutil.which("ruff"):
            code, text = run(["ruff", "format", "--check", *py], root)
            out.append("ruff format --check (changed .py files): " + ("clean" if code == 0 else f"NOT clean: {text[:400]}"))
        else:
            code, text = run([sys.executable, "-m", "py_compile", *py], root)
            out.append("ruff not installed; py_compile (syntax only): " + ("ok" if code == 0 else f"FAILED: {text[:400]}"))
    if cs := by_lang.get("csharp"):
        for d in project_dirs(root, cs, "csharp"):
            workspaces = sorted(d.glob("*.sln")) + sorted(d.glob("*.slnx")) or sorted(d.glob("*.csproj"))
            rel = [str((root / p).relative_to(d)) for p in cs if (root / p).is_relative_to(d)]
            cd = f"cd {d.relative_to(root)} && " if d != root else ""
            if len(workspaces) != 1:
                out.append(f"dotnet format: {d.relative_to(root) if d != root else 'the repo root'} has "
                           f"{len(workspaces)} solution/project files; run it per project by hand")
                continue
            cmd = ["dotnet", "format", workspaces[0].name, "--verify-no-changes", "--include", *rel]
            if quick or not shutil.which("dotnet"):
                out.append(f"not run{' (--quick)' if quick else ' (dotnet missing)'}: {cd}{' '.join(cmd)}")
                continue
            code, text = run(cmd, d, SLOW_TIMEOUT_S)
            out.append(f"{cd}{' '.join(cmd[:4])} --include <changed>: "
                       + ("clean" if code == 0 else f"NOT clean or failed: {text[-400:]}"))
    if js := by_lang.get("js"):
        out.append(f"{len(js)} JS/TS file(s): use the project's format script (see Checks to run)")
    return out or ["no code files changed"]


def suggested_checks(root: Path, by_lang: dict[str, list[str]], files: dict[str, dict]) -> list[str]:
    out = []
    makefile = root / "Makefile"
    if makefile.is_file():
        targets = re.findall(r"^([\w-]+):", makefile.read_text(errors="replace"), re.M)
        wanted = [t for t in targets if re.search(r"test|lint|check|fmt|format|build|vet|type", t)]
        if wanted:
            out.append("Makefile targets: " + ", ".join(f"make {t}" for t in wanted))
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if workflows:
        out.append("CI workflows (read for the exact commands CI runs): " +
                   ", ".join(str(w.relative_to(root)) for w in workflows))
    concurrency = any(CONCURRENCY.search(t) for p, f in files.items() if p.endswith(".go") for _, t in f["lines"])
    for lang, paths in by_lang.items():
        for d in project_dirs(root, paths, lang):
            cd = f"cd {d.relative_to(root)} && " if d != root else ""
            if lang == "go":
                cmds = ["go build ./...", "go vet ./...", "go test ./..."]
                if concurrency:
                    cmds.append("go test -race ./...  (the change touches goroutines/channels/sync; needs cgo)")
                if list(d.glob(".golangci.y*ml")) or list(root.glob(".golangci.y*ml")):
                    cmds.append("golangci-lint run ./...")
            elif lang == "csharp":
                cmds = ["dotnet build  (new warnings count as problems)", "dotnet test"]
            elif lang == "python":
                cfg = " ".join(p.read_text(errors="replace") for p in (d / "pyproject.toml", d / "ruff.toml",
                                                                         d / "setup.cfg", d / "mypy.ini") if p.is_file())
                cmds = [f"{PYTHON} -m pytest -q"]
                if "ruff" in cfg:
                    cmds.append("ruff check .")
                if "mypy" in cfg:
                    cmds.append("mypy .")
            else:
                pkg = (d / "package.json").read_text(errors="replace") if (d / "package.json").is_file() else ""
                scripts = re.findall(r'"(lint|typecheck|test|build|format|check)"\s*:', pkg)
                runner = next((r for f, r in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"))
                               if (d / f).is_file()), "npm")
                cmds = [f"{runner} run {s}" for s in scripts] or ["no package.json scripts found; see README"]
            out += [cd + c for c in cmds]
    return out


def instruction_files(root: Path, paths: list[str]) -> list[str]:
    found = []
    dirs = {root} | {(root / p).parent for p in paths}
    for d in sorted(dirs):
        while d.is_relative_to(root):
            for name in INSTRUCTION_FILES:
                f = d / name
                rel = str(f.relative_to(root))
                if f.is_file() and rel not in found:
                    found.append(rel)
            if d == root:
                break
            d = d.parent
    return found
# endregion


def show(title: str, items: list[str], hint: str = "") -> list[str]:
    if not items:
        return []
    lines = [f"- {title} ({len(items)}){': ' + hint if hint else ''}"]
    lines += [f"    {item}" for item in items[:MAX_ITEMS]]
    if len(items) > MAX_ITEMS:
        lines.append(f"    ... and {len(items) - MAX_ITEMS} more")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    top = subprocess.run(["git", "-C", args.repo, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        fail(f"{args.repo} is not inside a git repository")
    root = Path(top.stdout.strip())
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}"],
                      capture_output=True).returncode != 0:
        fail(f"--base {args.base!r} is not a commit or branch in {root}")

    files = changed_files(root, args.base)
    if not files:
        print(f"No changes against {args.base} (tracked or untracked). Nothing to review.")
        return
    live = [p for p, f in files.items() if f["status"] != "D" and (root / p).is_file()]
    by_lang: dict[str, list[str]] = {}
    for p in live:
        if lang := LANG_EXT.get(Path(p).suffix):
            by_lang.setdefault(lang, []).append(p)

    kinds: dict[str, int] = {}
    for p in files:
        kinds[kind(p)] = kinds.get(kind(p), 0) + 1
    added = sum(f["added"] for f in files.values())
    removed = sum(f["removed"] for f in files.values())
    what = "uncommitted changes" if args.base == "HEAD" else f"everything since {args.base}, committed or not"
    out = ["# Change facts", "", f"Repo: {root}. Compared with {args.base} ({what}), plus untracked files.",
           f"{len(files)} file{'s' if len(files) != 1 else ''}, +{added} -{removed} lines: " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())),
           f"Read the whole change: git diff {args.base}" + (" and each untracked (?) file" if any(
               f["status"] == "?" for f in files.values()) else ""), "", "## Files", ""]
    status_name = {"M": "modified", "A": "added", "D": "deleted", "R": "renamed", "?": "untracked", "C": "copied", "T": "type"}
    for p, f in sorted(files.items()):
        size = "binary" if f["binary"] else f"+{f['added']} -{f['removed']}"
        out.append(f"- {p}  [{status_name.get(f['status'], f['status'])}, {kind(p)}, {size}]")

    found = flags(files)
    worth = (show("Possible leftover files", found["leftovers"],
                  "scratch/debug files belong in a temp folder; keep only if the task needs them")
             + show("Tests removed", found["tests_removed"], "deleting tests needs a reason the request gives")
             + show("Dependencies added", found["dependencies_added"], "only if the request allows new dependencies")
             + show("Existing comments removed", found["comments_removed"], "fine only if the change made them wrong")
             + show("TODO/FIXME added", found["todos"])
             + show("Commented-out code added", found["commented_code"])
             + show("Debug output added", found["debug_output"], "fine in CLI output code, not as leftover debugging"))
    out += ["", "## Worth a look (heuristics: confirm each by reading the code before reporting it)", ""]
    out += worth or ["- nothing flagged"]
    formatting = format_check(root, by_lang, args.quick)
    out += ["", "## Format check (changed files only)", ""] + [f"- {line}" for line in formatting]
    out += ["", "## Checks to run (prefer the project's own commands from the instruction files and CI)", ""]
    out += [f"- {line}" for line in suggested_checks(root, by_lang, files)] or ["- none found"]
    out += ["", "## Instruction files to read", ""]
    out += [f"- {p}" for p in instruction_files(root, live)] or ["- none in the repo"]
    print("\n".join(out))
    sys.exit(1 if worth or any("NOT clean" in line or "FAILED" in line for line in formatting) else 0)


if __name__ == "__main__":
    main()
