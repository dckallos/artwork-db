"""Subprocess runner for extraction CLIs.

The orchestration layer drives extraction by shelling out to the existing module
CLIs (``python -m extraction.<source>.run <subcommand> ...``). This is the single
seam between Dagster and the extractors; keeping it in one place means the asset
factory never constructs subprocess commands itself.

CLI CONTRACT (every source's ``run.py`` must honor):
  * ``python -m <cli_module> <subcommand> [flags]`` runs one phase and exits 0 on success.
  * Rate-limited enrichment reads its per-worker request rate from an env var
    (default ``MET_API_RPS``) so the orchestrator can divide a global budget.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Mapping, Optional, Sequence

from .config import REPO_ROOT


def run_module(
    context,
    cli_module: str,
    args: Sequence[str],
    extra_env: Optional[Mapping[str, str]] = None,
) -> None:
    """Run ``python -m <cli_module> <args...>`` from the repo root, raising on failure."""
    cmd = [sys.executable, "-m", cli_module, *args]
    context.log.info("Running: %s", " ".join(cmd))
    env = {**os.environ, **extra_env} if extra_env else None
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Extraction command failed ({proc.returncode}): {' '.join(cmd)}")
