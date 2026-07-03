#!/usr/bin/env python3
"""
Append a line to session-progress-log.md.

The workspace FS does not support O_APPEND (>>), so we read-then-rewrite in 'w'
mode (truncate-write IS supported). Usage: python3 logp.py "message"
Prefixes each entry with the fork id (from .fork_id) and a UTC timestamp. Before
writing, warns to stdout if a DIFFERENT fork id already appears in the log.
"""
import datetime
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent
fork_id = (root / ".fork_id").read_text().strip()
log = root / "session-progress-log.md"
msg = " ".join(sys.argv[1:])
ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

existing = log.read_text() if log.exists() else ""
# Fork-collision detector: any [fork-XXXX] tag that isn't ours.
import re
others = {m for m in re.findall(r"\[fork-[0-9a-f]+\]", existing)} - {f"[{fork_id}]"}
if others:
    print(f"WARNING: other fork id(s) present in log: {sorted(others)} — reconcile!")

log.write_text(existing + f"[{fork_id}][{ts}] {msg}\n")
print(f"logged: [{fork_id}][{ts}] {msg}")
