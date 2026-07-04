"""
Unit tests for :mod:`ghclient.secrets` -- the ``secrets publish`` capability.

Entirely offline (``no_network``): the ``gh`` seam is a recording fake, the connections
profile comes from ``tests/fixtures/connections.toml``, and every secret *value* is
synthetic. Coverage: pure plan derivation, H8 secret-vs-variable semantics, the publish
modes, the H3 identity guard (positive + ACCOUNTADMIN / non-allowlisted / OAuth / no-role /
local-user), dry-run-vs-apply, values-via-stdin, and the H5 adversarial matrix including an
explicit redaction test.

Sentinel secret values here are deliberately chosen NOT to be substrings of any published
item *name* (e.g. avoid "PASSPHRASE", which is a substring of
``DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE``) so that a leak assertion cannot false-positive on
a name that legitimately appears in the preview.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient.config import ItemKind, load_config
from ghclient.connections import load_profile
from ghclient.secrets import (
    PublishAction,
    PublishMode,
    assert_ci_identity,
    build_publish_plan,
    run_publish,
)
from ghclient.gh import GhResult

_MANAGED_SECRETS = (
    "DBT_SNOWFLAKE_USER",
    "DBT_SNOWFLAKE_PRIVATE_KEY",
    "DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE",
)
_MANAGED_VARS = ("SNOWFLAKE_ACCOUNT", "DBT_SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE")

# Synthetic values that are NOT substrings of any managed item name.
_KEY_VALUE = "pk-data-9f3a2b7c"
_PP_VALUE = "pp-7c1d4e2a"
_ACCOUNT_VALUE = "orgname-staging_acct"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _cfg(fixtures_dir: Path):
    """
    Load the fixture config and point the connections source at the fixture toml.
    """
    cfg = load_config(fixtures_dir / "secrets-config.yml", package_dir=fixtures_dir)
    secrets = dataclasses.replace(cfg.secrets, source=str(fixtures_dir / "connections.toml"))
    return dataclasses.replace(cfg, secrets=secrets)


def _profile(fixtures_dir: Path, name: str = "artwork_ci_staging"):
    """
    Load one connections profile from the fixture toml.
    """
    return load_profile(str(fixtures_dir / "connections.toml"), name)


def _runner(
    fake_runner_factory,
    *,
    env_status: int = 200,
    existing_secrets=(),
    existing_variables=None,
    list_status: int = 200,
    set_results=None,
):
    """
    Build a recording fake gh runner with scripted env/list/set responses.
    """
    existing_variables = existing_variables or {}
    set_results = set_results or {}

    def handler(kind, method, path, body):
        if kind == "api" and "/environments/" in path:
            if env_status == 200:
                return GhResult(args=(), returncode=0, stdout="{}", status_code=200)
            return GhResult(args=(), returncode=1, stderr=f"(HTTP {env_status})", status_code=env_status)
        if "secret list" in path:
            if list_status != 200:
                return GhResult(args=(), returncode=1, stderr=f"(HTTP {list_status})", status_code=list_status)
            return GhResult(
                args=(), returncode=0, stdout=json.dumps([{"name": n} for n in existing_secrets]), status_code=200
            )
        if "variable list" in path:
            return GhResult(
                args=(),
                returncode=0,
                stdout=json.dumps([{"name": k, "value": v} for k, v in existing_variables.items()]),
                status_code=200,
            )
        toks = path.split()
        if len(toks) >= 3 and toks[1] in ("set", "delete"):
            return set_results.get(toks[2], GhResult(args=(), returncode=0, stdout="", status_code=200))
        return GhResult(args=(), returncode=0, stdout="{}", status_code=200)

    return fake_runner_factory(handler)


def _set_delete_calls(runner):
    """
    Return the ``(verb, action, name)`` of every recorded secret/variable set/delete call.
    """
    out = []
    for kind, _m, path, _b in runner.calls:
        if kind != "run":
            continue
        toks = path.split()
        if len(toks) >= 3 and toks[1] in ("set", "delete"):
            out.append((toks[0], toks[1], toks[2]))
    return out


def _stdin_by_name(runner):
    """
    Map each ``set`` call's item name to the value that rode in on stdin.
    """
    out = {}
    for args, text in runner.run_inputs:
        if len(args) >= 3 and args[1] == "set":
            out[args[2]] = text
    return out


# --------------------------------------------------------------------------- #
# Pure plan derivation + H8
# --------------------------------------------------------------------------- #
def test_plan_all_create_when_env_empty(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets=set(), existing_variables={}, mode=PublishMode(),
    )
    by_name = {i.name: i for i in plan}
    assert set(by_name) == set(_MANAGED_SECRETS) | set(_MANAGED_VARS)
    assert all(i.action is PublishAction.CREATE for i in plan)


def test_h8_secret_items_never_carry_a_value(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets=set(), existing_variables={}, mode=PublishMode(),
    )
    for item in plan:
        if item.kind is ItemKind.SECRET:
            assert item.value_preview is None


def test_h8_variable_shows_value_diff(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets=set(), existing_variables={"DBT_SNOWFLAKE_ROLE": "OLD_ROLE"},
        mode=PublishMode(force=True),
    )
    role = next(i for i in plan if i.name == "DBT_SNOWFLAKE_ROLE")
    assert role.value_preview is not None
    assert "OLD_ROLE" in role.value_preview
    assert "ARTWORK_TRANSFORMER" in role.value_preview


def test_plan_skips_existing_under_no_overwrite(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets=set(),
        existing_variables={"SNOWFLAKE_ACCOUNT": _ACCOUNT_VALUE, "DBT_SNOWFLAKE_ROLE": "ARTWORK_TRANSFORMER"},
        mode=PublishMode(no_overwrite=True, force=False),
    )
    by_name = {i.name: i.action for i in plan}
    assert by_name["SNOWFLAKE_ACCOUNT"] is PublishAction.SKIP
    assert by_name["DBT_SNOWFLAKE_ROLE"] is PublishAction.SKIP
    assert by_name["DBT_SNOWFLAKE_USER"] is PublishAction.CREATE


def test_plan_force_updates_existing(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets=set(), existing_variables={"SNOWFLAKE_ACCOUNT": "old"}, mode=PublishMode(force=True),
    )
    account = next(i for i in plan if i.name == "SNOWFLAKE_ACCOUNT")
    assert account.kind is ItemKind.VARIABLE
    assert account.action is PublishAction.UPDATE


def test_plan_delete_missing_preserves_unmanaged_items(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    plan = build_publish_plan(
        _profile(fixtures_dir), cfg.secrets.get("staging"),
        existing_secrets={"STALE_SECRET", "DBT_SNOWFLAKE_USER"},
        existing_variables={"STALE_VAR": "x", "SNOWFLAKE_ACCOUNT": _ACCOUNT_VALUE},
        mode=PublishMode(delete_missing=True),
    )
    deletes = {(i.name, i.kind) for i in plan if i.action is PublishAction.DELETE}
    assert deletes == set()
    assert any(i.name == "STALE_SECRET" for i in plan) is False
    assert any(i.name == "STALE_VAR" for i in plan) is False


# --------------------------------------------------------------------------- #
# H3 identity guard
# --------------------------------------------------------------------------- #
def test_h3_allows_allowlisted_role(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    assert_ci_identity(_profile(fixtures_dir), cfg.secrets.get("staging"))  # ARTWORK_TRANSFORMER: no raise


def test_h3_rejects_accountadmin(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    with pytest.raises(Exception) as exc:
        assert_ci_identity(_profile(fixtures_dir, "admin_conn"), cfg.secrets.get("admin"))
    assert "forbidden" in str(exc.value)


def test_h3_accountadmin_override_allows(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    assert_ci_identity(
        _profile(fixtures_dir, "admin_conn"), cfg.secrets.get("admin"),
        allow_roles_override=("ACCOUNTADMIN",),
    )  # no raise


def test_h3_rejects_non_allowlisted_role(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    with pytest.raises(Exception) as exc:
        assert_ci_identity(_profile(fixtures_dir, "wrong_role_conn"), cfg.secrets.get("wrong_role_set"))
    assert "allowlist" in str(exc.value)


def test_h3_rejects_oauth_session_profile(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    with pytest.raises(Exception) as exc:
        assert_ci_identity(_profile(fixtures_dir, "oauth_conn"), cfg.secrets.get("oauth"))
    assert "session" in str(exc.value).lower()


def test_h3_rejects_missing_role(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    with pytest.raises(Exception) as exc:
        assert_ci_identity(_profile(fixtures_dir, "no_role_conn"), cfg.secrets.get("staging"))
    assert "role" in str(exc.value)


def test_h3_rejects_local_user_identity(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    with pytest.raises(Exception) as exc:
        assert_ci_identity(_profile(fixtures_dir, "human_conn"), cfg.secrets.get("human"), local_user="rskallos")
    assert "personal/interactive identity" in str(exc.value)


# --------------------------------------------------------------------------- #
# run_publish: dry-run vs apply, values via stdin
# --------------------------------------------------------------------------- #
def test_dry_run_makes_no_mutations(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", apply=False)
    assert code == 0
    assert _set_delete_calls(runner) == []                    # no set/delete on dry-run
    assert all(text is None for _a, text in runner.run_inputs)  # no stdin used
    assert any("DRY-RUN" in ln for ln in lines)


def test_apply_creates_passing_values_via_stdin(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory)
    code, lines = run_publish(
        runner, _cfg(fixtures_dir), profile_set="staging", apply=True,
        file_reader=lambda p: _KEY_VALUE, prompt=lambda n: _PP_VALUE,
    )
    assert code == 0
    calls = _set_delete_calls(runner)
    assert ("variable", "set", "SNOWFLAKE_ACCOUNT") in calls
    assert ("variable", "set", "DBT_SNOWFLAKE_ROLE") in calls
    stdin = _stdin_by_name(runner)
    assert stdin["SNOWFLAKE_ACCOUNT"] == _ACCOUNT_VALUE
    assert stdin["DBT_SNOWFLAKE_PRIVATE_KEY"] == _KEY_VALUE
    assert stdin["DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"] == _PP_VALUE
    # No secret value ever appears in argv (the recorded path) or the output lines.
    blob = "\n".join(lines) + "\n".join(p for _k, _m, p, _b in runner.calls)
    for value in ("ARTWORK_CI_SVC_STAGING", _KEY_VALUE, _PP_VALUE):
        assert value not in blob


def test_apply_skips_existing_without_force(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory, existing_variables={"SNOWFLAKE_ACCOUNT": _ACCOUNT_VALUE})
    code, _ = run_publish(
        runner, _cfg(fixtures_dir), profile_set="staging", apply=True,
        file_reader=lambda p: _KEY_VALUE, prompt=lambda n: _PP_VALUE,
    )
    assert code == 0
    calls = _set_delete_calls(runner)
    assert ("variable", "set", "SNOWFLAKE_ACCOUNT") not in calls  # skipped
    assert ("secret", "set", "DBT_SNOWFLAKE_USER") in calls


def test_delete_missing_preserves_unmanaged_items(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory, existing_secrets=["STALE_SECRET"])
    code, lines = run_publish(
        runner, _cfg(fixtures_dir), profile_set="staging", apply=True,
        force=True, delete_missing=True, file_reader=lambda p: _KEY_VALUE, prompt=lambda n: _PP_VALUE,
    )
    assert code == 0
    assert ("secret", "delete", "STALE_SECRET") not in _set_delete_calls(runner)
    assert any("--delete-missing requested but ignored" in ln for ln in lines)


def test_run_publish_refuses_accountadmin_before_any_gh_call(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="admin", apply=True)
    assert code == 1
    assert any("forbidden" in ln for ln in lines)
    assert runner.calls == []  # guard fires before any gh call


def test_run_publish_allow_role_override(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory)
    code, _ = run_publish(
        runner, _cfg(fixtures_dir), profile_set="admin", apply=False, allow_roles=("ACCOUNTADMIN",)
    )
    assert code == 0


# --------------------------------------------------------------------------- #
# H5 adversarial matrix
# --------------------------------------------------------------------------- #
def test_h5_env_not_found_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory, env_status=404)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", apply=True)
    assert code == 1
    assert any("not found" in ln and "create" in ln.lower() for ln in lines)
    assert _set_delete_calls(runner) == []
    assert all(k == "api" for (k, _m, _p, _b) in runner.calls)  # stopped at precheck


def test_h5_env_forbidden_403_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory, env_status=403)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", apply=False)
    assert code == 1
    assert any("cannot verify environment" in ln for ln in lines)


def test_h5_env_timeout_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    def handler(kind, method, path, body):
        return GhResult(args=(), returncode=124, stderr="timed out", status_code=None)

    runner = fake_runner_factory(handler)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", apply=False)
    assert code == 1
    assert any("cannot verify environment" in ln for ln in lines)


def test_h5_list_permission_error_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory, list_status=403)
    code, lines = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", apply=False)
    assert code == 1
    assert any("cannot list secrets" in ln for ln in lines)


def test_h5_url_encoded_environment_name(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = _runner(fake_runner_factory)
    code, _ = run_publish(runner, _cfg(fixtures_dir), profile_set="staging", env="stag ing/x", apply=False)
    assert code == 0
    api_paths = [p for (k, _m, p, _b) in runner.calls if k == "api"]
    assert any("environments/stag%20ing%2Fx" in p for p in api_paths)


def test_h5_partial_apply_reports_and_stops(fixtures_dir: Path, fake_runner_factory) -> None:
    fail = GhResult(args=(), returncode=1, stderr="server error", status_code=500)
    runner = _runner(fake_runner_factory, set_results={"DBT_SNOWFLAKE_USER": fail})
    code, lines = run_publish(
        runner, _cfg(fixtures_dir), profile_set="staging", apply=True,
        file_reader=lambda p: _KEY_VALUE, prompt=lambda n: _PP_VALUE,
    )
    assert code == 1
    assert any("[FAILED]" in ln and "DBT_SNOWFLAKE_USER" in ln for ln in lines)
    assert any("aborted" in ln for ln in lines)
    calls = _set_delete_calls(runner)
    assert ("variable", "set", "SNOWFLAKE_ACCOUNT") in calls        # applied before the failure
    assert ("variable", "set", "DBT_SNOWFLAKE_ROLE") not in calls    # not attempted after abort


def test_h5_redaction_secret_value_never_surfaces(fixtures_dir: Path, fake_runner_factory) -> None:
    # Worst case: gh echoes the private-key value on stderr; _check must scrub it with the value.
    leak = GhResult(args=(), returncode=1, stderr=f"gh: failed writing {_KEY_VALUE} upstream", status_code=500)
    runner = _runner(fake_runner_factory, set_results={"DBT_SNOWFLAKE_PRIVATE_KEY": leak})
    code, lines = run_publish(
        runner, _cfg(fixtures_dir), profile_set="staging", apply=True,
        file_reader=lambda p: _KEY_VALUE, prompt=lambda n: _PP_VALUE,
    )
    out = "\n".join(lines)
    assert code == 1
    assert _KEY_VALUE not in out   # THE redaction guarantee
    assert "[REDACTED]" in out
    assert any("[FAILED]" in ln for ln in lines)
