"""Shared resources and paths for the artwork orchestration code location.

Wires Dagster to the existing dbt project (``artwork_pipeline``) using the
local ``dev`` profile target. No new credentials: dbt reads the same key-pair
env vars documented in the repo's .env.example.
"""
from __future__ import annotations

from dagster_dbt import DbtCliResource, DbtProject

from .config import REPO_ROOT

DBT_PROJECT_DIR = REPO_ROOT / "artwork_pipeline"

# DbtProject handles manifest generation in dev (prepare_if_dev) and points at
# a pre-built manifest.json in production. target="dev" uses the local
# key-pair profile from profiles.yml.
artwork_dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    target="dev",
)

# Build the manifest ONCE, and only when it is missing.
#
# ``prepare_if_dev()`` shells out to ``dbt deps`` + ``dbt parse``. This module is
# re-imported by EVERY run-worker subprocess (Dagster reconstructs the code location per
# run), so calling it unconditionally makes every worker re-run ``dbt deps`` against the
# shared ``dbt_packages/`` dir. Under a multi-partition backfill those runs collide, and
# dbt-fusion's unpacker then fails to set file mtimes -> ``IoError (dbt1001)`` -> the run
# dies before its step starts. Guarding on the manifest's absence means the parent
# ``dagster dev`` process prepares once and every worker just reuses the manifest.
#
# To pick up dbt *model* changes, rebuild the manifest (``run_dagster_dev.sh`` runs
# ``dbt parse`` on launch, or delete target/manifest.json) and restart.
if not artwork_dbt_project.manifest_path.exists():
    artwork_dbt_project.prepare_if_dev()

dbt_resource = DbtCliResource(project_dir=artwork_dbt_project)
