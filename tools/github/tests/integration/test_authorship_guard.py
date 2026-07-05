"""
H7 authorship-guard tests (no network).

Exercises the relocated, hardened ``scripts/check_no_attribution.sh`` against throwaway
git repositories: clean trees pass, markers in the newly-covered file types (``.md`` and
friends) are caught, the escape token is honored, an explicit ``--base`` range works, and
the sandbox-branch default has been removed. Skips cleanly where ``git``/``bash`` are
unavailable.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

_GUARD = Path(__file__).resolve().parents[4] / "scripts" / "check_no_attribution.sh"

_missing_tools = shutil.which("git") is None or shutil.which("bash") is None
pytestmark = [pytest.mark.no_network, pytest.mark.skipif(_missing_tools, reason="git/bash unavailable")]


def _git(repo: Path, *args: str) -> None:
    """
    Run a git command in ``repo``, raising on failure.
    """
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    """
    Initialize a throwaway repo with a deterministic identity and one clean commit.
    """
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")
    (repo / "README.md").write_text("# project\nnothing to see\n")
    (repo / "flow.yml").write_text("jobs:\n  build: {}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "initial clean commit")


def _run_guard(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """
    Invoke the guard inside ``repo`` and return the completed process.
    """
    return subprocess.run(
        ["bash", str(_GUARD), *args], cwd=repo, capture_output=True, text=True
    )


def test_guard_exists_and_dropped_sandbox_default() -> None:
    assert _GUARD.is_file(), f"guard not found at {_GUARD}"
    text = _GUARD.read_text()
    assert "donkey-kong-sandbox" not in text  # H7: sandbox base default removed


def test_clean_repo_passes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    result = _run_guard(tmp_path, "--files-only")
    assert result.returncode == 0, result.stderr


def test_marker_in_markdown_is_caught(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "notes.md").write_text("Generated with Claude Code\n")
    _git(tmp_path, "add", "-A")
    result = _run_guard(tmp_path, "--files-only")
    assert result.returncode == 1
    assert "notes.md" in result.stderr


def test_allow_token_is_respected(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "notes.md").write_text("Generated with Claude Code authorship-marker-ok\n")
    _git(tmp_path, "add", "-A")
    result = _run_guard(tmp_path, "--files-only")
    assert result.returncode == 0, result.stderr


def test_markdown_prose_body_discussing_marker_is_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # A review/doc that DISCUSSES a marker deep in its prose (outside the edge windows)
    # must not be flagged (C5): clean header + footer, marker only in the middle.
    body = (
        ["# Review notes", ""]
        + [f"line {i}" for i in range(1, 26)]
        + ["We must never let a tool write 'Generated with Claude Code' as a footer.", ""]
        + [f"tail {i}" for i in range(1, 26)]
        + ["## End", ""]
    )
    (tmp_path / "review.md").write_text("\n".join(body))
    _git(tmp_path, "add", "-A")
    result = _run_guard(tmp_path, "--files-only")
    assert result.returncode == 0, result.stderr


def test_markdown_automated_footer_is_caught(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # An automated attribution FOOTER in the last lines is still caught structurally.
    body = ["# Change log", ""] + [f"entry {i}" for i in range(1, 40)] + [
        "",
        "Generated with Cortex Code",
        "",
    ]
    (tmp_path / "CHANGELOG.md").write_text("\n".join(body))
    _git(tmp_path, "add", "-A")
    result = _run_guard(tmp_path, "--files-only")
    assert result.returncode == 1
    assert "CHANGELOG.md" in result.stderr


def test_commit_scan_with_explicit_base(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True
    ).stdout.strip()
    (tmp_path / "feature.txt").write_text("a change\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "Co-authored-by: Cortex Code <noreply@snowflake.com>")
    result = _run_guard(tmp_path, "--commits-only", "--base", base)
    assert result.returncode == 1
    assert "noreply@snowflake.com" in result.stderr or "co-authored-by" in result.stderr.lower()
