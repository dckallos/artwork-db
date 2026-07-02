"""Central configuration for the orchestration layer.

Two things live here, both deliberately dependency-light so importing this module
never drags in the dbt stack:

* ``REPO_ROOT`` -- the single home for the repo path (resources.py, _runner.py,
  _snowflake.py, _connection.py all import it from here). Resolution is robust to an
  installed-package layout, not just the in-repo checkout (see ``_paths.resolve_repo_root``).
* ``FRAMEWORK`` / ``BRONZE`` -- the parsed, validated engine config loaded from
  ``framework.yaml`` (see loader.py + model.py). Everything that used to be a hardcoded
  ``ARTWORK_DB.BRONZE.<TABLE>`` string now flows through ``BRONZE.fqn(...)``; the
  database/schema (and every other knob) are set ONCE, in YAML, not in Python.

The dbt project/profiles directories are ALSO single-sourced here (``DBT_PROJECT_DIR`` /
``DBT_PROFILES_DIR``), derived from ``framework.yaml -> connection`` -- so resources.py,
dbt_manifest.py and _connection.py never re-hardcode ``"artwork_pipeline"`` or a target.
"""
from __future__ import annotations

from ._paths import resolve_repo_root
from .loader import load_framework_config

# The whole Layer-A engine config, parsed + validated from framework.yaml (cached). Loaded
# from the package dir (loader uses ``__file__``), so it does NOT depend on REPO_ROOT.
FRAMEWORK = load_framework_config()

# The single home for the repo path. Resolution (env override -> marker walk -> in-repo
# fallback) lives in the dependency-free _paths module so it is unit-testable without
# Dagster; see :func:`artwork_orchestration._paths.resolve_repo_root`.
REPO_ROOT = resolve_repo_root(FRAMEWORK.connection.project_dir)


def _resolve_repo_root(project_dirname: str):
    """Thin wrapper around :func:`artwork_orchestration._paths.resolve_repo_root`.

    Kept on ``config`` as the stable entry point consumers/tests reference; the actual
    (dependency-free, unit-testable) logic lives in ``_paths``.
    """
    return resolve_repo_root(project_dirname)


# The dbt project (where dbt_project.yml + target/manifest.json live) and the profiles dir
# (where profiles.yml lives). Single-sourced from framework.yaml; every consumer imports
# these rather than re-deriving the location.
DBT_PROJECT_DIR = (REPO_ROOT / FRAMEWORK.connection.project_dir).resolve()
DBT_PROFILES_DIR = (REPO_ROOT / FRAMEWORK.connection.profiles_dir).resolve()

# Location of the raw (Bronze) landing tables; import this rather than hardcoding names.
BRONZE = FRAMEWORK.bronze
