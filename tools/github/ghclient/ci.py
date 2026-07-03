"""
Reconcile a branch's required CI checks to the always-emitting aggregate context (H2).

The problem this fixes (plan §2.2): both repo workflows are *path-filtered*, so a
docs-only PR runs neither and emits no status -- yet ``main`` required a check named
``test`` that nothing produces, deadlocking those PRs forever. The fix is to require a
single aggregate context (``ci-required``) that a workflow emits for **every** PR, and to
never require a path-filtered job name directly.

Design (mirrors ``branch_protection.py``):
  * Pure functions parse the configured workflow YAML and derive the check contexts each
    workflow declares (matrix-expanded, deduped) -- used to *validate* that the configured
    aggregate is a real job and to *preview* what feeds the gate.
  * :func:`build_reconcile_plan` returns the desired required contexts as **exactly** the
    configured aggregate (never a path job name).
  * Execution is a separate step through the injected :class:`~ghclient.gh.GhRunner`;
    dry-run by default, ``apply=True`` issues one ``PATCH`` and is idempotent.
  * Import-safe: no network, no disk, no credentials at import time.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import yaml

from .config import GithubClientConfig
from .errors import ConfigError, GhApiError, GhClientError
from .gh import GhRunner

__all__ = [
    "ReconcilePlan",
    "build_reconcile_plan",
    "declared_context_names",
    "job_check_contexts",
    "run_reconcile",
]


def required_checks_path(repo: str, branch: str) -> str:
    """
    The REST path for a branch's required-status-checks sub-resource.
    """
    return f"repos/{repo}/branches/{branch}/protection/required_status_checks"


# --------------------------------------------------------------------------- #
# Pure workflow parsing / derivation (no IO; drives the H2 + H5 tests).
# --------------------------------------------------------------------------- #
def _load_workflow(text: str, source: str) -> dict:
    """
    Parse workflow YAML into a mapping, raising a file-scoped :class:`ConfigError`.
    """
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(source, None, f"invalid workflow YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigError(source, None, "workflow YAML is not a mapping")
    return loaded


def _jobs(text: str, source: str) -> dict:
    """
    Return the workflow's ``jobs`` mapping, or raise if it is missing/empty.
    """
    top = _load_workflow(text, source)
    jobs = top.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        raise ConfigError(source, "jobs", "workflow defines no jobs")
    return jobs


def _context_name(job_id: str, job_def: Any) -> str:
    """
    The base check-context name for a job: its ``name:`` if set, else the job id.
    """
    if isinstance(job_def, dict):
        name = job_def.get("name")
        if isinstance(name, str) and name.strip():
            return name
    return job_id


def _expand_matrix(base: str, matrix: dict) -> List[str]:
    """
    Expand a job's ``strategy.matrix`` into GitHub-style ``base (v1, v2)`` contexts.

    Dimensions are the list-valued keys (excluding ``include``/``exclude``); their
    cartesian product yields one context each. ``include`` entries add one extra context
    apiece. A matrix with no list dimensions collapses to the base name.
    """
    dims = {
        key: val
        for key, val in matrix.items()
        if key not in ("include", "exclude") and isinstance(val, list) and val
    }
    contexts: List[str] = []
    if dims:
        keys = list(dims)
        for combo in itertools.product(*(dims[key] for key in keys)):
            label = ", ".join(str(v) for v in combo)
            contexts.append(f"{base} ({label})")
    else:
        contexts.append(base)

    for entry in matrix.get("include", []) or []:
        if isinstance(entry, dict) and entry:
            label = ", ".join(str(v) for v in entry.values())
            contexts.append(f"{base} ({label})")
    return contexts


def job_check_contexts(text: str, *, source: str) -> List[str]:
    """
    Derive the ordered, matrix-expanded check contexts a workflow declares.

    Skipped / path-filtered jobs (those with an ``if:``) still declare a context and are
    included; duplicate context names within one workflow are de-duplicated preserving
    order. Raises a scoped :class:`ConfigError` on malformed YAML or a job-less workflow.
    """
    contexts: List[str] = []
    for job_id, job_def in _jobs(text, source).items():
        base = _context_name(job_id, job_def)
        strategy = job_def.get("strategy") if isinstance(job_def, dict) else None
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        expanded = _expand_matrix(base, matrix) if isinstance(matrix, dict) else [base]
        for ctx in expanded:
            if ctx not in contexts:
                contexts.append(ctx)
    return contexts


def declared_context_names(text: str, *, source: str) -> set:
    """
    The set of base context names a workflow declares (each job id and its ``name:``).

    Used to validate that the configured aggregate context is a real job -- so we never
    reconcile a branch to a required check that no workflow can ever emit.
    """
    names: set = set()
    for job_id, job_def in _jobs(text, source).items():
        names.add(job_id)
        if isinstance(job_def, dict) and isinstance(job_def.get("name"), str):
            if job_def["name"].strip():
                names.add(job_def["name"])
    return names


@dataclass(frozen=True)
class ReconcilePlan:
    """
    The desired-vs-current required-check state for one branch.

    ``desired_contexts`` is always exactly the configured aggregate (H2).
    ``workflow_contexts`` is the informational list of path-job contexts that feed the
    aggregate, shown in the preview but never required directly.
    """

    repo: str
    branch: str
    api_path: str
    current_contexts: Tuple[str, ...]
    desired_contexts: Tuple[str, ...]
    workflow_contexts: Tuple[str, ...]

    @property
    def changed(self) -> bool:
        """
        True when the current required contexts differ from the desired set.
        """
        return sorted(self.current_contexts) != sorted(self.desired_contexts)


def build_reconcile_plan(
    cfg: GithubClientConfig,
    workflow_texts: Sequence[Tuple[str, str]],
    *,
    branch: str,
    current_contexts: Sequence[str],
) -> ReconcilePlan:
    """
    Build the reconcile plan: validate the aggregate exists, desire exactly that context.

    ``workflow_texts`` is a sequence of ``(source, text)`` pairs. Raises a scoped
    :class:`ConfigError` if the config has no ``ci`` block or if the configured
    ``aggregate_context`` is not a job in any configured workflow (which would set an
    unsatisfiable required check).
    """
    ci = cfg.ci
    if ci is None:
        raise ConfigError(str(cfg.config_path), "ci", "no ci block configured")

    declared: set = set()
    contexts: List[str] = []
    for source, text in workflow_texts:
        declared |= declared_context_names(text, source=source)
        for ctx in job_check_contexts(text, source=source):
            if ctx not in contexts:
                contexts.append(ctx)

    if ci.aggregate_context not in declared:
        raise ConfigError(
            ci.source,
            "ci.aggregate_context",
            f"{ci.aggregate_context!r} is not a job in any configured workflow; "
            f"declared jobs: {sorted(declared)}",
        )

    return ReconcilePlan(
        repo=cfg.repo,
        branch=branch,
        api_path=required_checks_path(cfg.repo, branch),
        current_contexts=tuple(current_contexts),
        desired_contexts=(ci.aggregate_context,),
        workflow_contexts=tuple(contexts),
    )


# --------------------------------------------------------------------------- #
# Execution (through the injected runner; dry-run default, idempotent apply).
# --------------------------------------------------------------------------- #
def _contexts_from_payload(payload: Any) -> Tuple[str, ...]:
    """
    Extract the required contexts from a ``required_status_checks`` GET payload.

    Prefers the modern ``checks`` array (``[{context, app_id}]``) and falls back to the
    legacy ``contexts`` list.
    """
    if not isinstance(payload, dict):
        return ()
    checks = payload.get("checks")
    if isinstance(checks, list):
        return tuple(
            c["context"] for c in checks if isinstance(c, dict) and c.get("context")
        )
    contexts = payload.get("contexts")
    if isinstance(contexts, list):
        return tuple(c for c in contexts if isinstance(c, str))
    return ()


def _get_current_contexts(
    runner: GhRunner, repo: str, branch: str
) -> Optional[Tuple[str, ...]]:
    """
    Read a branch's current required contexts; ``None`` when none are configured (404).

    A verified 404 means the required-status-checks sub-resource does not exist (branch
    protection off, or no required checks set). Any other failure is fail-aware: it raises
    :class:`~ghclient.errors.GhApiError` carrying the status rather than being read as
    "empty".
    """
    res = runner.api(required_checks_path(repo, branch), method="GET")
    if res.ok:
        return _contexts_from_payload(res.json())
    if res.status_code == 404:
        return None
    raise GhApiError(
        f"failed to read required status checks for {branch!r}",
        status_code=res.status_code,
        stderr=res.stderr,
    )


def _apply_plan(runner: GhRunner, plan: ReconcilePlan) -> None:
    """
    Issue the single ``PATCH`` that sets the required contexts to the aggregate.
    """
    body = {"checks": [{"context": ctx} for ctx in plan.desired_contexts]}
    res = runner.api(plan.api_path, method="PATCH", input_body=body)
    if not res.ok:
        raise GhApiError(
            f"failed to set required status checks on {plan.branch!r}",
            status_code=res.status_code,
            stderr=res.stderr,
        )


def _render(plan: ReconcilePlan, *, apply: bool) -> List[str]:
    """
    Render the human-readable preview of a plan (current vs desired + exact API call).
    """
    mode = "apply" if apply else "dry-run"
    declared = ", ".join(plan.workflow_contexts) or "(none)"
    current = ", ".join(plan.current_contexts) or "(none)"
    desired = ", ".join(plan.desired_contexts)
    lines = [
        f"[{plan.branch}] ci reconcile ({mode})",
        f"  workflows declare {len(plan.workflow_contexts)} check context(s): {declared}",
        f"  current required: [{current}]",
        f"  desired required: [{desired}]  (H2: always-emitting aggregate only)",
    ]
    if not plan.changed:
        lines.append("  NOOP: already reconciled")
        return lines
    lines.append(f'  CHANGE: PATCH {plan.api_path}  body={{"checks":[{{"context":"{desired}"}}]}}')
    if not apply:
        lines.append("  dry-run: nothing changed; re-run with --apply to mutate")
    return lines


def run_reconcile(
    runner: GhRunner,
    cfg: GithubClientConfig,
    *,
    branch: Optional[str] = None,
    apply: bool = False,
    workflows_root: Optional[Path] = None,
) -> Tuple[int, List[str]]:
    """
    Reconcile required checks to the aggregate context; dry-run unless ``apply``.

    Targets every configured branch whose ``required_checks_from_workflows`` is true (or
    the single ``branch`` when given). Returns ``(exit_code, lines)``; ``workflows_root``
    is injectable so tests resolve ``ci.workflows`` against a fixtures dir. Idempotent:
    a branch already set to the aggregate is reported as a NOOP and never mutated.
    """
    lines: List[str] = []
    try:
        ci = cfg.ci
        if ci is None or not ci.workflows:
            return 1, ["ci reconcile: FAIL: config has no 'ci.workflows'"]

        targets = [b for b in cfg.branch_protection.branches if b.required_checks_from_workflows]
        if branch is not None:
            targets = [b for b in targets if b.branch == branch]
            if not targets:
                return 1, [
                    f"ci reconcile: FAIL: {branch!r} is not a configured protected branch "
                    "with required_checks_from_workflows: true"
                ]
        if not targets:
            return 0, [
                "ci reconcile: no branches have required_checks_from_workflows: true; nothing to do"
            ]

        root = Path(workflows_root) if workflows_root is not None else cfg.repo_root
        workflow_texts: List[Tuple[str, str]] = []
        for wf in ci.workflows:
            path = root / wf
            if not path.is_file():
                raise ConfigError(ci.source, "ci.workflows", f"workflow file not found: {path}")
            workflow_texts.append((wf, path.read_text()))

        code = 0
        for target in targets:
            current = _get_current_contexts(runner, cfg.repo, target.branch)
            if current is None:
                code = 1
                lines.append(
                    f"[{target.branch}] FAIL: no required status checks configured "
                    "(branch protection off?); run `ghclient branch-protection apply --apply` first"
                )
                continue
            plan = build_reconcile_plan(
                cfg, workflow_texts, branch=target.branch, current_contexts=current
            )
            lines.extend(_render(plan, apply=apply))
            if plan.changed and apply:
                _apply_plan(runner, plan)
                lines.append(
                    f"[{target.branch}] applied: required checks now "
                    f"[{', '.join(plan.desired_contexts)}]"
                )
        return code, lines
    except GhClientError as exc:
        lines.append(f"ci reconcile: FAIL: {exc}")
        return 1, lines
