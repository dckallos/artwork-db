"""
Unit tests for CI required-check reconciliation (no network).

Derivation is asserted data-drivenly against committed workflow fixtures; execution runs
through the fake ``GhRunner`` from ``conftest``. H2: the reconciled required context is
always the aggregate ``ci-required`` and never a path-filtered job name. H5: malformed,
empty, or missing workflows yield actionable file/field-scoped errors.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.no_network

from ghclient import ci
from ghclient.config import load_config
from ghclient.errors import ConfigError

_AGGREGATE = "ci-required"
_REQUIRED_CHECKS = "repos/octocat/hello-world/branches/main/protection/required_status_checks"


def _cfg(fixtures_dir: Path):
    """
    Load the committed ci-reconcile config against the fixtures package dir.
    """
    return load_config(fixtures_dir / "ci-reconcile-config.yml", package_dir=fixtures_dir)


def _text(fixtures_dir: Path, name: str) -> str:
    """
    Read a committed workflow fixture by file name.
    """
    return (fixtures_dir / name).read_text()


# --------------------------------------------------------------------------- #
# Pure derivation (matrix / skipped / duplicate).
# --------------------------------------------------------------------------- #
def test_matrix_jobs_expand_to_one_context_each(fixtures_dir: Path) -> None:
    contexts = ci.job_check_contexts(_text(fixtures_dir, "workflow-matrix.yml"), source="matrix")
    assert "unit (3.11)" in contexts
    assert "unit (3.12)" in contexts
    assert _AGGREGATE in contexts


def test_skipped_and_path_filtered_jobs_still_declare_contexts(fixtures_dir: Path) -> None:
    contexts = ci.job_check_contexts(_text(fixtures_dir, "workflow-skipped.yml"), source="skipped")
    assert {"pytest", "docs", _AGGREGATE} <= set(contexts)


def test_duplicate_job_names_are_deduped_preserving_order(fixtures_dir: Path) -> None:
    contexts = ci.job_check_contexts(_text(fixtures_dir, "workflow-duplicate.yml"), source="dup")
    assert contexts.count("shared") == 1
    assert _AGGREGATE in contexts


def test_declared_context_names_include_job_ids_and_names(fixtures_dir: Path) -> None:
    names = ci.declared_context_names(_text(fixtures_dir, "workflow-normal.yml"), source="normal")
    assert _AGGREGATE in names
    assert "dbt-checks" in names  # job id
    assert "dbt checks" in names  # job name


# --------------------------------------------------------------------------- #
# H2: desired required context is the aggregate, never a path-filtered job name.
# --------------------------------------------------------------------------- #
def test_plan_desired_is_exactly_the_aggregate(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    workflows = [("workflow-normal.yml", _text(fixtures_dir, "workflow-normal.yml"))]
    plan = ci.build_reconcile_plan(cfg, workflows, branch="main", current_contexts=["test"])
    assert plan.desired_contexts == (_AGGREGATE,)
    # None of the path-filtered job contexts leak into the required set.
    for path_job in ("dbt-checks", "dbt checks", "github-client"):
        assert path_job not in plan.desired_contexts
    assert plan.changed is True


def test_plan_is_noop_when_already_aggregate(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    workflows = [("workflow-normal.yml", _text(fixtures_dir, "workflow-normal.yml"))]
    plan = ci.build_reconcile_plan(cfg, workflows, branch="main", current_contexts=[_AGGREGATE])
    assert plan.changed is False


# --------------------------------------------------------------------------- #
# H5: adversarial inputs yield actionable, scoped errors.
# --------------------------------------------------------------------------- #
def test_malformed_workflow_is_actionable(fixtures_dir: Path) -> None:
    with pytest.raises(ConfigError, match="invalid workflow YAML"):
        ci.job_check_contexts(_text(fixtures_dir, "workflow-malformed.yml"), source="malformed")


def test_empty_jobs_workflow_is_actionable(fixtures_dir: Path) -> None:
    with pytest.raises(ConfigError, match="defines no jobs"):
        ci.job_check_contexts(_text(fixtures_dir, "workflow-empty-jobs.yml"), source="empty")


def test_aggregate_not_a_job_is_actionable(fixtures_dir: Path) -> None:
    cfg = _cfg(fixtures_dir)
    # A workflow whose jobs do not include the configured aggregate context.
    text = "name: x\non: {pull_request: {}}\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    with pytest.raises(ConfigError, match=r"ci\.aggregate_context"):
        ci.build_reconcile_plan(cfg, [("x.yml", text)], branch="main", current_contexts=[])


# --------------------------------------------------------------------------- #
# Execution through the fake runner (dry-run / apply / idempotent / fail-aware).
# --------------------------------------------------------------------------- #
def _get_returns(contexts):
    """
    Build a handler that answers the required-status-checks GET with ``contexts`` and any
    PATCH with an empty 200.
    """
    import json as _json

    def handler(kind, method, path, body):
        from ghclient.gh import GhResult

        if method == "GET":
            return GhResult(args=(), returncode=0, stdout=_json.dumps({"strict": True, "contexts": contexts}), status_code=200)
        return GhResult(args=(), returncode=0, stdout="{}", status_code=200)

    return handler


def test_dry_run_reconcile_executes_no_patch(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory(_get_returns(["test"]))
    code, lines = ci.run_reconcile(runner, _cfg(fixtures_dir), apply=False, workflows_root=fixtures_dir)
    assert code == 0
    assert [c for c in runner.api_calls if c[0] == "PATCH"] == []
    assert any("dry-run" in line for line in lines)


def test_apply_issues_exactly_one_patch_of_the_aggregate(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory(_get_returns(["test"]))
    code, _ = ci.run_reconcile(runner, _cfg(fixtures_dir), apply=True, workflows_root=fixtures_dir)
    assert code == 0
    patches = [(p, b) for (m, p, b) in runner.api_calls if m == "PATCH"]
    assert patches == [(_REQUIRED_CHECKS, {"checks": [{"context": _AGGREGATE}]})]


def test_apply_is_idempotent(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory(_get_returns([_AGGREGATE]))
    code, _ = ci.run_reconcile(runner, _cfg(fixtures_dir), apply=True, workflows_root=fixtures_dir)
    assert code == 0
    assert [c for c in runner.api_calls if c[0] == "PATCH"] == []  # already reconciled


def test_missing_protection_is_actionable(fixtures_dir: Path, fake_runner_factory, gh_result) -> None:
    runner = fake_runner_factory(lambda k, m, p, b: gh_result(returncode=1, stderr="Not Found (HTTP 404)", status_code=404))
    code, lines = ci.run_reconcile(runner, _cfg(fixtures_dir), apply=True, workflows_root=fixtures_dir)
    assert code == 1
    assert any("branch protection" in line.lower() or "required status checks" in line.lower() for line in lines)
    assert [c for c in runner.api_calls if c[0] == "PATCH"] == []  # never mutate on a failed read


def test_missing_workflow_file_is_actionable(fixtures_dir: Path, tmp_path: Path, fake_runner_factory) -> None:
    # workflows_root without the configured workflow -> actionable "not found".
    runner = fake_runner_factory(_get_returns(["test"]))
    code, lines = ci.run_reconcile(runner, _cfg(fixtures_dir), apply=False, workflows_root=tmp_path)
    assert code == 1
    assert any("not found" in line.lower() for line in lines)


def test_unknown_branch_selection_is_actionable(fixtures_dir: Path, fake_runner_factory) -> None:
    runner = fake_runner_factory(_get_returns(["test"]))
    code, lines = ci.run_reconcile(runner, _cfg(fixtures_dir), branch="nope", apply=False, workflows_root=fixtures_dir)
    assert code == 1
    assert any("nope" in line for line in lines)
