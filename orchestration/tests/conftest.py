"""Shared pytest fixtures for the orchestration test suite.

Unit tests here are dependency-light: they exercise the PURE seams (auth kwargs, profile
resolution, repo-root logic) and must not require a live Snowflake or a running Dagster
instance. Integration tests (real Dagster, stubbed dbt) live under ``integration/`` and
self-skip via ``pytest.importorskip("dagster")`` when the runtime is absent.

Sandbox gotcha (documented in issue #6): run pytest with ``PYTHONPATH`` cleared, otherwise
site-packages (PyYAML) can be shadowed. CI runs pytest with ``PYTHONPATH: ""``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"

# env_var names used by the fixture profiles.yml 'rendered' target; cleared before each
# test so rendering is deterministic (default-branch and no-default-raises paths).
_AUTH_ENV_VARS = ("ARTWORK_TEST_ACCOUNT", "ARTWORK_TEST_USER", "ARTWORK_TEST_KEY")


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the committed ``tests/fixtures`` directory."""
    return FIXTURES


@pytest.fixture
def profiles_path() -> Path:
    """Path to the fixture dbt ``profiles.yml`` used by connection unit tests."""
    return FIXTURES / "profiles.yml"


@pytest.fixture(autouse=True)
def _clean_auth_env(tmp_path, monkeypatch):
    """Neutralize ambient auth env for deterministic tests.

    * Clears the ``ARTWORK_TEST_*`` env vars the fixture profile renders, so the
      env_var default and no-default-raises branches are exercised deterministically.
    * Points the in-Snowflake session-token path at a nonexistent file (the environment
      may have a real ``/snowflake/session/token``); tests exercising the session/native
      path override this env var explicitly.
    """
    for var in _AUTH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SNOWFLAKE_TOKEN_FILE_PATH", str(tmp_path / "no-session-token"))
