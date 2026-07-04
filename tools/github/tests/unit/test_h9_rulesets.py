"""
H9 ruleset-awareness (no network).

Before any classic-protection mutation, the audit path inventories BOTH classic branch
protection AND active repo/org rulesets, and reports overlap. v1 mutates classic only and
must never silently fight a ruleset. Fixtures drive the expectations.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp

_REPO = "octocat/hello-world"
_PROTECTION = f"repos/{_REPO}/branches/main/protection"
_RULESETS = f"repos/{_REPO}/rulesets?includes_parents=true"
_BRANCH_RULES = f"repos/{_REPO}/rules/branches/main"


def _handler(fixtures_dir: Path, gh_result):
    """
    Serve classic protection (404), rulesets, and branch rules from committed fixtures.
    """
    rulesets = (fixtures_dir / "rulesets.json").read_text()
    branch_rules = (fixtures_dir / "branch-rules.json").read_text()

    def handler(kind, method, path, body):
        if path == _PROTECTION:
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        if path == _RULESETS:
            return gh_result(returncode=0, stdout=rulesets)
        if path == _BRANCH_RULES:
            return gh_result(returncode=0, stdout=branch_rules)
        return gh_result(returncode=0, stdout="[]")

    return handler


def test_audit_inventories_both_and_reports_overlap(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(_handler(fixtures_dir, gh_result))
    report = bp.audit(runner, _REPO, "main")

    # Read BOTH surfaces: classic protection + rulesets + branch rules.
    paths = [p for (_m, p, _b) in runner.api_calls]
    assert _PROTECTION in paths and _RULESETS in paths and _BRANCH_RULES in paths

    expected_rules = json.loads((fixtures_dir / "branch-rules.json").read_text())
    assert report.classic.is_null
    assert len(report.rulesets) == 1
    assert report.has_ruleset_overlap
    assert len(report.branch_rules) == len(expected_rules)

    rendered = report.render()
    assert "WARNING" in rendered and "CLASSIC ONLY" in rendered


def test_audit_no_overlap_when_no_branch_rules(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    def handler(kind, method, path, body):
        if path == _PROTECTION:
            return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
        return gh_result(returncode=0, stdout="[]")

    report = bp.audit(fake_runner_factory(handler), _REPO, "main")
    assert not report.has_ruleset_overlap
    assert "ruleset overlap: none" in report.render()


def _overlap_handler(fixtures_dir: Path, gh_result):
    """
    Unprotected classic (404 GET / 200 PUT) plus a ruleset overlap from committed fixtures.
    """
    rulesets = (fixtures_dir / "rulesets.json").read_text()
    branch_rules = (fixtures_dir / "branch-rules.json").read_text()

    def handler(kind, method, path, body):
        if "protection" in path:
            if method == "GET":
                return gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404)
            return gh_result(returncode=0, stdout="{}")
        if "rulesets" in path:
            return gh_result(returncode=0, stdout=rulesets)
        if "rules/branches" in path:
            return gh_result(returncode=0, stdout=branch_rules)
        return gh_result(returncode=0, stdout="[]")

    return handler


def _cfg(fixtures_dir: Path):
    """
    Load the committed valid config, resolving policy paths under the fixtures dir.
    """
    from ghclient.config import load_config

    return load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)


def test_apply_blocks_on_ruleset_overlap_unless_overridden(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    cfg = _cfg(fixtures_dir)
    handler = _overlap_handler(fixtures_dir, gh_result)

    # --apply WITHOUT override: overlap blocks the mutation (A3).
    runner = fake_runner_factory(handler)
    code, lines = bp.run_apply(runner, cfg, apply=True)
    assert code == 1
    assert "PUT" not in [m for (m, _p, _b) in runner.api_calls]
    assert any("BLOCKED" in ln for ln in lines) and any("WARNING" in ln for ln in lines)

    # --apply WITH the explicit override: proceeds to exactly one PUT.
    runner2 = fake_runner_factory(handler)
    code2, lines2 = bp.run_apply(runner2, cfg, apply=True, allow_ruleset_overlap=True)
    assert code2 == 0
    assert [m for (m, _p, _b) in runner2.api_calls].count("PUT") == 1
    assert any("WARNING" in ln for ln in lines2)


def test_dry_run_warns_on_overlap_without_mutating(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    cfg = _cfg(fixtures_dir)
    runner = fake_runner_factory(_overlap_handler(fixtures_dir, gh_result))
    code, lines = bp.run_apply(runner, cfg, apply=False)
    assert code == 0
    assert "PUT" not in [m for (m, _p, _b) in runner.api_calls]
    assert any("WARNING" in ln for ln in lines)
