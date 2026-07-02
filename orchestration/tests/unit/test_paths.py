"""Unit tests for robust repo-root resolution (installed-package safe).

Imports only the dependency-free :mod:`artwork_orchestration._paths` -- no Dagster.
"""
from __future__ import annotations

from pathlib import Path

from artwork_orchestration._paths import REPO_ROOT_ENV, resolve_repo_root


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(REPO_ROOT_ENV, str(tmp_path))
    assert resolve_repo_root("artwork_pipeline") == tmp_path.resolve()


def test_env_override_expands_user(monkeypatch):
    monkeypatch.setenv(REPO_ROOT_ENV, "~/somewhere")
    assert resolve_repo_root("anything") == (Path.home() / "somewhere").resolve()


def test_marker_walk_finds_project_dir(monkeypatch, tmp_path):
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    root = tmp_path / "repo"
    proj = root / "myproj"
    proj.mkdir(parents=True)
    (proj / "dbt_project.yml").write_text("name: x\nprofile: p\n")
    start = proj / "orchestration" / "pkg" / "config.py"
    start.parent.mkdir(parents=True)
    start.write_text("# marker")
    assert resolve_repo_root("myproj", start=start) == root.resolve()


def test_marker_walk_finds_repo_root_file(monkeypatch, tmp_path):
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    root = tmp_path / "repo"
    (root).mkdir()
    (root / "AGENTS.md").write_text("marker")
    start = root / "a" / "b" / "c.py"
    start.parent.mkdir(parents=True)
    start.write_text("# x")
    assert resolve_repo_root("no_such_project", start=start) == root.resolve()


def test_fallback_to_parents_two_when_no_marker(monkeypatch, tmp_path):
    monkeypatch.delenv(REPO_ROOT_ENV, raising=False)
    # No markers anywhere: falls back to <start>.parents[2].
    start = tmp_path / "orchestration" / "pkg" / "config.py"
    start.parent.mkdir(parents=True)
    start.write_text("# x")
    assert resolve_repo_root("nope", start=start) == tmp_path.resolve()
