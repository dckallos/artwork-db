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
from ghclient.cli import run_preflight

_PROTECTION = "repos/octocat/hello-world/branches/main/protection"


def _cfg(fixtures_dir: Path):
    """
    Load the committed valid config against the fixtures package dir.
    """
    from ghclient.config import load_config

    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def test_preflight_green_dispatches_auth_status(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    code, lines = run_preflight(runner, config_path=fixtures_dir / "valid-config.yml", jq_present=True)
    assert code == 0
    assert ("run", "", "auth status", None) in runner.calls
    assert any("gh auth: OK" in line for line in lines)


def test_preflight_fails_without_jq(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    code, _ = run_preflight(runner, config_path=fixtures_dir / "valid-config.yml", jq_present=False)
    assert code == 1


def test_apply_dry_run_records_no_api_calls(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory()
    code, _ = bp.run_apply(runner, _cfg(fixtures_dir), apply=False)
    assert code == 0
    assert runner.api_calls == []


def test_apply_with_flag_exports_then_puts(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if method == "GET":
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        return gh_result(returncode=0, stdout="{}")

    runner = fake_runner_factory(handler)
    code, _ = bp.run_apply(runner, _cfg(fixtures_dir), apply=True)
    assert code == 0
    methods = [m for (m, _p, _b) in runner.api_calls]
    assert methods == ["GET", "PUT"]  # H1 before-state export precedes the mutation


def test_audit_reads_three_surfaces(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0, stdout="[]") if "protection" not in p
                                 else gh_result(returncode=1, stderr="(HTTP 404)", status_code=404))
    code, _ = bp.run_audit(runner, _cfg(fixtures_dir))
    assert code == 0
    assert len(runner.api_calls) == 3


def test_rollback_dry_run_records_nothing(fixtures_dir: Path, fake_runner_factory, tmp_path: Path) -> None:
    cfg = _cfg(fixtures_dir)
    # Seed a null snapshot in a temp exports dir by monkeypatch-free construction: write it.
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "main.json").write_text("null\n")

    class _Cfg:
        repo = cfg.repo
        branch_protection = cfg.branch_protection
        exports_dir = exports

    runner = fake_runner_factory()
    code, lines = bp.run_rollback(runner, _Cfg(), apply=False)
    assert code == 0
    assert runner.api_calls == []
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
    assert calls[-1][2] == {"checks": [{"context": "ci-required"}]}
