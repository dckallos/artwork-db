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
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Tuple

from ._paths import quote_segment
from .config import BranchPolicyCfg, CiCfg, GithubClientConfig
from .errors import GhApiError, GhClientError
from .gh import GhResult, GhRunner

# Status-check contexts that must never appear on a protected branch: ``test`` is the
# legacy path-filtered job name that deadlocks docs-only PRs; the single source of truth
# for required checks is ``cfg.ci.aggregate_context`` (H1-X / feedback "A and C fight").
_FORBIDDEN_CONTEXTS: frozenset = frozenset({"test"})

# Snapshot envelope schema version (A2): a persisted snapshot is always a JSON *object*
# carrying provenance + a PUT-ready restore body. A bare ``null`` file is refused, so a
# hand-written ``echo null`` can never become delete-eligible.
_SNAPSHOT_SCHEMA = 1


def _protection_path(repo: str, branch: str) -> str:
    """
    REST path for a branch's classic protection (branch percent-encoded, A4).
    """
    return f"repos/{repo}/branches/{quote_segment(branch)}/protection"


def _snapshot_filename(branch: str) -> str:
    """
    Filesystem-safe snapshot filename for ``branch`` (``/`` encoded, so ``release/x`` is
    one file, not a nested directory) -- A4.
    """
    return f"{quote_segment(branch)}.json"


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
class ProtectionSnapshot:
    """
    A persisted before-state envelope (A1/A2): provenance + a PUT-ready restore body.

    ``live_response`` is the raw ``GET .../protection`` payload (kept for audit only);
    ``restore_body`` is the normalized body that :func:`plan_rollback` PUTs -- a GET
    response is *not* a valid PUT payload (it carries ``url`` fields and ``{"enabled":
    ...}`` wrappers), so rollback must never replay it verbatim. ``source == "verified-404"``
    (with ``restore_body is None``) is the only delete-eligible state, and it can only be
    produced by :func:`export_snapshot`'s verified 404 -- never by a hand-written file.
    """

    schema_version: int
    repo: str
    branch: str
    captured_at: str
    source: str  # "live" | "verified-404"
    live_response: Optional[dict]
    restore_body: Optional[dict]

    @property
    def is_null(self) -> bool:
        """
        True when the branch had no protection at capture time (verified 404).
        """
        return self.restore_body is None and self.source == "verified-404"

    def to_json(self) -> dict:
        """
        The on-disk envelope object (never a bare ``null``).
        """
        return {
            "schema_version": self.schema_version,
            "repo": self.repo,
            "branch": self.branch,
            "captured_at": self.captured_at,
            "source": self.source,
            "live_response": self.live_response,
            "restore_body": self.restore_body,
        }


# GET returns these as ``{"enabled": bool, "url": ...}``; PUT wants a bare boolean.
_ENABLED_FLAG_KEYS: Tuple[str, ...] = (
    "enforce_admins",
    "required_linear_history",
    "allow_force_pushes",
    "allow_deletions",
    "required_conversation_resolution",
    "block_creations",
    "required_signatures",
    "lock_branch",
    "allow_fork_syncing",
)


def _flag(value: Any) -> Optional[bool]:
    """
    Normalize a GET flag (``bool`` or ``{"enabled": bool}``) to a PUT boolean.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, dict) and isinstance(value.get("enabled"), bool):
        return value["enabled"]
    return None


def _contexts_from_required_status_checks(rsc: Any) -> List[str]:
    """
    Extract status-check context names from a protection payload.

    GitHub may expose required checks either as the legacy ``contexts`` list or as
    modern ``checks`` objects.  The full ``PUT .../protection`` endpoint is stricter
    than the status-check subresource, so full branch-protection bodies use a
    contexts-only shape and leave app-specific ``checks`` writes to
    ``ci reconcile``'s ``PATCH .../required_status_checks`` path.
    """
    if not isinstance(rsc, dict):
        return []
    contexts: List[str] = [c for c in (rsc.get("contexts") or []) if isinstance(c, str)]
    for check in rsc.get("checks") or []:
        if isinstance(check, dict) and isinstance(check.get("context"), str):
            contexts.append(check["context"])
    # Preserve first-seen order while avoiding duplicate contexts.
    return list(dict.fromkeys(contexts))


def _normalize_required_status_checks(rsc: Any) -> Optional[dict]:
    """
    Reduce a GET ``required_status_checks`` object to the full branch-protection
    ``PUT`` shape.

    Deliberately contexts-only: the full update endpoint rejects payloads that include
    both ``contexts`` and ``checks``.  The ``checks``/``app_id`` form remains isolated to
    the required-status-checks subresource PATCH in :mod:`ghclient.ci`.
    """
    if not isinstance(rsc, dict):
        return None
    return {
        "strict": bool(rsc.get("strict", True)),
        "contexts": _contexts_from_required_status_checks(rsc),
    }


def _normalize_pr_reviews(reviews: Any) -> Optional[dict]:
    """
    Keep only the PUT-valid keys of a GET ``required_pull_request_reviews`` object.
    """
    if not isinstance(reviews, dict):
        return None
    allowed = (
        "dismiss_stale_reviews",
        "require_code_owner_reviews",
        "required_approving_review_count",
        "require_last_push_approval",
    )
    out = {k: reviews[k] for k in allowed if k in reviews}
    dr = reviews.get("dismissal_restrictions")
    if isinstance(dr, dict):
        out["dismissal_restrictions"] = {
            "users": [u["login"] for u in dr.get("users", []) if isinstance(u, dict) and u.get("login")],
            "teams": [t["slug"] for t in dr.get("teams", []) if isinstance(t, dict) and t.get("slug")],
        }
    return out


def _normalize_restrictions(restrictions: Any) -> Optional[dict]:
    """
    Reduce a GET ``restrictions`` object to the PUT shape (login/slug lists) or ``None``.
    """
    if not isinstance(restrictions, dict):
        return None
    return {
        "users": [u["login"] for u in restrictions.get("users", []) if isinstance(u, dict) and u.get("login")],
        "teams": [t["slug"] for t in restrictions.get("teams", []) if isinstance(t, dict) and t.get("slug")],
        "apps": [a["slug"] for a in restrictions.get("apps", []) if isinstance(a, dict) and a.get("slug")],
    }


def normalize_to_put_body(live: dict) -> dict:
    """
    Convert a ``GET .../protection`` response into a valid ``PUT`` restore body (A1).

    GitHub's protection GET returns response-only shapes -- ``url`` fields and
    ``{"enabled": ...}`` wrappers -- that the update endpoint rejects. This maps them to
    the PUT schema: the four required keys (``required_status_checks``,
    ``enforce_admins``, ``required_pull_request_reviews``, ``restrictions``) are always
    present (``None`` when absent), and the optional ``{"enabled"}`` flags are flattened
    to booleans only when the GET carried them.
    """
    body: dict = {
        "required_status_checks": _normalize_required_status_checks(live.get("required_status_checks")),
        "enforce_admins": bool(_flag(live.get("enforce_admins"))),
        "required_pull_request_reviews": _normalize_pr_reviews(live.get("required_pull_request_reviews")),
        "restrictions": _normalize_restrictions(live.get("restrictions")),
    }
    for key in _ENABLED_FLAG_KEYS:
        if key == "enforce_admins":
            continue
        flag = _flag(live.get(key))
        if flag is not None:
            body[key] = flag
    return body


def build_snapshot(repo: str, snapshot: Snapshot) -> ProtectionSnapshot:
    """
    Wrap a captured :class:`Snapshot` in a persisted :class:`ProtectionSnapshot` envelope.

    A verified-404 capture yields ``restore_body=None`` (delete-eligible); a live capture
    stores the raw response for audit and a normalized, PUT-ready ``restore_body`` (A1).
    """
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if snapshot.is_null:
        return ProtectionSnapshot(
            schema_version=_SNAPSHOT_SCHEMA,
            repo=repo,
            branch=snapshot.branch,
            captured_at=captured_at,
            source="verified-404",
            live_response=None,
            restore_body=None,
        )
    return ProtectionSnapshot(
        schema_version=_SNAPSHOT_SCHEMA,
        repo=repo,
        branch=snapshot.branch,
        captured_at=captured_at,
        source="live",
        live_response=snapshot.body,
        restore_body=normalize_to_put_body(snapshot.body or {}),
    )


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


def _require_ci(cfg: GithubClientConfig, branch: str) -> CiCfg:
    """
    Return the typed ``ci`` config or raise: a branch that derives required checks from
    workflows needs an aggregate context to derive them *to*.
    """
    if cfg.ci is None:
        raise GhClientError(
            f"branch {branch!r} sets required_checks_from_workflows: true but the config "
            "has no 'ci:' block; add ci.aggregate_context (single source of truth for the "
            "required check)."
        )
    return cfg.ci


def _reject_forbidden_contexts(body: dict, branch: str) -> None:
    """
    Refuse a policy whose required status checks name a forbidden context (e.g. ``test``).

    Guards against a hand-edited policy re-introducing the path-filtered check that
    deadlocks docs-only PRs -- the derived aggregate is the only permitted required check.
    """
    rsc = body.get("required_status_checks")
    if not isinstance(rsc, dict):
        return
    present = {c for c in (rsc.get("contexts") or []) if isinstance(c, str)}
    present |= {
        c.get("context")
        for c in (rsc.get("checks") or [])
        if isinstance(c, dict) and c.get("context")
    }
    bad = sorted(present & _FORBIDDEN_CONTEXTS)
    if bad:
        raise GhClientError(
            f"policy for {branch!r} names forbidden required check(s) {bad}; the required "
            "check is derived from ci.aggregate_context (remove the hardcoded context)."
        )


def policy_body_for_apply(cfg: GithubClientConfig, policy: BranchPolicyCfg) -> dict:
    """
    Build the PUT body for a branch, deriving required checks from ci config (H1-X / C4).

    When ``required_checks_from_workflows`` is set, ``required_status_checks`` is generated
    from ``cfg.ci.aggregate_context`` -- the single source of truth -- as a full-branch-
    protection ``PUT`` compatible, contexts-only object:
    ``{"strict": <policy strict or True>, "contexts": [<aggregate>]}``.

    The modern ``checks``/``app_id`` form is valid for the required-status-checks
    subresource PATCH handled by :mod:`ghclient.ci`; keeping the two shapes separate
    avoids GitHub's full ``PUT`` schema rejecting a mixed ``checks`` + ``contexts`` body.
    A forbidden context (e.g. a leftover ``test``) is rejected either way.
    """
    body = load_policy_body(policy.policy_path)
    if policy.required_checks_from_workflows:
        ci = _require_ci(cfg, policy.branch)
        existing = body.get("required_status_checks")
        strict = existing.get("strict", True) if isinstance(existing, dict) else True
        body["required_status_checks"] = {
            "strict": bool(strict),
            "contexts": [ci.aggregate_context],
        }
    _reject_forbidden_contexts(body, policy.branch)
    return body


def plan_apply(cfg: GithubClientConfig, policy: BranchPolicyCfg) -> ProtectionAction:
    """
    Build the PUT plan that makes ``policy.branch`` match its desired-state body.

    Idempotent by construction: ``PUT .../protection`` replaces the whole config, so
    re-applying converges to the committed policy. Required checks are derived from
    ``cfg.ci.aggregate_context`` when the branch opts in (H1-X), so the policy JSON and
    ``ci reconcile`` never fight over the required check.
    """
    body = policy_body_for_apply(cfg, policy)
    return ProtectionAction(
        kind=ActionKind.PUT,
        repo=cfg.repo,
        branch=policy.branch,
        reason=f"apply desired-state policy {policy.policy_path.name}",
        body=body,
    )


def plan_rollback(repo: str, snapshot: ProtectionSnapshot) -> ProtectionAction:
    """
    Build the plan that restores ``snapshot`` (the captured before-state envelope).

    A verified-404 envelope (``restore_body is None``) -> DELETE protection; a captured
    envelope -> PUT its **normalized** ``restore_body`` (never the raw GET response, which
    is not a valid PUT payload -- A1). H1/A2: only a strictly validated
    ``source == "verified-404"`` envelope is delete-eligible, so a legacy bare-null,
    mismatched, or internally inconsistent snapshot can never delete protection.
    """
    if snapshot.schema_version != _SNAPSHOT_SCHEMA:
        raise GhClientError(
            f"snapshot for {snapshot.branch} has unsupported schema_version "
            f"{snapshot.schema_version!r}; refusing to roll back."
        )
    if snapshot.repo != repo:
        raise GhClientError(
            f"snapshot for {snapshot.branch} was captured for repo {snapshot.repo!r}, "
            f"not {repo!r}; refusing to roll back."
        )
    if snapshot.is_null:
        if snapshot.source != "verified-404":
            raise GhClientError(
                f"refusing to DELETE protection on {snapshot.branch}: null "
                f"snapshot has untrusted provenance {snapshot.source!r} (H1/A2)."
            )
        return ProtectionAction(
            kind=ActionKind.DELETE,
            repo=repo,
            branch=snapshot.branch,
            reason="restore unprotected before-state (verified 404)",
        )
    if snapshot.source != "live" or snapshot.restore_body is None:
        raise GhClientError(
            f"refusing to roll back {snapshot.branch}: snapshot has no trusted restore_body "
            f"for source {snapshot.source!r} (A2)."
        )
    return ProtectionAction(
        kind=ActionKind.PUT,
        repo=repo,
        branch=snapshot.branch,
        reason="restore saved protection from snapshot (normalized PUT body)",
        body=snapshot.restore_body,
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


def write_snapshot(snapshot: ProtectionSnapshot, exports_dir: Path) -> Path:
    """
    Persist a :class:`ProtectionSnapshot` envelope to ``exports/<branch>.json``.

    Always a JSON object (schema-versioned) -- never a bare ``null`` -- so provenance
    travels with the file and a hand-written ``null`` is not delete-eligible (A2).
    """
    exports_dir.mkdir(parents=True, exist_ok=True)
    out = exports_dir / _snapshot_filename(snapshot.branch)
    out.write_text(json.dumps(snapshot.to_json(), indent=2, sort_keys=True) + "\n")
    return out


def _parse_captured_at(value: Any, *, path_name: str) -> str:
    """
    Validate and return the snapshot capture timestamp.
    """
    if not isinstance(value, str) or not value:
        raise GhClientError(f"corrupt snapshot {path_name}: missing captured_at; refusing to roll back.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GhClientError(
            f"corrupt snapshot {path_name}: invalid captured_at {value!r}; refusing to roll back."
        ) from exc
    return value


def _dict_or_none(value: Any, *, field_name: str, path_name: str) -> Optional[dict]:
    """
    Validate optional object fields from a snapshot envelope.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise GhClientError(
            f"corrupt snapshot {path_name}: {field_name} must be an object or null; refusing to roll back."
        )
    return value


def read_snapshot(path: Path, branch: str) -> ProtectionSnapshot:
    """
    Load a persisted :class:`ProtectionSnapshot` envelope, refusing a corrupt/legacy one.

    A bare ``null`` (legacy or hand-written) is **refused** -- delete-eligibility requires
    a schema-versioned envelope whose ``source`` is ``"verified-404"`` (A2). A non-object
    or unparseable file is refused (corrupt-snapshot rollback refusal, H5).
    """
    if not path.exists():
        raise GhClientError(
            f"no snapshot for {branch} at {path}; run `ghclient branch-protection "
            "export` first."
        )
    text = path.read_text().strip()
    if text == "null":
        raise GhClientError(
            f"refusing bare-null snapshot {path.name}: legacy/untrusted provenance; "
            "re-export to produce a schema-versioned envelope (A2)."
        )
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GhClientError(
            f"corrupt snapshot {path.name}: not valid JSON; refusing to roll back."
        ) from exc
    if not isinstance(data, dict) or "schema_version" not in data:
        raise GhClientError(
            f"corrupt snapshot {path.name}: expected a schema-versioned envelope; "
            "refusing to roll back."
        )
    schema_version = data.get("schema_version")
    if type(schema_version) is not int or schema_version != _SNAPSHOT_SCHEMA:
        raise GhClientError(
            f"corrupt snapshot {path.name}: unsupported schema_version {schema_version!r}; "
            f"expected {_SNAPSHOT_SCHEMA}; refusing to roll back."
        )
    repo = data.get("repo")
    if not isinstance(repo, str) or not repo:
        raise GhClientError(f"corrupt snapshot {path.name}: missing repo; refusing to roll back.")
    snap_branch = data.get("branch")
    if snap_branch != branch:
        raise GhClientError(
            f"corrupt snapshot {path.name}: branch mismatch {snap_branch!r} != {branch!r}; "
            "refusing to roll back."
        )
    captured_at = _parse_captured_at(data.get("captured_at"), path_name=path.name)
    source = data.get("source")
    if source not in ("live", "verified-404"):
        raise GhClientError(
            f"corrupt snapshot {path.name}: unknown source {source!r}; refusing to roll back."
        )
    live_response = _dict_or_none(data.get("live_response"), field_name="live_response", path_name=path.name)
    restore_body = _dict_or_none(data.get("restore_body"), field_name="restore_body", path_name=path.name)
    if source == "verified-404" and (live_response is not None or restore_body is not None):
        raise GhClientError(
            f"corrupt snapshot {path.name}: verified-404 envelopes must not carry live_response "
            "or restore_body; refusing to roll back."
        )
    if source == "live" and (live_response is None or restore_body is None):
        raise GhClientError(
            f"corrupt snapshot {path.name}: live envelopes require both live_response and "
            "restore_body; refusing to roll back."
        )
    return ProtectionSnapshot(
        schema_version=schema_version,
        repo=repo,
        branch=snap_branch,
        captured_at=captured_at,
        source=source,
        live_response=live_response,
        restore_body=restore_body,
    )


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
    List ruleset-sourced rules that apply to ``branch`` -- fail-closed on ANY error (A3).

    GitHub's ``GET /repos/{repo}/rules/branches/{branch}`` returns ``200`` with all active
    rules -- even for a branch that does not exist -- so a ``404`` here is anomalous
    (endpoint/auth/repo ambiguity), never proof of "no rules." We therefore fail closed on
    a 404 too, so a ruleset overlap is never silently missed before a classic mutation.
    """
    res: GhResult = runner.api(f"repos/{repo}/rules/branches/{quote_segment(branch)}", method="GET")
    if res.ok:
        data = json.loads(res.stdout or "[]")
        return list(data) if isinstance(data, list) else []
    raise GhApiError(
        f"audit {repo}@{branch}: listing branch rules failed (HTTP "
        f"{res.status_code}); failing closed (a 404 here is not 'no rules', A3).",
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
    runner: GhRunner,
    cfg: GithubClientConfig,
    *,
    branch: Optional[str] = None,
    apply: bool = False,
    allow_ruleset_overlap: bool = False,
) -> Tuple[int, List[str]]:
    """
    Preview (default) or ``--apply`` the desired-state policy for the selected branches.

    Ruleset-aware (A3): each branch is audited first (classic protection + active
    rulesets/branch rules, fail-closed). An overlap is always warned about; on ``--apply``
    it BLOCKS the mutation unless ``allow_ruleset_overlap`` is set, so classic protection
    never silently fights a ruleset. The audit's classic capture doubles as the H1
    before-state snapshot (no second GET). Idempotent: re-applying converges.
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            report = audit(runner, cfg.repo, policy.branch)  # A3: read-only audit-first
            action = plan_apply(cfg, policy)
            lines.append(action.render())
            if report.has_ruleset_overlap:
                kinds = sorted({str(r.get("type", "?")) for r in report.branch_rules})
                lines.append(
                    f"  WARNING: {len(report.branch_rules)} ruleset rule(s) also govern "
                    f"{policy.branch} (types: {kinds}); a classic PUT may fight them (A3)."
                )
                if apply and not allow_ruleset_overlap:
                    code = 1
                    lines.append(
                        f"  BLOCKED: refusing to --apply over a ruleset overlap on "
                        f"{policy.branch}; re-run with --allow-ruleset-overlap to override (A3)."
                    )
                    continue
            if apply:
                out = write_snapshot(build_snapshot(cfg.repo, report.classic), cfg.exports_dir)
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

    A verified 404 writes a schema-versioned ``verified-404`` envelope; any other
    failure writes nothing and yields a non-zero exit so a transport error is never
    mistaken for "no rules."
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
            out = write_snapshot(build_snapshot(cfg.repo, snapshot), cfg.exports_dir)
            state = "no protection (verified 404)" if snapshot.is_null else "protection present"
            lines.append(f"exported {policy.branch}: {state} -> {out}")
        except GhClientError as exc:
            code = 1
            lines.append(
                f"export {policy.branch}: FAILED (fail-closed, no snapshot written): {exc}"
            )
    return (code, lines)


def run_rollback(
    runner: GhRunner,
    cfg: GithubClientConfig,
    *,
    branch: Optional[str] = None,
    apply: bool = False,
    allow_ruleset_overlap: bool = False,
) -> Tuple[int, List[str]]:
    """
    Preview (default) or ``--apply`` a restore from the last exported snapshot.

    A ``verified-404`` snapshot DELETEs protection; a saved body PUT-restores it. A corrupt
    or untrusted snapshot is refused (H1/H5). Rollback is also a classic-protection mutation,
    so it inventories rulesets before applying and blocks over overlap unless explicitly
    overridden (H9).
    """
    try:
        policies = _selected_policies(cfg, branch)
    except GhClientError as exc:
        return (1, [str(exc)])
    lines: List[str] = []
    code = 0
    for policy in policies:
        try:
            snapshot = read_snapshot(cfg.exports_dir / _snapshot_filename(policy.branch), policy.branch)
            action = plan_rollback(cfg.repo, snapshot)
            report = audit(runner, cfg.repo, policy.branch)
            lines.append(action.render())
            if report.has_ruleset_overlap:
                kinds = sorted({str(r.get("type", "?")) for r in report.branch_rules})
                lines.append(
                    f"  WARNING: {len(report.branch_rules)} ruleset rule(s) also govern "
                    f"{policy.branch} (types: {kinds}); a classic rollback may fight them (A3)."
                )
                if apply and not allow_ruleset_overlap:
                    code = 1
                    lines.append(
                        f"  BLOCKED: refusing to --apply rollback over a ruleset overlap on "
                        f"{policy.branch}; re-run with --allow-ruleset-overlap to override (A3)."
                    )
                    continue
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
