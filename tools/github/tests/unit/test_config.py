"""
Unit tests for config parsing/validation (no network).
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient.config import load_config
from ghclient.errors import ConfigError


def test_valid_config_parses_to_frozen_dataclasses(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)
    assert cfg.repo == "octocat/hello-world"
    assert cfg.branch_protection.names() == ["main"]
    main = cfg.branch_protection.get("main")
    assert main.branch == "main"
    assert main.required_checks_from_workflows is True
    assert main.policy_path.exists()
    assert main.policy_path.name == "policy.main.json"


def test_unknown_branch_key_is_rejected(fixtures_dir: Path) -> None:
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(fixtures_dir / "unknown-key-config.yml", package_dir=fixtures_dir)


def test_missing_policy_file_is_actionable(fixtures_dir: Path) -> None:
    with pytest.raises(ConfigError, match=r"branch_protection\.branches\.main\.policy: file not found"):
        load_config(fixtures_dir / "missing-policy-config.yml", package_dir=fixtures_dir)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="config file not found"):
        load_config(tmp_path / "nope.yml", package_dir=tmp_path)


def test_bad_repo_slug_is_actionable(tmp_path: Path) -> None:
    bad = tmp_path / "c.yml"
    bad.write_text("repo: notaslug\nbranch_protection:\n  branches:\n    main:\n      policy: p.json\n")
    with pytest.raises(ConfigError, match="expected 'owner/name'"):
        load_config(bad, package_dir=tmp_path)


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "p.json").write_text("{}")
    bad = tmp_path / "c.yml"
    bad.write_text(
        "repo: a/b\nsurprise: 1\nbranch_protection:\n  branches:\n    main:\n      policy: policies/p.json\n"
    )
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(bad, package_dir=tmp_path)


def test_get_unknown_branch_lists_available(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "valid-config.yml", package_dir=fixtures_dir)
    with pytest.raises(ConfigError, match="not a configured protected branch"):
        cfg.branch_protection.get("develop")
