"""
Import-inertness acceptance test (roadmap issue #11).

Thin wrapper over ``scripts/ci/check_import_inertness.py`` so the gate runs as
part of ``pytest extraction/tests`` as well as standalone in CI. The heavy
lifting -- importing each target in a fresh guarded interpreter -- lives in the
script, which gives precise import-time detection independent of the pytest
process's already-imported modules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "ci" / "check_import_inertness.py"


def test_targets_import_without_side_effects() -> None:
    """
    Importing the extraction/orchestration entry modules triggers no network,
    Snowflake, subprocess, or dotenv side effects.
    """
    assert _SCRIPT.is_file(), f"missing inertness script: {_SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        "import-inertness gate failed:\n" + proc.stdout + "\n" + proc.stderr
    )
