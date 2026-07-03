"""
Branch-protection: config-driven apply / export / rollback / audit.

Ported from ``bin/*-branch-protection.sh`` but split into pure, testable pieces:

* **plan builders** turn desired-state (a policy JSON) or a snapshot into a typed
  :class:`ProtectionAction` -- no I/O, no ``gh``;
* **execution** is a separate step that runs the plan through an injected
  :class:`~ghclient.gh.GhRunner`; dry-run renders the plan and runs nothing.

H1 (fail-closed export/rollback):
  ``export_snapshot`` writes a ``null`` snapshot ONLY for a *verified* HTTP 404
  ("protection not found"). Every other failure (auth/403/5xx/network/timeout/
  bad-repo) raises -- no snapshot is written. Because a ``null`` file can there-
  fore only come from a verified 404, ``plan_rollback`` may safely DELETE from a
  ``null`` snapshot; a non-null-but-unparseable snapshot is refused.

H9 (ruleset awareness):
  ``audit`` inventories BOTH classic branch protection AND active repo rulesets
  that target the branch, and reports overlap. v1 mutates classic only and never
  silently fights a ruleset.

Importing this module is side-effect-free.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .config import BranchPolicyCfg, GithubClientConfig
from .errors import GhApiError, GhClientError
from .gh import GhResult, GhRunner


def _protection_path(repo: str, branch: str) -> str:
    """
    REST path for a branch's classic protection.
    """
    return f"repos/{repo}/branches/{branch}/protection"


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------
class ActionKind(str, Enum):
    """
    What a :class:`ProtectionAction` will do to the live branch protection.
    """

    PUT = "PUT"
    DELETE = "DELETE"
    NOOP = "NOOP"


@dataclass(frozen=True)
class ProtectionAction:
    """
    A single planned change to one branch's classic protection.

    Pure data: building it touches neither ``gh`` nor the network. ``body`` is the
    PUT payload for :attr:`ActionKind.PUT` (``None`` for DELETE/NOOP).
    """

    kind: ActionKind
    repo: str
    branch: str
    reason: str
    body: Optional[dict] = None

    @property
    def api_path(self) -> str:
        """
        REST path this action targets.
        """
        return _protection_path(self.repo, self.branch)

    def render(self) -> str:
        """
        Human-readable preview of the exact change (the dry-run output).
        """
        head = f"[{self.kind.value}] {self.branch} -> {self.api_path}  ({self.reason})"
        if self.kind is ActionKind.PUT and self.body is not None:
            return head + "\n" + json.dumps(self.body, indent=2, sort_keys=True)
        return head


@dataclass(frozen=True)
class Snapshot:
    """
    A before-state capture of one branch's classic protection.

    ``body is None`` means "no protection" and -- per H1 -- can only be produced
    by a verified HTTP 404. ``source`` records that provenance for auditing.
    """

    branch: str
    body: Optional[dict]
    source: str  # "live" | "verified-404"

    @property
    def is_null(self) -> bool:
        """
        True when the branch had no protection at snapshot time.
        """
        return self.body is None


@dataclass(frozen=True)
class AuditReport:
    """
    The read-only inventory produced by :func:`audit` (classic + rulesets, H9).
    """

    repo: str
    branch: str
    classic: Snapshot
    rulesets: Tuple[dict, ...] = field(default_factory=tuple)
    branch_rules: Tuple[dict, ...] = field(default_factory=tuple)

    @property
    def has_ruleset_overlap(self) -> bool:
        """
        True when one or more rulesets also govern this branch.
        """
        return bool(self.branch_rules)

    def render(self) -> str:
        """
        Human-readable audit summary, including any ruleset overlap warning.
        """
        lines = [f"# audit: {self.repo}@{self.branch}"]
        if self.classic.is_null:
            lines.append("classic protection: NONE (verified 404)")
        else:
            lines.append("classic protection: PRESENT")
        lines.append(f"active rulesets: {len(self.rulesets)}")
        if self.has_ruleset_overlap:
            kinds = sorted({str(r.get("type", "?")) for r in self.branch_rules})
            lines.append(
                f"WARNING: {len(self.branch_rules)} ruleset-sourced rule(s) also "
                f"govern {self.branch} (types: {kinds}). v1 mutates CLASSIC ONLY; "
                "review overlap before applying."
            )
        else:
            lines.append("ruleset overlap: none")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure plan builders
# ---------------------------------------------------------------------------
def load_policy_body(policy_path: Path) -> dict:
    """
    Read and parse a desired-state policy JSON body, with actionable errors.
    """
    if not policy_path.exists():
        raise GhClientError(f"policy file not found: {policy_path}")
    try:
        body = json.loads(policy_path.read_text())
    except json.JSONDecodeError as exc:
        raise GhClientError(f"{policy_path.name}: invalid JSON -- {exc}") from exc
    if not isinstance(body, dict):
        raise GhClientError(f"{policy_path.name}: policy body must be a JSON object.")
    return body


def plan_apply(repo: str, policy: BranchPolicyCfg) -> ProtectionAction:
    """
    Build the PUT plan that makes ``policy.branch`` match its desired-state body.

    Idempotent by construction: ``PUT .../protection`` replaces the whole config,
    so re-applying converges to the committed policy.
    """
    body = load_policy_body(policy.policy_path)
    return ProtectionAction(
        kind=ActionKind.PUT,
        repo=repo,
        branch=policy.branch,
        reason=f"apply desired-state policy {policy.policy_path.name}",
        body=body,
    )


def plan_rollback(repo: str, snapshot: Snapshot) -> ProtectionAction:
    """
    Build the plan that restores ``snapshot`` (the captured before-state).

    A ``null`` snapshot (verified 404) -> DELETE protection; a captured body ->
    PUT-restore it. H1: because ``export_snapshot`` never writes ``null`` on an
    error, a ``null`` snapshot is proof of a verified 404 and is delete-eligible.
    """
    if snapshot.is_null:
        if snapshot.source != "verified-404":
            raise GhClientError(
                f"refusing to DELETE protection on {snapshot.branch}: null "
                f"snapshot has untrusted provenance {snapshot.source!r} (H1)."
            )
        return ProtectionAction(
            kind=ActionKind.DELETE,
            repo=repo,
            branch=snapshot.branch,
            reason="restore unprotected before-state (verified 404)",
        )
    return ProtectionAction(
        kind=ActionKind.PUT,
        repo=repo,
        branch=snapshot.branch,
        reason="restore saved protection from snapshot",
        body=snapshot.body,
    )


# ---------------------------------------------------------------------------
# Snapshot I/O (H1 fail-closed)
# ---------------------------------------------------------------------------
def export_snapshot(runner: Any, repo: str, branch: str) -> Snapshot:
    """
    Capture the current live protection for ``branch`` -- fail-closed (H1).

    A verified HTTP 404 -> ``Snapshot(body=None, source="verified-404")``. Any
    other failure raises :class:`~ghclient.errors.GhApiError` and NO snapshot is
    produced, so a caller can never mistake "couldn't reach GitHub" for "no rules".
    """
    res: GhResult = runner.api(_protection_path(repo, branch), method="GET")
    if res.ok:
        try:
            body = json.loads(res.stdout)
        except json.JSONDecodeError as exc:
            raise GhApiError(
                f"export {repo}@{branch}: gh returned success but malformed JSON; "
                "failing closed (no snapshot written).",
                status_code=res.status_code,
                stderr=res.stderr,
            ) from exc
        return Snapshot(branch=branch, body=body, source="live")
    if res.status_code == 404:
        return Snapshot(branch=branch, body=None, source="verified-404")
    raise GhApiError(
        f"export {repo}@{branch}: gh api failed (HTTP {res.status_code}); failing "
        "closed -- no snapshot written, protection left untouched.",
        status_code=res.status_code,
        stderr=res.stderr,
    )


def write_snapshot(snapshot: Snapshot, exports_dir: Path) -> Path:
    """
    Persist ``snapshot`` to ``exports/<branch>.json`` (literal ``null`` when empty).
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    out = exports_dir / f"{snapshot.branch}.json"
    if snapshot.is_null:
        out.write_text("null\n")
    else:
        out.write_text(json.dumps(snapshot.body, indent=2, sort_keys=True) + "\n")
    return out


def read_snapshot(path: Path, branch: str) -> Snapshot:
    """
    Load a previously written snapshot, refusing a corrupt one.

    A literal ``null`` -> verified-404 (delete-eligible); a JSON object -> a live
    body; anything else raises (corrupt-snapshot rollback refusal, H5).
    """
    if not path.exists():
        raise GhClientError(
            f"no snapshot for {branch} at {path}; run `ghclient branch-protection "
            "export` first."
        )
    text = path.read_text().strip()
    if text == "null":
        return Snapshot(branch=branch, body=None, source="verified-404")
    try:
        body = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GhClientError(
            f"corrupt snapshot {path.name}: not valid JSON; refusing to roll back."
        ) from exc
    if not isinstance(body, dict):
        raise GhClientError(
            f"corrupt snapshot {path.name}: expected a JSON object or null; "
            "refusing to roll back."
        )
    return Snapshot(branch=branch, body=body, source="live")


# ---------------------------------------------------------------------------
# Ruleset inventory (H9)
# ---------------------------------------------------------------------------
def list_rulesets(runner: Any, repo: str) -> List[dict]:
    """
    List active repo rulesets, fail-closed on any non-404 error.
    """
    res: GhResult = runner.api(
        f"repos/{repo}/rulesets?includes_parents=true", method="GET"
    )
    if res.ok:
        data = json.loads(res.stdout or "[]")
        return list(data) if isinstance(data, list) else []
    if res.status_code == 404:
        return []
    raise GhApiError(
        f"audit {repo}: listing rulesets failed (HTTP {res.status_code}); failing "
        "closed.",
        status_code=res.status_code,
        stderr=res.stderr,
    )


def get_branch_rules(runner: Any, repo: str, branch: str) -> List[dict]:
    """
    List ruleset-sourced rules that apply to ``branch`` (fail-closed on non-404).
    """
    res: GhResult = runner.api(f"repos/{repo}/rules/branches/{branch}", method="GET")
    if res.ok:
        data = json.loads(res.stdout or "[]")
        return list(data) if isinstance(data, list) else []
    if res.status_code == 404:
        return []
    raise GhApiError(
        f"audit {repo}@{branch}: listing branch rules failed (HTTP "
        f"{res.status_code}); failing closed.",
        status_code=res.status_code,
        stderr=res.stderr,
    )


def audit(runner: Any, repo: str, branch: str) -> AuditReport:
    """
    Read-only inventory of classic protection + rulesets for ``branch`` (H9).
    """
    classic = export_snapshot(runner, repo, branch)
    rulesets = list_rulesets(runner, repo)
    branch_rules = get_branch_rules(runner, repo, branch)
    return AuditReport(
        repo=repo,
        branch=branch,
        classic=classic,
        rulesets=tuple(rulesets),
        branch_rules=tuple(branch_rules),
    )


def execute(runner: Any, action: ProtectionAction) -> GhResult:
    """
    Run a planned mutation through the injected runner.

    Only called on the ``--apply`` path; dry-run renders :meth:`ProtectionAction.render`
    and never reaches here. A NOOP is a no-op; a failed mutation raises.
    """
    if action.kind is ActionKind.NOOP:
        return GhResult(args=(), returncode=0, stdout="", stderr="", status_code=200)
    if action.kind is ActionKind.PUT:
        res = runner.api(action.api_path, method="PUT", input_body=action.body)
    else:  # DELETE
        res = runner.api(action.api_path, method="DELETE")
    if not res.ok:
        raise GhApiError(
            f"{action.kind.value} {action.repo}@{action.branch} failed (HTTP "
            f"{res.status_code}).",
            status_code=res.status_code,
            stderr=res.stderr,
        )
    return res


# ---------------------------------------------------------------------------
# CLI command wrappers: config -> plan -> (dry-run render | --apply execute).
# Each returns ``(exit_code, lines)``; dry-run is the default and mutates nothing.
# ---------------------------------------------------------------------------
def _selected_policies(cfg: GithubClientConfig, branch: Optional[str]) -> List[BranchPolicyCfg]:
    """
    Resolve the policies to act on: one ``--branch`` (validated) or all governed branches.
    """
    if branch is not None:
        return [cfg.branch_protection.get(branch)]
    return list(cfg.branch_protection.branches)


def run_apply(
    runner: GhRunner, cfg: GithubClientConfig, *, branch: Optional[str] = None, apply: bool = False
) -> Tuple[int, List[str]]:
    """
    Preview (default) or ``--apply`` the desired-state policy for the selected branches.

    On ``--apply`` the current state is exported first (H1 before-state), then the PUT
    runs. Idempotent: re-applying converges to the committed policy.
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            action = plan_apply(cfg.repo, policy)
            lines.append(action.render())
            if apply:
                snapshot = export_snapshot(runner, cfg.repo, policy.branch)
                out = write_snapshot(snapshot, cfg.exports_dir)
                lines.append(f"  before-state snapshot -> {out}")
                execute(runner, action)
                lines.append(f"  APPLIED: {policy.branch} protection updated.")
            else:
                lines.append(f"  (dry-run) pass --apply to PUT this policy to {policy.branch}.")
        except GhClientError as exc:
            code = 1
            lines.append(f"  ERROR ({policy.branch}): {exc}")
    return (code, lines)


def run_export(
    runner: GhRunner, cfg: GithubClientConfig, *, branch: Optional[str] = None
) -> Tuple[int, List[str]]:
    """
    Snapshot current live protection to ``policies/exports/`` -- fail-closed (H1).

    A verified 404 writes a ``null`` snapshot; any other failure writes nothing and
    yields a non-zero exit so a transport error is never mistaken for "no rules."
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            snapshot = export_snapshot(runner, cfg.repo, policy.branch)
            out = write_snapshot(snapshot, cfg.exports_dir)
            state = "no protection (verified 404)" if snapshot.is_null else "protection present"
            lines.append(f"exported {policy.branch}: {state} -> {out}")
        except GhClientError as exc:
            code = 1
            lines.append(
                f"export {policy.branch}: FAILED (fail-closed, no snapshot written): {exc}"
            )
    return (code, lines)


def run_rollback(
    runner: GhRunner, cfg: GithubClientConfig, *, branch: Optional[str] = None, apply: bool = False
) -> Tuple[int, List[str]]:
    """
    Preview (default) or ``--apply`` a restore from the last exported snapshot.

    A ``null`` snapshot (verified 404) DELETEs protection; a saved body PUT-restores it.
    A corrupt or untrusted snapshot is refused (H1/H5).
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            snapshot = read_snapshot(cfg.exports_dir / f"{policy.branch}.json", policy.branch)
            action = plan_rollback(cfg.repo, snapshot)
            lines.append(action.render())
            if apply:
                execute(runner, action)
                lines.append(f"  ROLLED BACK: {policy.branch}.")
            else:
                lines.append(f"  (dry-run) pass --apply to restore {policy.branch}.")
        except GhClientError as exc:
            code = 1
            lines.append(f"  ERROR ({policy.branch}): {exc}")
    return (code, lines)


def run_audit(
    runner: GhRunner, cfg: GithubClientConfig, *, branch: Optional[str] = None
) -> Tuple[int, List[str]]:
    """
    Report classic protection + ruleset overlap for the selected branches (read-only, H9).
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            lines.append(audit(runner, cfg.repo, policy.branch).render())
        except GhClientError as exc:
            code = 1
            lines.append(f"audit {policy.branch}: FAILED (fail-closed): {exc}")
    return (code, lines)
