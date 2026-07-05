"""
Unit tests for the unified preflight (offline; gh seam injected).

Checks: gh auth, config validity, and repo admin permission (A5). The obsolete jq
check is gone. The admin check runs only when config loaded AND gh is authenticated.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient.config import load_config
from ghclient.preflight import preflight


def _cfg(fixtures_dir: Path):
    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def _handler(gh_result, *, admin: bool):
    """
    Answer ``gh auth status`` (a run) with success and ``gh api repos/…`` with a
    permissions payload carrying the given admin bit.
    """
    def handler(kind, method, path, body):
        if kind == "api":
            return gh_result(returncode=0, stdout='{"permissions": {"admin": %s}}' % ("true" if admin else "false"))
        return gh_result(returncode=0)

    return handler


def test_preflight_all_green(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    report = preflight(fake_runner_factory(_handler(gh_result, admin=True)), _cfg(fixtures_dir))
    assert report.ok is True
    assert "preflight: PASS" in report.render()
    assert any(c.name == "repo admin" and c.ok for c in report.checks)


def test_preflight_fails_when_unauthenticated(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=1, stderr="not logged in"))
    report = preflight(runner, _cfg(fixtures_dir))
    assert report.ok is False
    assert any(c.name == "gh auth" and not c.ok for c in report.checks)
    # The admin check is skipped when unauthenticated (it needs a working credential).
    assert not any(c.name == "repo admin" for c in report.checks)


def test_preflight_fails_when_not_admin(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    report = preflight(fake_runner_factory(_handler(gh_result, admin=False)), _cfg(fixtures_dir))
    assert report.ok is False
    assert any(c.name == "repo admin" and not c.ok for c in report.checks)


def test_preflight_fails_when_repo_unreadable(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if kind == "api":
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        return gh_result(returncode=0)

    report = preflight(fake_runner_factory(handler), _cfg(fixtures_dir))
    assert report.ok is False
    assert any(c.name == "repo admin" and not c.ok for c in report.checks)


def test_preflight_fails_when_config_none(fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    report = preflight(runner, None)
    assert report.ok is False
    assert any(c.name == "config" and not c.ok for c in report.checks)
