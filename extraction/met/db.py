"""
SQLite schema and connection helpers for the Met extraction pipeline.

Two tables only:
  - met_artworks:    one row per Met object_id, holds CSV fields + API image
                     URLs + enrichment state.
  - extraction_runs: one row per pipeline phase invocation for observability.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator


def load_sql(name: str) -> str:
    """Read a ``.sql`` file from the ``extraction.met.sql`` package.

    Centralizing this in one place lets every module use the same loader.
    """
    return resources.files("extraction.met.sql").joinpath(name).read_text(encoding="utf-8")


def strip_sql_comments(sql: str) -> str:
    """Remove ``--`` line comments from a SQL string.

    WHY THIS EXISTS: the Snowflake connector pyformat-binds the ENTIRE command
    string when params are passed (``command % params``), and it does not know
    SQL comments from bindable text. A single stray ``%`` in a ``-- comment``
    (e.g. documenting a ``%s`` placeholder) is therefore mis-read as a format
    specifier and blows up with "not enough arguments for format string". Stripping
    line comments before binding removes that whole class of bug -- including a
    future ``--where "culture LIKE '%greek%'"`` slice predicate.

    CAVEAT: this is a deliberately simple line-comment stripper. It would also
    remove a literal ``--`` that appeared INSIDE a single-quoted string. None of
    the Met SQL templates contain such a literal (all dynamic values are bound),
    so this is safe here; revisit if that ever changes.
    """
    return re.sub(r"--[^\n]*", "", sql)



def initialize_database(sqlite_path: Path) -> None:
    """Create the SQLite database file and apply the schema if missing."""
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(sqlite_path)) as conn:
        conn.executescript(load_sql("schema.sql"))
        conn.commit()


@contextmanager
def connect(sqlite_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with Row factory; closes on exit."""
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
