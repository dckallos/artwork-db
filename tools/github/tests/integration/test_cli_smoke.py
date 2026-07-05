"""
Integration smoke: end-to-end verb dispatch through the pure command functions with a
fake ``GhRunner`` recording commands (no network, no typer required).

Asserts the recorded ``gh`` command sequence per verb, the dry-run-vs-apply boundary, and
correct exit codes -- the seam and loader that Areas B/C will build on.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp
from ghclient import ci
from ghclient.preflight import run_preflight

_PROTECTION = "repos/octocat/hello-world/branches/main/protection"


def _cfg(fixtures_dir: Path):
    """
    Load the committed valid config against the fixtures package dir.
    """
    from ghclient.config import load_config

    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def test_preflight_green_dispatches_auth_status(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if kind == "api":
            return gh_result(returncode=0, stdout='{"permissions": {"admin": true}}')
        return gh_result(returncode=0)

    runner = fake_runner_factory(handler)
    code, lines = run_preflight(runner, config_path=fixtures_dir / "valid-config.yml")
    assert code == 0
    assert ("run", "", "auth status", None) in runner.calls
    assert any("gh auth" in line and "authenticated" in line for line in lines)


def test_preflight_fails_without_admin(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if kind == "api":
            return gh_result(returncode=0, stdout='{"permissions": {"admin": false}}')
        return gh_result(returncode=0)

    runner = fake_runner_factory(handler)
    code, _ = run_preflight(runner, config_path=fixtures_dir / "valid-config.yml")
    assert code == 1


def test_apply_dry_run_records_no_mutations(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    # audit-first (A3) reads protection + rulesets + branch rules; dry-run must MUTATE nothing.
    def handler(kind, method, path, body):
        if "protection" in path:
            return gh_result(returncode=1, stderr="(HTTP 404)", status_code=404)
        return gh_result(returncode=0, stdout="[]")

    runner = fake_runner_factory(handler)
    code, _ = bp.run_apply(runner, _cfg(fixtures_dir), apply=False)
    assert code == 0
    assert [m for (m, _p, _b) in runner.api_calls if m in ("PUT", "DELETE")] == []


def test_apply_with_flag_audits_then_puts(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if "protection" in path:
            if method == "GET":
                return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
            return gh_result(returncode=0, stdout="{}")
        return gh_result(returncode=0, stdout="[]")  # rulesets + branch rules: no overlap

    runner = fake_runner_factory(handler)
    code, _ = bp.run_apply(runner, _cfg(fixtures_dir), apply=True)
    assert code == 0
    methods = [m for (m, _p, _b) in runner.api_calls]
    # A3: read-only audit precedes the single mutation, which is the final PUT.
    assert methods[-1] == "PUT"
    assert methods.count("PUT") == 1 and "DELETE" not in methods
    assert methods.index("PUT") > 0  # at least one GET (the audit) came first


def test_audit_reads_three_surfaces(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0, stdout="[]") if "protection" not in p
                                 else gh_result(returncode=1, stderr="(HTTP 404)", status_code=404))
    code, _ = bp.run_audit(runner, _cfg(fixtures_dir))
    assert code == 0
    assert len(runner.api_calls) == 3


def test_rollback_dry_run_audits_but_records_no_mutations(
    fixtures_dir: Path, fake_runner_factory, gh_result, tmp_path: Path
) -> None:
    cfg = _cfg(fixtures_dir)
    # Seed a verified-404 snapshot ENVELOPE (A2: a bare `null` file is refused).
    exports = tmp_path / "exports"
    exports.mkdir()
    snap = bp.build_snapshot(cfg.repo, bp.Snapshot(branch="main", body=None, source="verified-404"))
    bp.write_snapshot(snap, exports)

    class _Cfg:
        repo = cfg.repo
        branch_protection = cfg.branch_protection
        exports_dir = exports

    def handler(kind, method, path, body):
        if "protection" in path:
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        return gh_result(returncode=0, stdout="[]")

    runner = fake_runner_factory(handler)
    code, lines = bp.run_rollback(runner, _Cfg(), apply=False)
    assert code == 0
    assert [m for (m, _p, _b) in runner.api_calls if m in ("PUT", "DELETE")] == []
    assert len(runner.api_calls) == 3
    assert any("dry-run" in line for line in lines)


def _ci_cfg(fixtures_dir: Path):
    """
    Load the committed ci-reconcile config against the fixtures package dir.
    """
    from ghclient.config import load_config

    return load_config(fixtures_dir / "ci-reconcile-config.yml", package_dir=fixtures_dir)


def test_ci_reconcile_dry_run_reads_but_does_not_patch(fixtures_dir: Path, fake_runner_factory) -> None:
    import json

    def handler(kind, method, path, body):
        from ghclient.gh import GhResult

        if method == "GET":
            return GhResult(args=(), returncode=0, stdout=json.dumps({"contexts": ["test"]}), status_code=200)
        return GhResult(args=(), returncode=0, stdout="{}", status_code=200)

    runner = fake_runner_factory(handler)
    code, _ = ci.run_reconcile(runner, _ci_cfg(fixtures_dir), apply=False, workflows_root=fixtures_dir)
    assert code == 0
    methods = [m for (m, _p, _b) in runner.api_calls]
    assert methods == ["GET"]  # reads current state; no mutation on dry-run


def test_ci_reconcile_apply_reads_then_patches_aggregate(fixtures_dir: Path, fake_runner_factory) -> None:
    import json

    def handler(kind, method, path, body):
        from ghclient.gh import GhResult

        if method == "GET":
            return GhResult(args=(), returncode=0, stdout=json.dumps({"contexts": ["test"]}), status_code=200)
        return GhResult(args=(), returncode=0, stdout="{}", status_code=200)

    runner = fake_runner_factory(handler)
    code, _ = ci.run_reconcile(runner, _ci_cfg(fixtures_dir), apply=True, workflows_root=fixtures_dir)
    assert code == 0
    calls = runner.api_calls
    assert [m for (m, _p, _b) in calls] == ["GET", "PATCH"]  # H1-style read before the mutation
    assert calls[-1][2] == {
        "strict": True,
        "checks": [{"context": "ci-required", "app_id": -1}],
        "contexts": [],
    }


# --------------------------------------------------------------------------- #
# secrets publish (Area B, slice 3) -- dispatch through the fake runner
# --------------------------------------------------------------------------- #
def _secrets_cfg(fixtures_dir: Path):
    """
    Load the fixture secrets config and repoint the connections source at the fixture toml.
    """
    import dataclasses

    from ghclient.config import load_config

    cfg = load_config(fixtures_dir / "secrets-config.yml", package_dir=fixtures_dir)
    secrets = dataclasses.replace(cfg.secrets, source=str(fixtures_dir / "connections.toml"))
    return dataclasses.replace(cfg, secrets=secrets)


def _secrets_handler(*, existing_secrets=(), existing_variables=None):
    """
    Build a handler that answers the env precheck + secret/variable list reads with 200s.
    """
    import json

    from ghclient.gh import GhResult

    existing_variables = existing_variables or {}

    def handler(kind, method, path, body):
        if kind == "api" and "/environments/" in path:
            return GhResult(args=(), returncode=0, stdout="{}", status_code=200)
        if "secret list" in path:
            rows = [{"name": n} for n in existing_secrets]
            return GhResult(args=(), returncode=0, stdout=json.dumps(rows), status_code=200)
        if "variable list" in path:
            rows = [{"name": k, "value": v} for k, v in existing_variables.items()]
            return GhResult(args=(), returncode=0, stdout=json.dumps(rows), status_code=200)
        return GhResult(args=(), returncode=0, stdout="", status_code=200)

    return handler


def test_secrets_publish_dry_run_reads_env_and_lists_only(fixtures_dir: Path, fake_runner_factory) -> None:
    from ghclient import secrets

    runner = fake_runner_factory(_secrets_handler())
    code, lines = secrets.run_publish(
        runner, _secrets_cfg(fixtures_dir), profile_set="staging", apply=False, local_user="ci-bot"
    )
    assert code == 0
    # The env existence precheck is the single gh api call, path-encoded by the client.
    assert [p for (_m, p, _b) in runner.api_calls] == ["repos/octocat/hello-world/environments/staging"]
    run_cmds = [p for (k, _m, p, _b) in runner.calls if k == "run"]
    assert any(c.startswith("secret list") for c in run_cmds)
    assert any(c.startswith("variable list") for c in run_cmds)
    # Dry-run mutates nothing and puts nothing on stdin.
    assert not any(" set " in f" {c} " or " delete " in f" {c} " for c in run_cmds)
    assert all(text is None for (_argv, text) in runner.run_inputs)
    assert any("DRY-RUN" in ln for ln in lines)


def test_secrets_publish_apply_sets_values_via_stdin(fixtures_dir: Path, fake_runner_factory) -> None:
    from ghclient import secrets

    runner = fake_runner_factory(_secrets_handler())
    code, _ = secrets.run_publish(
        runner,
        _secrets_cfg(fixtures_dir),
        profile_set="staging",
        apply=True,
        force=True,
        local_user="ci-bot",
        file_reader=lambda _p: "KEYMATERIAL_ov7",
        prompt=lambda _n: "PPHRASE_qz2",
    )
    assert code == 0
    sets = [(argv, text) for (argv, text) in runner.run_inputs if len(argv) >= 2 and argv[1] == "set"]
    got = [(argv[0], argv[2], text) for (argv, text) in sets]
    assert got == [
        ("variable", "SNOWFLAKE_ACCOUNT", "orgname-staging_acct"),
        ("secret", "DBT_SNOWFLAKE_USER", "ARTWORK_CI_SVC_STAGING"),
        ("variable", "DBT_SNOWFLAKE_ROLE", "ARTWORK_TRANSFORMER"),
        ("variable", "SNOWFLAKE_WAREHOUSE", "DBT_STAGING_WH"),
        ("secret", "DBT_SNOWFLAKE_PRIVATE_KEY", "KEYMATERIAL_ov7"),
        ("secret", "DBT_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "PPHRASE_qz2"),
    ]
    # No value ever rides on argv -- only on stdin (H5).
    for argv, _text in sets:
        for tok in argv:
            assert "orgname-staging_acct" not in tok
            assert "KEYMATERIAL_ov7" not in tok
            assert "PPHRASE_qz2" not in tok
