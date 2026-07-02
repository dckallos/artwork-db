"""Shared resources and paths for the artwork orchestration code location.

Wires Dagster to the existing dbt project (``artwork_pipeline``) using the
local ``dev`` profile target. No new credentials: dbt reads the same key-pair
env vars documented in the repo's .env.example.
"""
from __future__ import annotations

from pathlib import Path

from dagster_dbt import DbtCliResource, DbtProject

# orchestration/artwork_orchestration/resources.py -> repo root is three up.
REPO_ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT_DIR = REPO_ROOT / "artwork_pipeline"

# DbtProject handles manifest generation in dev (prepare_if_dev) and points at
# a pre-built manifest.json in production. target="dev" uses the local
# key-pair profile from profiles.yml.
artwork_dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
    profiles_dir=DBT_PROJECT_DIR,
    target="dev",
)

# In `dagster dev`, ensure a manifest exists (runs `dbt parse` if missing/stale).
artwork_dbt_project.prepare_if_dev()

dbt_resource = DbtCliResource(project_dir=artwork_dbt_project)
