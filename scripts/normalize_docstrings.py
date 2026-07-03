#!/usr/bin/env python3
"""
Normalize triple-quoted docstrings to the artwork-db house style.

House style (CODE_STANDARDS.md section 8): every triple-quoted docstring opens with ``\"\"\"``
alone on its own line and closes with ``\"\"\"`` alone on its own line -- even a one-line
docstring. The first line of prose is never glued to the opening quotes, and the whole
docstring is never squeezed onto a single line.

    # compliant
    def f():
        \"\"\"
        Summary on its own line.
        \"\"\"

    # violations (fixed by --write)
    def g():
        \"\"\"Glued to the opening quotes.
        \"\"\"

    def h():
        \"\"\"Whole docstring on one line.\"\"\"

The tool is AST-based: it only rewrites module/class/function DOCSTRINGS (the first
statement of a scope). It never touches triple-quoted string *values* (assignments,
call arguments, constants), so it is safe to run across the tree.

Usage:
    python scripts/normalize_docstrings.py --check PATH [PATH ...]   # report, exit 1 if any
    python scripts/normalize_docstrings.py --write PATH [PATH ...]   # rewrite in place

With no PATH, defaults to ``orchestration/artwork_orchestration`` and ``scripts``.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Tuple

_QUOTE_PREFIX_RE = re.compile(r"^[rRuUbBfF]*")
_DEFAULT_TARGETS = ("orchestration/artwork_orchestration", "scripts")


def _docstring_nodes(tree: ast.AST) -> List[ast.Constant]:
    """
    Return the string-literal nodes that are DOCSTRINGS (first stmt of a scope).
    """
    nodes: List[ast.Constant] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                nodes.append(body[0].value)
    return nodes


def _split_literal(segment: str) -> Tuple[str, str, str] | None:
    """
    Split a string literal into (prefix+quote, body, quote); None if not triple-quoted.
    """
    prefix = _QUOTE_PREFIX_RE.match(segment).group()
    rest = segment[len(prefix):]
    if rest[:3] not in ('"""', "'''"):
        return None
    quote = rest[:3]
    return prefix + quote, rest[3:-3], quote


def _is_compliant(body: str) -> bool:
    """
    A docstring body is compliant iff it opens and closes with its own line.
    """
    opens_ok = body.startswith("\n")
    closes_ok = re.search(r"\n[ \t]*$", body) is not None
    return opens_ok and closes_ok


def _normalize(segment: str, indent: str) -> str | None:
    """
    Return the normalized literal for ``segment``, or None if unchanged / not applicable.
    """
    split = _split_literal(segment)
    if split is None:
        return None
    open_q, body, quote = split
    if _is_compliant(body):
        return None

    # Keep the author's content; only fix the edges. Drop whitespace-only leading/trailing
    # lines, then re-indent the first line (a glued/one-line docstring has none) while
    # leaving continuation lines exactly as written.
    lines = body.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        lines = [""]
    first = indent + lines[0].lstrip()
    rest = lines[1:]
    inner = "\n".join([first, *rest])
    return f"{open_q}\n{inner}\n{indent}{quote}"


def _process(path: Path, write: bool) -> List[str]:
    """
    Check (and optionally fix) one file; return a list of human-readable violations.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # a broken file is not this tool's problem to fix
        return [f"{path}: skipped (syntax error: {exc})"]

    edits: List[Tuple[int, int, str, int]] = []  # (start, end, new_text, lineno)
    violations: List[str] = []
    lines_start = _line_offsets(source)

    for node in _docstring_nodes(tree):
        segment = ast.get_source_segment(source, node)
        if segment is None:
            continue
        indent = " " * node.col_offset
        new_segment = _normalize(segment, indent)
        if new_segment is None:
            continue
        violations.append(f"{path}:{node.lineno}: docstring quotes must each sit on their own line")
        start = lines_start[node.lineno - 1] + node.col_offset
        end = lines_start[node.end_lineno - 1] + node.end_col_offset
        edits.append((start, end, new_segment, node.lineno))

    if write and edits:
        for start, end, new_text, _ in sorted(edits, reverse=True):
            source = source[:start] + new_text + source[end:]
        path.write_text(source, encoding="utf-8")

    return violations


def _line_offsets(source: str) -> List[int]:
    """
    Return the character offset at which each line begins (index i -> line i+1).
    """
    offsets = [0]
    for line in source.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def _iter_py_files(targets: List[str]) -> List[Path]:
    """
    Expand target paths into .py files, skipping caches and virtualenvs.
    """
    out: List[Path] = []
    for t in targets:
        p = Path(t)
        candidates = [p] if p.is_file() else sorted(p.rglob("*.py"))
        for c in candidates:
            if c.suffix == ".py" and "__pycache__" not in c.parts and ".venv" not in c.parts:
                out.append(c)
    return out


def main(argv: List[str] | None = None) -> int:
    """
    Parse args, then check or rewrite docstrings; return a process exit code.
    """
    parser = argparse.ArgumentParser(description="Normalize triple-quoted docstrings.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="report violations; exit 1 if any")
    mode.add_argument("--write", action="store_true", help="rewrite files in place")
    parser.add_argument("paths", nargs="*", default=list(_DEFAULT_TARGETS))
    args = parser.parse_args(argv)

    files = _iter_py_files(args.paths or list(_DEFAULT_TARGETS))
    all_violations: List[str] = []
    for f in files:
        all_violations.extend(_process(f, write=args.write))

    if args.write:
        print(f"normalize_docstrings: scanned {len(files)} file(s); fixed {len(all_violations)} docstring(s).")
        return 0
    if all_violations:
        print("\n".join(all_violations))
        print(f"\nnormalize_docstrings: {len(all_violations)} violation(s). Run with --write to fix.")
        return 1
    print(f"normalize_docstrings: {len(files)} file(s) OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
