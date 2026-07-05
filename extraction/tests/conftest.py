"""
Pytest configuration for the extraction offline test suite.

Puts the repository root on ``sys.path`` so ``import extraction.*`` resolves when
the suite is run as ``pytest extraction/tests`` from the repo root with a cleared
``PYTHONPATH`` (as CI does). No import-time credentials, network, or dbt work.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
