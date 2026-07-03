"""
Unit tests for dbt profile resolution + ``env_var()`` rendering (driver/Dagster-free).

These exercise ``_resolve_profile`` against the fixture ``profiles.yml`` using the explicit
path seam (so no packaged config / dagster import is needed) and the profile-name
derivation from ``dbt_project.yml``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from artwork_orchestration._connection import (
    _derive_profile_name,
    _resolve_profile,
)


def test_resolve_keypair_target(profiles_path: Path) -> None:
    p = _resolve_profile(profiles_path, profile="artwork_test", target="keypair")
    assert p.account == "acct_kp"
    assert p.private_key_path == "~/keys/test_rsa_key.p8"
    assert p.private_key_passphrase == "kp_secret"
    assert p.password is None


def test_resolve_oauth_target_carries_token(profiles_path: Path) -> None:
    p = _resolve_profile(profiles_path, profile="artwork_test", target="oauth")
    assert p.authenticator == "oauth"
    assert p.token == "oauth_token_value"


def test_env_var_rendering_uses_environment(
    profiles_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ARTWORK_TEST_ACCOUNT", "rendered_acct")
    monkeypatch.setenv("ARTWORK_TEST_KEY", "/keys/rendered.p8")
    p = _resolve_profile(profiles_path, profile="artwork_test", target="rendered")
    assert p.account == "rendered_acct"
    assert p.private_key_path == "/keys/rendered.p8"
    # user falls back to the env_var default when the var is unset
    assert p.user == "fallback_user"


def test_env_var_without_default_and_unset_raises(profiles_path: Path) -> None:
    # ARTWORK_TEST_ACCOUNT has no default in the fixture and is cleared by _clean_auth_env.
    with pytest.raises(RuntimeError, match="ARTWORK_TEST_ACCOUNT"):
        _resolve_profile(profiles_path, profile="artwork_test", target="rendered")


def test_unknown_target_raises_actionable_error(profiles_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not found"):
        _resolve_profile(profiles_path, profile="artwork_test", target="does_not_exist")


def test_explicit_path_requires_profile_and_target(profiles_path: Path) -> None:
    with pytest.raises(ValueError):
        _resolve_profile(profiles_path, profile="artwork_test")  # missing target


def test_derive_profile_name_from_dbt_project(fixtures_dir: Path) -> None:
    assert _derive_profile_name(fixtures_dir) == "artwork_test"


def test_derive_profile_name_missing_project_raises(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="dbt_project.yml"):
        _derive_profile_name(tmp_path)
