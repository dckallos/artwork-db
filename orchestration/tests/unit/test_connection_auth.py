"""Unit tests for the auth-method mapping (``build_connect_kwargs``) -- driver/Dagster-free.

Complements ``test_connection_profile.py`` (which covers ``profiles.yml`` resolution) by
asserting how a resolved :class:`ProfileConfig` maps onto ``snowflake.connector`` kwargs
for EVERY dbt auth method the project supports: key-pair, password, externalbrowser,
oauth, username_password_mfa, and the in-Snowflake session/native path. This is the
"support and TEST all dbt auth methods" acceptance item from issue #6 section 1.

Imports only ``_connection`` (config imported lazily inside it) and ``model`` -- no Dagster.
The autouse ``_clean_auth_env`` fixture neutralizes any real session token file.
"""
from __future__ import annotations

from pathlib import Path

from artwork_orchestration._connection import _resolve_profile, build_connect_kwargs
from artwork_orchestration.model import ProfileConfig


# --------------------------------------------------------------- pure kwargs matrix
def test_key_pair_expands_path_and_carries_passphrase():
    kw = build_connect_kwargs(
        ProfileConfig(account="a", user="u", private_key_path="~/k.p8", private_key_passphrase="pw")
    )
    assert kw["private_key_file"] == str(Path("~/k.p8").expanduser())
    assert kw["private_key_file_pwd"] == "pw"
    assert "password" not in kw and "authenticator" not in kw and "token" not in kw


def test_key_pair_without_passphrase_omits_pwd():
    kw = build_connect_kwargs(ProfileConfig(private_key_path="/k.p8"))
    assert kw["private_key_file"] == "/k.p8" and "private_key_file_pwd" not in kw


def test_password_auth():
    kw = build_connect_kwargs(ProfileConfig(account="a", user="u", password="secret"))
    assert kw["password"] == "secret" and "authenticator" not in kw and "token" not in kw


def test_password_with_explicit_authenticator():
    kw = build_connect_kwargs(ProfileConfig(password="s", authenticator="snowflake"))
    assert kw["password"] == "s" and kw["authenticator"] == "snowflake"


def test_externalbrowser_carries_no_secret():
    kw = build_connect_kwargs(ProfileConfig(user="u", authenticator="externalbrowser"))
    assert kw["authenticator"] == "externalbrowser"
    assert "password" not in kw and "token" not in kw and "private_key_file" not in kw


def test_oauth_with_explicit_token():
    kw = build_connect_kwargs(ProfileConfig(authenticator="oauth", token="TOK"))
    assert kw["authenticator"] == "oauth" and kw["token"] == "TOK"


def test_username_password_mfa():
    kw = build_connect_kwargs(
        ProfileConfig(user="u", password="p", authenticator="username_password_mfa")
    )
    assert kw["authenticator"] == "username_password_mfa" and kw["password"] == "p"


def test_no_credentials_and_no_session_yields_no_auth_kwargs():
    # _clean_auth_env guarantees no session-token file is present.
    kw = build_connect_kwargs(ProfileConfig(account="a", user="u"))
    assert "authenticator" not in kw and "token" not in kw and "password" not in kw


def test_session_native_path_uses_session_token_file(tmp_path, monkeypatch):
    tok = tmp_path / "session.token"
    tok.write_text("SESSIONTOK\n")
    monkeypatch.setenv("SNOWFLAKE_TOKEN_FILE_PATH", str(tok))
    kw = build_connect_kwargs(ProfileConfig(account="a", user="u"))
    assert kw["authenticator"] == "oauth" and kw["token"] == "SESSIONTOK"


def test_oauth_falls_back_to_session_token_when_no_explicit_token(tmp_path, monkeypatch):
    tok = tmp_path / "session.token"
    tok.write_text("FROMFILE")
    monkeypatch.setenv("SNOWFLAKE_TOKEN_FILE_PATH", str(tok))
    kw = build_connect_kwargs(ProfileConfig(authenticator="oauth"))
    assert kw["token"] == "FROMFILE"


def test_none_values_filtered_out():
    kw = build_connect_kwargs(ProfileConfig(user="u"))
    assert all(v is not None for v in kw.values()) and "account" not in kw


def test_identity_fields_passed_through():
    kw = build_connect_kwargs(
        ProfileConfig(account="a", user="u", role="r", warehouse="w", database="d", schema="s", password="p")
    )
    for k, v in dict(account="a", user="u", role="r", warehouse="w", database="d", schema="s").items():
        assert kw[k] == v


# ------------------------------------------- round-trip: fixture profile -> kwargs
def test_keypair_profile_round_trips_to_private_key_file(profiles_path):
    pc = _resolve_profile(profiles_path, profile="artwork_test", target="keypair")
    kw = build_connect_kwargs(pc)
    assert kw["private_key_file"] == str(Path("~/keys/test_rsa_key.p8").expanduser())
    assert kw["private_key_file_pwd"] == "kp_secret" and "password" not in kw


def test_oauth_profile_round_trips_to_token(profiles_path):
    pc = _resolve_profile(profiles_path, profile="artwork_test", target="oauth")
    kw = build_connect_kwargs(pc)
    assert kw["authenticator"] == "oauth" and kw["token"] == "oauth_token_value"
