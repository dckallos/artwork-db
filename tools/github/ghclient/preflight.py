"""
preflight: verify the local environment before any GitHub operation.

Read-only and injectable -- the ``gh`` seam is passed in, so the whole check is
unit-testable offline. This is the *single* preflight implementation (A5): it reports
per-check status and the overall result is ``ok`` only when every required check passes.

Checks (A5): ``gh`` is authenticated; the config loads; and the authenticated identity
has **admin** permission on the target repo (branch-protection and required-status-check
updates require admin/owner). The obsolete ``jq`` check was removed -- snapshots are
formatted with ``json.dumps``, not ``jq``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .config import GithubClientConfig, load_config
from .errors import ConfigError


@dataclass(frozen=True)
class Check:
    """
    One preflight check: a name, pass/fail, and an actionable detail line.
    """

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    """
    The aggregate of every preflight :class:`Check`.
    """

    checks: Tuple[Check, ...]

    @property
    def ok(self) -> bool:
        """
        True only when every check passed.
        """
        return all(c.ok for c in self.checks)

    def render(self) -> str:
        """
        Human-readable, one line per check, with a final verdict.
        """
        lines = [f"[{'ok' if c.ok else 'FAIL'}] {c.name}: {c.detail}" for c in self.checks]
        lines.append("preflight: PASS" if self.ok else "preflight: FAIL")
        return "\n".join(lines)


def _admin_check(runner: Any, repo: str) -> Check:
    """
    Confirm the authenticated identity has ``admin`` permission on ``repo`` (A5).

    Branch-protection and required-status-check updates require admin/owner; a
    non-admin token would fail mid-apply, so we surface it up front and read-only.
    """
    res = runner.api(f"repos/{repo}")
    if not res.ok:
        return Check(
            "repo admin",
            False,
            f"could not read {repo} (HTTP {res.status_code}); need admin/owner access",
        )
    try:
        perms = (res.json() or {}).get("permissions") or {}
    except Exception:  # noqa: BLE001 - a malformed body is simply "unknown, fail safe"
        perms = {}
    admin = bool(perms.get("admin"))
    return Check(
        "repo admin",
        admin,
        "admin: true" if admin else f"insufficient permission on {repo}; branch protection requires admin",
    )


def preflight(runner: Any, config: Optional[GithubClientConfig]) -> PreflightReport:
    """
    Check ``gh`` auth, config validity, and repo admin permission.

    ``config`` is the already-loaded config (or ``None`` if loading failed, itself reported
    as a failed check). The admin check runs only when the config loaded and ``gh`` is
    authenticated, since it needs both a repo slug and a working credential.
    """
    checks: List[Check] = []

    auth = runner.run(["auth", "status"])
    checks.append(
        Check(
            name="gh auth",
            ok=bool(auth.ok),
            detail="authenticated" if auth.ok else "run `gh auth login` (not authenticated)",
        )
    )

    checks.append(
        Check(
            name="config",
            ok=config is not None,
            detail=(
                f"{config.repo} ({len(config.branch_protection.names())} protected branch(es))"
                if config is not None
                else "config failed to load (see the error above)"
            ),
        )
    )

    if config is not None and auth.ok:
        checks.append(_admin_check(runner, config.repo))

    return PreflightReport(checks=tuple(checks))


def run_preflight(runner: Any, *, config_path: Optional[Path] = None) -> Tuple[int, List[str]]:
    """
    Load the config and run :func:`preflight`, returning ``(exit_code, lines)``.

    A non-zero code means at least one check failed. A config that fails to load is
    reported as a failed ``config`` check (never a bare traceback).
    """
    try:
        config: Optional[GithubClientConfig] = load_config(config_path)
    except ConfigError:
        config = None
    report = preflight(runner, config)
    return (0 if report.ok else 1, report.render().splitlines())
