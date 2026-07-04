"""
Governance-contract tests (H1-C7): lock the high-level invariants that A and C can
silently regress, asserted against the **real committed** config, policy body, and
workflows -- not fixtures. Deterministic and credential-free (no network, no ``gh``).

These are the contracts the external review flagged as regressable:
  * the committed ``policy.main.json`` must not re-introduce a forbidden ``test`` check;
  * ``branch-protection apply`` must derive required checks from ``ci.aggregate_context``
    (never regress the branch away from the always-emitting aggregate);
  * ``ci reconcile`` must carry ``strict`` through its PATCH (never silently flip it);
  * no committed workflow may invoke ``ghclient ... --apply`` (H4).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.no_network

from ghclient import branch_protection as bp
from ghclient import ci
from ghclient.config import default_config_path, load_config


def _real_cfg():
    """
    Load the repo's real committed ``config/github-client-config.yml``.
    """
    return load_config(default_config_path())


def test_committed_policy_has_no_forbidden_required_check() -> None:
    cfg = _real_cfg()
    policy = cfg.branch_protection.get("main")
    body = bp.load_policy_body(policy.policy_path)
    rsc = body.get("required_status_checks")
    if isinstance(rsc, dict):
        present = {c for c in (rsc.get("contexts") or []) if isinstance(c, str)}
        present |= {
            c.get("context")
            for c in (rsc.get("checks") or [])
            if isinstance(c, dict) and c.get("context")
        }
        assert bp._FORBIDDEN_CONTEXTS.isdisjoint(present), (
            f"committed policy re-introduced forbidden required check(s): "
            f"{sorted(present & bp._FORBIDDEN_CONTEXTS)}"
        )


def test_apply_derives_required_check_from_aggregate_no_regression() -> None:
    cfg = _real_cfg()
    assert cfg.ci is not None, "real config must declare a ci block for the aggregate"
    policy = cfg.branch_protection.get("main")
    assert policy.required_checks_from_workflows is True
    body = bp.policy_body_for_apply(cfg, policy)
    # The only required check is the always-emitting aggregate, via the modern checks array.
    assert body["required_status_checks"]["checks"] == [
        {"context": cfg.ci.aggregate_context, "app_id": -1}
    ]
    assert body["required_status_checks"]["contexts"] == []
    # And it is genuinely derived from config, not a hardcoded literal.
    assert cfg.ci.aggregate_context not in bp._FORBIDDEN_CONTEXTS


def test_reconcile_patch_carries_strict_through() -> None:
    cfg = _real_cfg()
    assert cfg.ci is not None
    # A minimal synthetic workflow that declares the aggregate job, so the plan builds
    # without depending on the exact contents of the committed workflows.
    wf = f"jobs:\n  {cfg.ci.aggregate_context}:\n    runs-on: ubuntu-latest\n"
    for strict in (True, False):
        plan = ci.build_reconcile_plan(
            cfg, [("synthetic.yml", wf)], branch="main", current_contexts=["test"], strict=strict
        )
        assert plan.strict is strict  # carried, never silently flipped (C4)
        assert plan.desired_contexts == (cfg.ci.aggregate_context,)


def test_no_committed_workflow_runs_ghclient_apply() -> None:
    cfg = _real_cfg()
    workflows_dir = cfg.repo_root / ".github" / "workflows"
    files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    assert files, f"expected committed workflows under {workflows_dir}"
    for path in files:
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue  # a comment documenting the rule is not a violation
            if "ghclient" in line:
                assert "--apply" not in line, (
                    f"{path.name}:{lineno} invokes ghclient with --apply; "
                    "no CI job may mutate GitHub state (H4)"
                )
