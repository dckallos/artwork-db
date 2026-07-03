"""
Unit tests for portability wiring: single-sourced dbt dirs, robust REPO_ROOT,
optional profile / defaulted project_dir, and manifest-derived marts.

These import the framework ``config``/``loader`` (which pull in ``dagster`` via the spec
module), so the whole module is skipped where Dagster is not installed. In CI
(``pip install -e orchestration``) they run in full.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("dagster", reason="config/loader import chain requires dagster (spec.py)")

from artwork_orchestration import config as cfg  # noqa: E402
from artwork_orchestration.loader import (  # noqa: E402
    ConfigError,
    load_framework_config,
    reset_framework_cache,
)

_FW_NO_DIRS = """
connection:
  target: dev
bronze:
  database: D
  schema: S
defaults:
  retry: {max_retries: 1, delay_seconds: 1, backoff: exponential, jitter: none}
  timeouts_seconds: {default: 10}
  batching: {size: 1, max_batches: 1}
  rate_limit: {rps_budget: 1, concurrency: 1}
tags: {rate_limit_key: k, max_runtime_key: m}
freshness: {gold_marts: [], gold_lag_hours: 1}
"""


def test_project_dir_defaults_to_profiles_dir_and_profile_optional(fixtures_dir: Path) -> None:
    reset_framework_cache()
    try:
        fw = load_framework_config(str(fixtures_dir / "framework_min.yaml"))
        assert fw.connection.profiles_dir == "fixtures"
        assert fw.connection.project_dir == "fixtures"  # defaulted from profiles_dir
        assert fw.connection.profile is None            # optional, derived elsewhere
        assert fw.connection.target == "dev"
    finally:
        reset_framework_cache()


def test_connection_without_any_dir_is_actionable_error(tmp_path: Path) -> None:
    bad = tmp_path / "fw.yaml"
    bad.write_text(_FW_NO_DIRS)
    reset_framework_cache()
    try:
        with pytest.raises(ConfigError, match="profiles_dir"):
            load_framework_config(str(bad))
    finally:
        reset_framework_cache()


def test_repo_root_env_override_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTWORK_REPO_ROOT", str(tmp_path))
    assert cfg._resolve_repo_root("anything") == tmp_path.resolve()


def test_repo_root_marker_walk_finds_real_repo() -> None:
    # In a real checkout the resolved REPO_ROOT must actually contain the configured dbt
    # project, proving the marker walk (not a brittle parents[N]) located it.
    assert (cfg.REPO_ROOT / cfg.FRAMEWORK.connection.project_dir / "dbt_project.yml").exists()


def test_single_sourced_dirs_are_absolute_and_exist() -> None:
    assert cfg.DBT_PROJECT_DIR.is_absolute() and cfg.DBT_PROJECT_DIR.exists()
    assert cfg.DBT_PROFILES_DIR.is_absolute() and cfg.DBT_PROFILES_DIR.exists()
    assert (cfg.DBT_PROJECT_DIR / "dbt_project.yml").exists()
    assert (cfg.DBT_PROFILES_DIR / "profiles.yml").exists()


def test_gold_mart_names_reads_only_marts_tagged_models(
    fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from artwork_orchestration import dbt_manifest

    monkeypatch.setattr(dbt_manifest, "_MANIFEST_PATH", fixtures_dir / "manifest.json")
    # seed tagged 'marts' and the staging model are excluded; result is sorted.
    assert dbt_manifest.gold_mart_names() == ["dim_artists", "fct_artworks"]


def test_gold_mart_names_empty_when_manifest_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from artwork_orchestration import dbt_manifest

    monkeypatch.setattr(dbt_manifest, "_MANIFEST_PATH", tmp_path / "nope.json")
    assert dbt_manifest.gold_mart_names() == []
