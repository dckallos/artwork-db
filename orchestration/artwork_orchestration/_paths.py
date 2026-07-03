"""
Repo-root / project-dir resolution -- dependency-free so it is unit-testable alone.

Kept separate from :mod:`artwork_orchestration.config` because ``config`` imports the
loader (and thus, transitively, Dagster via ``spec``). This module is stdlib-only, so the
path-resolution logic can be exercised in a bare test process with no Dagster installed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Explicit override for installed-package / container deployments (and tests) where the
# source tree is not an ancestor of the importing module.
REPO_ROOT_ENV = "ARTWORK_REPO_ROOT"

# Files that mark the repo root when walking up from the package.
_ROOT_MARKERS = ("AGENTS.md", ".git")


def resolve_repo_root(project_dirname: str, *, start: Optional[Path] = None) -> Path:
    """
    Locate the repo root robustly, in priority order:

    1. ``$ARTWORK_REPO_ROOT`` -- explicit override (installed-package / container / tests).
    2. Walk up from ``start`` looking for a marker: the configured dbt project dir
       (``<project_dirname>/dbt_project.yml``), or ``AGENTS.md`` / ``.git`` at the root.
    3. Fall back to the in-repo checkout layout
       (``orchestration/artwork_orchestration/<module>.py`` -> three parents up).

    ``project_dirname`` is the first path segment of the configured project dir, so the
    marker tracks config rather than a hardcoded literal. ``start`` defaults to this file
    (same package dir as ``config.py``, so the parents[2] fallback is identical).
    """
    override = os.environ.get(REPO_ROOT_ENV)
    if override:
        return Path(override).expanduser().resolve()

    here = (start or Path(__file__)).resolve()
    marker = (project_dirname or "").split("/", 1)[0]
    for parent in here.parents:
        if marker and (parent / marker / "dbt_project.yml").exists():
            return parent
        if any((parent / m).exists() for m in _ROOT_MARKERS):
            return parent
    return here.parents[2]
