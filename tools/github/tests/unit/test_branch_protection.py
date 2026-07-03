"""
Unit tests for branch-protection plan building and the CLI wrappers (no network).

Everything is driven through the fake ``GhRunner`` from ``conftest`` and the committed
config fixture, so no live ``gh`` call is ever made and expectations come from fixtures
rather than scattered literals.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp
from ghclient.branch_protection import ActionKind, Snapshot
from ghclient.config import load_config
from ghclient.errors import GhApiError, GhClientError

_PROTECTION = "repos/octocat/hello-world/branches/main/protection"


def _cfg(fixtures_dir: Path):
    """
    Load the committed valid config, resolving policy paths under the fixtures dir.
    """
    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def test_plan_apply_builds_put_from_policy_body(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    policy = cfg.branch_protection.get("main")
    action = bp.plan_apply(cfg.repo, policy)
    assert action.kind is ActionKind.PUT
    assert action.api_path == _PROTECTION
    assert action.body == bp.load_policy_body(policy.policy_path)
    assert isinstance(action.body, dict)


def test_dry_run_apply_executes_nothing(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory()
    code, lines = bp.run_apply(runner, _cfg(fixtures_dir), apply=False)
    assert code == 0
    assert runner.api_calls == []  # dry-run mutates nothing
    assert any("dry-run" in line for line in lines)


def test_apply_puts_policy_and_is_idempotent(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    cfg = _cfg(fixtures_dir)
    body = bp.load_policy_body(cfg.branch_protection.get("main").policy_path)

    def handler(kind, method, path, in_body):
        # 404 on the pre-apply export (branch currently unprotected), 200 on the PUT.
        if method == "GET":
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        return gh_result(returncode=0, stdout="{}")

    runner = fake_runner_factory(handler)
    code, _ = bp.run_apply(runner, cfg, apply=True)
    assert code == 0
    puts = [(p, b) for (m, p, b) in runner.api_calls if m == "PUT"]
    assert puts == [(_PROTECTION, body)]  # exactly one PUT of the desired body

    # Re-applying converges to the same single PUT of the same body (idempotent).
    runner2 = fake_runner_factory(handler)
    bp.run_apply(runner2, cfg, apply=True)
    assert [(p, b) for (m, p, b) in runner2.api_calls if m == "PUT"] == [(_PROTECTION, body)]


def test_rollback_branches_delete_vs_put() -> None:
    null_snap = Snapshot(branch="main", body=None, source="verified-404")
    assert bp.plan_rollback("octocat/hello-world", null_snap).kind is ActionKind.DELETE

    saved = Snapshot(branch="main", body={"enforce_admins": False}, source="live")
    put = bp.plan_rollback("octocat/hello-world", saved)
    assert put.kind is ActionKind.PUT
    assert put.body == {"enforce_admins": False}


def test_execute_raises_on_failed_mutation(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    cfg = _cfg(fixtures_dir)
    action = bp.plan_apply(cfg.repo, cfg.branch_protection.get("main"))
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=1, stderr="(HTTP 500)", status_code=500))
    with pytest.raises(GhApiError) as exc:
        bp.execute(runner, action)
    assert exc.value.status_code == 500


def test_unknown_branch_selection_is_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    code, lines = bp.run_apply(fake_runner_factory(), _cfg(fixtures_dir), branch="nope", apply=False)
    assert code == 1
    assert any("not a configured protected branch" in line for line in lines)
