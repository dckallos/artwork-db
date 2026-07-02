"""Placeholder CMA (Cleveland Museum of Art) extraction CLI.

A STUB that proves the orchestration "add a museum" path without real network work.
Honors the CLI contract used by the orchestration layer's subprocess runner:

    python -m extraction.cma.run <subcommand> [flags]   ->  runs one phase, exits 0.

Replace the body with a real snapshot loader (download the Cleveland OpenAccess dump,
COPY into BRONZE.RAW_CMA_ARTWORKS / RAW_CMA_AGENTS).
"""
from __future__ import annotations

import sys
from typing import List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    subcommand = args[0] if args else ""
    print(f"[cma stub] subcommand={subcommand!r} args={args[1:]} -- placeholder no-op.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
