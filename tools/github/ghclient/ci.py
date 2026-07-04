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

from ._paths import quote_segment
from .config import CiCfg, GithubClientConfig
from .errors import ConfigError, GhApiError, GhClientError
from .gh import GhRunner

__all__ = [
    "ReconcilePlan",
    "build_reconcile_plan",
    "declared_context_names",
    "job_check_contexts",
    "run_reconcile",
    "validate_aggregate_workflow",
]


def required_checks_path(repo: str, branch: str) -> str:
    """
    The REST path for a branch's required-status-checks sub-resource (branch encoded, A4).
    """
    return f"repos/{repo}/branches/{quote_segment(branch)}/protection/required_status_checks"


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


def _workflow_on(top: dict) -> Any:
    """
    Return a workflow's trigger section, tolerating PyYAML parsing bare ``on:`` as ``True``.

    Under YAML 1.1 an unquoted ``on`` key loads as the boolean ``True``; GitHub Actions
    files rely on it, so read both spellings (C3).
    """
    if "on" in top:
        return top["on"]
    return top.get(True)


def validate_aggregate_workflow(text: str, *, source: str, aggregate_context: str) -> None:
    """
    Validate that ``source`` makes ``aggregate_context`` an *always-emitting* PR gate (C3).

    A workflow can declare the aggregate job yet still never report it -- if it is not
    triggered on ``pull_request``, is path-filtered (so some PRs skip it, leaving the
    required check Pending forever), or if the aggregate job lacks ``if: always()`` or does
    not ``needs`` every sibling. Each failure raises a file/field-scoped
    :class:`~ghclient.errors.ConfigError`.
    """
    top = _load_workflow(text, source)
    on_section = _workflow_on(top)

    pr_present = False
    pr_cfg: Any = None
    if isinstance(on_section, dict) and "pull_request" in on_section:
        pr_present, pr_cfg = True, on_section["pull_request"]
    elif on_section == "pull_request":
        pr_present = True
    elif isinstance(on_section, list) and "pull_request" in on_section:
        pr_present = True
    if not pr_present:
        raise ConfigError(
            source, "on.pull_request",
            f"aggregate workflow must trigger on pull_request so {aggregate_context!r} emits for every PR",
        )
    if isinstance(pr_cfg, dict) and (pr_cfg.get("paths") or pr_cfg.get("paths-ignore")):
        raise ConfigError(
            source, "on.pull_request.paths",
            f"aggregate workflow must not path-filter pull_request (a filtered PR leaves "
            f"{aggregate_context!r} Pending forever)",
        )

    jobs = _jobs(text, source)
    agg_id = None
    agg_def: Any = None
    for job_id, job_def in jobs.items():
        if job_id == aggregate_context or (isinstance(job_def, dict) and job_def.get("name") == aggregate_context):
            agg_id, agg_def = job_id, job_def
            break
    if agg_id is None:
        raise ConfigError(
            source, "ci.aggregate_context",
            f"{aggregate_context!r} is not a job in {source}",
        )
    if not isinstance(agg_def, dict):
        raise ConfigError(source, f"jobs.{agg_id}", "aggregate job is not a mapping")
    if "always()" not in str(agg_def.get("if", "")):
        raise ConfigError(
            source, f"jobs.{agg_id}.if",
            f"aggregate job {aggregate_context!r} must set `if: always()` so it reports even "
            "when a dependency is skipped or failed",
        )
    needs = agg_def.get("needs")
    needs_set = {needs} if isinstance(needs, str) else set(needs or [])
    # Advisory jobs (continue-on-error: true) are deliberately NOT part of the gate, so the
    # aggregate need not depend on them; every other (gating) job must be a dependency (C3).
    gating = {
        jid
        for jid, jdef in jobs.items()
        if jid != agg_id and not (isinstance(jdef, dict) and jdef.get("continue-on-error") is True)
    }
    missing = sorted(gating - needs_set)
    if missing:
        raise ConfigError(
            source, f"jobs.{agg_id}.needs",
            f"aggregate job must `needs` every gating job so the gate reflects them "
            f"(advisory continue-on-error jobs excluded); missing: {missing}",
        )


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
    strict: bool = True

    @property
    def changed(self) -> bool:
        """
        True when the current required contexts differ from the desired set.
        """
        return sorted(self.current_contexts) != sorted(self.desired_contexts)


def _select_aggregate_workflow(ci: CiCfg, declared_by_source: dict) -> str:
    """
    Return the single workflow source that emits ``ci.aggregate_context`` (C2).

    Honours an explicit ``ci.aggregate_workflow`` -- validating the aggregate job is actually
    declared there -- otherwise finds the sole configured workflow that declares it.
    Informational workflows never emit the gate, so their jobs must not be presented as
    feeding it. Raises a scoped :class:`ConfigError` when no configured workflow can emit the
    aggregate.
    """
    if ci.aggregate_workflow is not None:
        if ci.aggregate_context not in declared_by_source.get(ci.aggregate_workflow, set()):
            raise ConfigError(
                ci.source,
                "ci.aggregate_workflow",
                f"{ci.aggregate_context!r} is not a job in the configured aggregate workflow "
                f"{ci.aggregate_workflow!r}",
            )
        return ci.aggregate_workflow

    matches = [src for src, names in declared_by_source.items() if ci.aggregate_context in names]
    if not matches:
        all_declared = sorted(set().union(*declared_by_source.values())) if declared_by_source else []
        raise ConfigError(
            ci.source,
            "ci.aggregate_context",
            f"{ci.aggregate_context!r} is not a job in any configured workflow; "
            f"declared jobs: {all_declared}",
        )
    return matches[0]


def build_reconcile_plan(
    cfg: GithubClientConfig,
    workflow_texts: Sequence[Tuple[str, str]],
    *,
    branch: str,
    current_contexts: Sequence[str],
    strict: bool = True,
) -> ReconcilePlan:
    """
    Build the reconcile plan: validate the aggregate exists, desire exactly that context.

    ``workflow_texts`` is a sequence of ``(source, text)`` pairs. ``strict`` is the branch's
    current ``strict`` (require-up-to-date) setting, carried through to the PATCH so the
    reconcile never silently flips it (C4). Raises a scoped :class:`ConfigError` if the
    config has no ``ci`` block or if the configured ``aggregate_context`` is not a job in
    the emitting workflow (which would set an unsatisfiable required check). The preview's
    ``workflow_contexts`` reflects only the aggregate-emitting workflow's jobs -- never the
    jobs of merely *informational* workflows, which do not feed the gate (C2).
    """
    ci = cfg.ci
    if ci is None:
        raise ConfigError(str(cfg.config_path), "ci", "no ci block configured")

    # Parse-validate every configured workflow (informational ones included, so malformed
    # or job-less YAML is still caught here), recording each one's declared jobs + contexts.
    declared_by_source: dict = {}
    contexts_by_source: dict = {}
    for source, text in workflow_texts:
        declared_by_source[source] = declared_context_names(text, source=source)
        contexts_by_source[source] = job_check_contexts(text, source=source)

    emitter = _select_aggregate_workflow(ci, declared_by_source)

    return ReconcilePlan(
        repo=cfg.repo,
        branch=branch,
        api_path=required_checks_path(cfg.repo, branch),
        current_contexts=tuple(current_contexts),
        desired_contexts=(ci.aggregate_context,),
        workflow_contexts=tuple(contexts_by_source[emitter]),
        strict=strict,
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


def _strict_from_payload(payload: Any) -> bool:
    """
    Extract ``strict`` (require branches up to date) from a GET payload, defaulting True.
    """
    if isinstance(payload, dict) and isinstance(payload.get("strict"), bool):
        return payload["strict"]
    return True


def _get_current_state(
    runner: GhRunner, repo: str, branch: str
) -> Optional[Tuple[Tuple[str, ...], bool]]:
    """
    Read a branch's current required ``(contexts, strict)``; ``None`` when none (404).

    A verified 404 means the required-status-checks sub-resource does not exist (branch
    protection off, or no required checks set). Any other failure is fail-aware: it raises
    :class:`~ghclient.errors.GhApiError` carrying the status rather than being read as
    "empty". ``strict`` is carried so the PATCH never silently flips it (C4).
    """
    res = runner.api(required_checks_path(repo, branch), method="GET")
    if res.ok:
        payload = res.json()
        return _contexts_from_payload(payload), _strict_from_payload(payload)
    if res.status_code == 404:
        return None
    raise GhApiError(
        f"failed to read required status checks for {branch!r}",
        status_code=res.status_code,
        stderr=res.stderr,
    )


def _apply_plan(runner: GhRunner, plan: ReconcilePlan) -> None:
    """
    Issue the single ``PATCH`` that sets the required checks to the aggregate.

    Uses the modern ``checks`` array with ``app_id: -1`` (any app may report the status),
    carries ``strict`` through unchanged, and clears the legacy ``contexts`` list (C4).
    """
    body = {
        "strict": plan.strict,
        "checks": [{"context": ctx, "app_id": -1} for ctx in plan.desired_contexts],
        "contexts": [],
    }
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
    lines.append(
        f'  CHANGE: PATCH {plan.api_path}  '
        f'body={{"strict":{str(plan.strict).lower()},'
        f'"checks":[{{"context":"{desired}","app_id":-1}}],"contexts":[]}}'
    )
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

        # C3: the workflow that emits the aggregate must make it an always-emitting PR gate
        # (triggered on pull_request, no path filter, if: always(), complete needs) -- else
        # the required check can sit Pending and deadlock merges. C2: the emitter is the
        # configured aggregate_workflow when set, otherwise the sole workflow declaring it.
        aggregate_wf = _select_aggregate_workflow(
            ci, {s: declared_context_names(t, source=s) for s, t in workflow_texts}
        )
        agg_text = next(t for s, t in workflow_texts if s == aggregate_wf)
        validate_aggregate_workflow(agg_text, source=aggregate_wf, aggregate_context=ci.aggregate_context)

        code = 0
        for target in targets:
            state = _get_current_state(runner, cfg.repo, target.branch)
            if state is None:
                code = 1
                lines.append(
                    f"[{target.branch}] FAIL: no required status checks configured "
                    "(branch protection off?); run `ghclient branch-protection apply --apply` first"
                )
                continue
            current, strict = state
            plan = build_reconcile_plan(
                cfg, workflow_texts, branch=target.branch, current_contexts=current, strict=strict
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
