"""
Unit tests for preflight (offline; gh seam + which injected).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient.config import load_config
from ghclient.preflight import preflight


def _cfg(fixtures_dir: Path):
    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def test_preflight_all_green(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    report = preflight(runner, _cfg(fixtures_dir), which=lambda name: "/usr/bin/jq")
    assert report.ok is True
    assert "preflight: PASS" in report.render()


def test_preflight_fails_when_unauthenticated(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=1, stderr="not logged in"))
    report = preflight(runner, _cfg(fixtures_dir), which=lambda name: "/usr/bin/jq")
    assert report.ok is False
    assert any(c.name == "gh auth" and not c.ok for c in report.checks)


def test_preflight_fails_when_jq_missing(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    report = preflight(runner, _cfg(fixtures_dir), which=lambda name: None)
    assert report.ok is False
    assert any(c.name == "jq" and not c.ok for c in report.checks)


def test_preflight_fails_when_config_none(fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=0))
    report = preflight(runner, None, which=lambda name: "/usr/bin/jq")
    assert report.ok is False
    assert any(c.name == "config" and not c.ok for c in report.checks)
