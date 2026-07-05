"""
Unit tests for :mod:`ghclient.connections` -- TOML profile parsing + H3 classification.

Offline and fixture-driven: every case reads the committed synthetic connections.toml
(no real secrets) and asserts file/field-scoped errors, never bare ``KeyError``\\s.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient.connections import SESSION_TOKEN_FIELDS, load_profile
from ghclient.errors import ConfigError


def _toml(fixtures_dir: Path) -> str:
    """
    Path to the fixture connections file, as a string source.
    """
    return str(fixtures_dir / "connections.toml")


def test_load_profile_parses_fields(fixtures_dir: Path) -> None:
    prof = load_profile(_toml(fixtures_dir), "artwork_ci_staging")
    assert prof.name == "artwork_ci_staging"
    assert prof.role == "ARTWORK_TRANSFORMER"
    assert prof.user == "ARTWORK_CI_SVC_STAGING"
    assert prof.require("account") == "orgname-staging_acct"
    assert prof.is_session_only() is False


def test_missing_file_is_file_scoped(tmp_path: Path) -> None:
    with pytest.raises(ConfigError) as ei:
        load_profile(str(tmp_path / "nope.toml"), "x")
    assert "connections file not found" in str(ei.value)


def test_missing_profile_lists_available(fixtures_dir: Path) -> None:
    with pytest.raises(ConfigError) as ei:
        load_profile(_toml(fixtures_dir), "does_not_exist")
    msg = str(ei.value)
    assert "[does_not_exist]" in msg
    assert "available:" in msg
    assert "artwork_ci_staging" in msg


def test_missing_required_field_is_field_scoped(fixtures_dir: Path) -> None:
    prof = load_profile(_toml(fixtures_dir), "missing_account")
    with pytest.raises(ConfigError) as ei:
        prof.require("account")
    assert "[missing_account].account" in str(ei.value)


def test_oauth_profile_is_session_only(fixtures_dir: Path) -> None:
    prof = load_profile(_toml(fixtures_dir), "oauth_conn")
    assert prof.is_session_only() is True
    assert prof.is_session_token_field("token_file_path") is True
    assert "token_file_path" in SESSION_TOKEN_FIELDS


def test_keypair_profile_is_not_session_only(fixtures_dir: Path) -> None:
    prof = load_profile(_toml(fixtures_dir), "artwork_ci_prod")
    assert prof.is_session_only() is False


def test_no_role_profile_role_is_none(fixtures_dir: Path) -> None:
    prof = load_profile(_toml(fixtures_dir), "no_role_conn")
    assert prof.role is None


def test_invalid_toml_is_file_scoped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text("this is = = not valid toml [[[\n")
    with pytest.raises(ConfigError) as ei:
        load_profile(str(bad), "x")
    assert "invalid TOML" in str(ei.value)
