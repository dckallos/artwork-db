"""
Grep-gate test: no museum identifiers may appear in framework ``.py``.

This enforces the prime directive from AGENTS.md -- behavior is configured in YAML, never
hardcoded in Python. Adding a source must require editing zero framework ``.py`` files, so
no source-specific identifier may leak into the package. The regex matches AGENTS.md's gate.

The test files themselves are intentionally NOT scanned: museum names are allowed in tests
(and none are used here anyway -- the suite is data-driven).
"""
from __future__ import annotations

import re
from pathlib import Path

_PACKAGE = Path(__file__).resolve().parents[2] / "artwork_orchestration"

# Mirrors the gate documented in AGENTS.md.
_GATE = re.compile(r"\b(met|aic|cma)\b|metropolitan|art institute|chicago|cleveland", re.IGNORECASE)


def test_no_museum_identifiers_in_framework_py() -> None:
    offenders: list[str] = []
    for py in sorted(_PACKAGE.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _GATE.search(line):
                rel = py.relative_to(_PACKAGE.parent)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "museum identifiers found in framework .py (config belongs in YAML):\n  "
        + "\n  ".join(offenders)
    )
