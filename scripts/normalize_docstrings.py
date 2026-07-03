#!/usr/bin/env python3
"""
normalize_docstrings.py -- put the triple quotes of docstrings on their own lines.

Scans a repository for Python files and rewrites *docstrings* and *standalone
triple-quoted string statements* (the block-comment idiom) so that:

  * the opening triple quote is alone on its line, and
  * the closing triple quote is alone on its line,

turning either of these malformed shapes:

    \"\"\"First line stuck to the opening quotes.
    \"\"\"

    \"\"\"A whole docstring squeezed onto one line.\"\"\"

into the canonical shape:

    \"\"\"
    First line stuck to the opening quotes.
    \"\"\"

WHY AST, NOT LINE FIND/REPLACE
------------------------------
A naive read-lines/replace pass cannot tell a docstring from a triple-quoted
string that is a real value (an assignment, a call argument, an element of a
list). It also trips over ''' vs \"\"\", string prefixes (r/b/f/u), and quotes
that merely appear *inside* other strings. This tool parses each file with the
``ast`` module and only rewrites string literals that are used as statements
(module/class/function docstrings and bare triple-quoted string expressions),
using each node's exact source offsets. Code, values, and f-strings are never
touched. The transform is idempotent.

USAGE
-----
    python scripts/normalize_docstrings.py [PATHS ...]        # dry run + diff
    python scripts/normalize_docstrings.py --write [PATHS...] # apply in place
    python scripts/normalize_docstrings.py --check [PATHS...] # CI: exit 1 if any
    python scripts/normalize_docstrings.py --selftest         # run internal tests

With no PATHS, the current directory is scanned. Common virtualenv/build/vcs
directories are skipped by default (see DEFAULT_EXCLUDES).
"""
from __future__ import annotations

import argparse
import ast
import difflib
import io
import os
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__", ".mypy_cache",
    ".pytest_cache", ".tox", ".eggs", ".ruff_cache", "build", "dist",
    "node_modules", "site-packages",
}

_TRIPLES = ('"""', "'''")


# --------------------------------------------------------------------------- #
# Core transform (pure string -> string, no I/O).
# --------------------------------------------------------------------------- #
def _split_prefix(literal: str) -> Tuple[str, str]:
    """
    Split a string literal into its (prefix, rest), e.g. ``r\"\"\"x\"\"\"`` ->
    ``('r', '\"\"\"x\"\"\"')``. The prefix is any leading run before the quote.
    """
    i = 0
    while i < len(literal) and literal[i] not in ('"', "'"):
        i += 1
    return literal[:i], literal[i:]


def reformat_triple_quoted(literal: str, indent: str) -> Optional[str]:
    """
    Return the canonical form of a triple-quoted string literal, or ``None`` if
    it is already canonical or must be left untouched.

    ``literal`` is the exact source text of the string (optionally prefixed).
    ``indent`` is the leading whitespace of the statement, used for the closing
    quote and for re-homing a first line that was glued to the opening quote.
    Interior lines are preserved verbatim so embedded indentation / examples are
    never corrupted.
    """
    prefix, rest = _split_prefix(literal)
    if len(rest) < 6 or rest[:3] not in _TRIPLES:
        return None
    delim = rest[:3]
    if not rest.endswith(delim):
        return None
    body = rest[3:-3]
    # If the delimiter appears inside the body it is implicit concatenation or a
    # malformed literal -- refuse to touch it (safety over cleverness).
    if delim in body:
        return None

    if "\n" not in body:
        content = body.strip()
        if content == "":
            new = f"{prefix}{delim}\n{indent}{delim}"
        else:
            new = f"{prefix}{delim}\n{indent}{content}\n{indent}{delim}"
    else:
        lines = body.split("\n")
        # Opening line: if content is glued to the quotes, drop it to its own
        # line (re-indented); if the opening line is blank, remove that blank.
        if lines[0].strip() != "":
            lines[0] = indent + lines[0].strip()
        else:
            lines = lines[1:]
        # Closing line: drop a trailing whitespace-only line so the closing
        # quote lands on its own fresh line.
        if lines and lines[-1].strip() == "":
            lines = lines[:-1]
        content_block = "\n".join(lines)
        new = f"{prefix}{delim}\n{content_block}\n{indent}{delim}"

    return new if new != literal else None


# --------------------------------------------------------------------------- #
# File-level processing.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Replacement:
    start: int
    end: int
    new: str


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _iter_string_statement_nodes(tree: ast.AST):
    """
    Yield every ``ast.Expr`` whose value is a ``str`` constant -- i.e. module,
    class, and function docstrings plus standalone triple-quoted string
    statements. f-strings (JoinedStr), bytes, and strings inside expressions are
    naturally excluded.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            yield node.value


def compute_new_text(text: str) -> str:
    """
    Return ``text`` with every eligible triple-quoted string statement
    normalized. Raises ``SyntaxError`` if the source does not parse.
    """
    tree = ast.parse(text)
    lines = text.split("\n")
    starts = _line_starts(text)

    replacements: List[Replacement] = []
    for node in _iter_string_statement_nodes(tree):
        if node.end_lineno is None or node.end_col_offset is None:
            continue
        start_line = lines[node.lineno - 1]
        indent = start_line[: node.col_offset]
        # Only proceed when everything before the literal is pure indentation;
        # this rejects cases like ``x = 1; \"\"\"doc\"\"\"`` where the column
        # offset would capture code, not indentation.
        if indent.strip() != "":
            continue
        start = starts[node.lineno - 1] + node.col_offset
        end = starts[node.end_lineno - 1] + node.end_col_offset
        literal = text[start:end]
        new = reformat_triple_quoted(literal, indent)
        if new is not None:
            replacements.append(Replacement(start, end, new))

    # Apply right-to-left so earlier offsets stay valid.
    replacements.sort(key=lambda r: r.start, reverse=True)
    out = text
    for r in replacements:
        out = out[: r.start] + r.new + out[r.end :]
    return out


def read_source(path: Path) -> Tuple[str, str, str]:
    """
    Read ``path`` and return (normalized_text, encoding, newline). Text is
    normalized to ``\\n`` for parsing; the detected dominant newline is returned
    so the file can be written back in its original style.
    """
    raw = path.read_bytes()
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    except SyntaxError:
        encoding = "utf-8"
    text = raw.decode(encoding)
    newline = "\r\n" if "\r\n" in text else ("\r" if "\r" in text else "\n")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized, encoding, newline


def process_file(path: Path, write: bool) -> Tuple[bool, str]:
    """
    Return (changed, unified_diff). Writes the file only when ``write`` is True
    and a change is needed. Files that fail to parse/decode are skipped.
    """
    try:
        text, encoding, newline = read_source(path)
    except (UnicodeDecodeError, OSError) as exc:
        print(f"  skip (read error): {path}: {exc}", file=sys.stderr)
        return False, ""

    try:
        new_text = compute_new_text(text)
    except SyntaxError as exc:
        print(f"  skip (syntax error): {path}: {exc}", file=sys.stderr)
        return False, ""

    if new_text == text:
        return False, ""

    diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=str(path),
        )
    )
    if write:
        data = new_text.replace("\n", newline).encode(encoding)
        path.write_bytes(data)
    return True, diff


# --------------------------------------------------------------------------- #
# Discovery.
# --------------------------------------------------------------------------- #
def iter_python_files(paths: List[str], excludes: set) -> List[Path]:
    found: List[Path] = []
    seen: set = set()

    def add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            found.append(p)

    for raw in paths:
        p = Path(raw)
        if p.is_file():
            if p.suffix == ".py":
                add(p)
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = [
                d for d in dirs
                if d not in excludes and not (d.startswith(".") and d not in {"."})
            ]
            for name in sorted(files):
                if name.endswith(".py"):
                    add(Path(root) / name)
    return sorted(found, key=lambda x: str(x))


# --------------------------------------------------------------------------- #
# Self-test (no filesystem needed).
# --------------------------------------------------------------------------- #
def _selftest() -> int:
    cases = [
        # (source, expected)
        (
            'def f():\n    """One liner."""\n    return 1\n',
            'def f():\n    """\n    One liner.\n    """\n    return 1\n',
        ),
        (
            '"""First line glued to quotes.\nSecond line.\n"""\n',
            '"""\nFirst line glued to quotes.\nSecond line.\n"""\n',
        ),
        (
            'class C:\n    """Summary.\n\n    Args:\n        x: foo\n    """\n',
            'class C:\n    """\n    Summary.\n\n    Args:\n        x: foo\n    """\n',
        ),
        # closing quote glued to last content line
        (
            '    """\n    Foo.\n    Bar."""\n',
            None,  # not a valid standalone module; tested separately below
        ),
    ]
    ok = True
    # Direct literal-level checks (indentation-aware).
    assert reformat_triple_quoted('"""x"""', "") == '"""\nx\n"""'
    assert reformat_triple_quoted('"""\nx\n"""', "") is None  # already canonical
    assert reformat_triple_quoted('"""a\nb\n"""', "") == '"""\na\nb\n"""'
    assert reformat_triple_quoted('"""Foo.\n    Bar."""', "    ") == '"""\n    Foo.\n    Bar.\n    """'
    # ''' delimiter + prefix preserved
    assert reformat_triple_quoted("r'''x'''", "") == "r'''\nx\n'''"
    # implicit-concat / delimiter-in-body is refused
    assert reformat_triple_quoted('"""a""" """b"""', "") is None

    for src, expected in cases:
        if expected is None:
            continue
        got = compute_new_text(src)
        if got != expected:
            ok = False
            print("SELFTEST FAIL\n--- source ---\n" + src +
                  "\n--- expected ---\n" + expected +
                  "\n--- got ---\n" + got, file=sys.stderr)
        # idempotency
        if compute_new_text(got) != got:
            ok = False
            print("SELFTEST FAIL (not idempotent) for:\n" + got, file=sys.stderr)

    # A triple-quoted string that is a VALUE must never be touched.
    value_src = 'X = """not a docstring, do not touch"""\n'
    if compute_new_text(value_src) != value_src:
        ok = False
        print("SELFTEST FAIL: rewrote a non-statement string value", file=sys.stderr)

    print("selftest: PASS" if ok else "selftest: FAIL")
    return 0 if ok else 1


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize triple-quoted docstrings so their quotes sit on their own lines.",
    )
    parser.add_argument("paths", nargs="*", default=["."], help="Files or directories (default: .).")
    parser.add_argument("-w", "--write", action="store_true", help="Apply changes in place.")
    parser.add_argument("--check", action="store_true", help="Exit 1 if any file would change (no writes).")
    parser.add_argument("--no-diff", action="store_true", help="Do not print diffs.")
    parser.add_argument("-q", "--quiet", action="store_true", help="Only print the summary.")
    parser.add_argument("--exclude", action="append", default=[], help="Extra directory name to skip (repeatable).")
    parser.add_argument("--selftest", action="store_true", help="Run internal tests and exit.")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    if sys.version_info < (3, 8):
        print("error: requires Python 3.8+ (needs end_lineno/end_col_offset).", file=sys.stderr)
        return 2

    excludes = set(DEFAULT_EXCLUDES) | set(args.exclude)
    paths = args.paths or ["."]
    files = iter_python_files(paths, excludes)

    changed_files: List[Path] = []
    for path in files:
        changed, diff = process_file(path, write=args.write)
        if changed:
            changed_files.append(path)
            if not args.quiet and not args.no_diff and diff:
                sys.stdout.write(diff)

    verb = "rewrote" if args.write else "would rewrite"
    print(f"\nscanned {len(files)} file(s); {verb} {len(changed_files)} file(s).")
    for p in changed_files:
        print(f"  {verb}: {p}")

    if args.check and changed_files:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
