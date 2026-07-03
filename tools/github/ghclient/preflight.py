"""
preflight: verify the local environment before any GitHub operation.

Read-only and injectable -- the ``gh`` seam and the ``which`` lookup are passed
in, so the whole check is unit-testable offline. Reports per-check status; the
overall result is ``ok`` only when every required check passes.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple

from .config import GithubClientConfig


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


def preflight(
    runner: Any,
    config: Optional[GithubClientConfig],
    *,
    which: Callable[[str], Optional[str]] = shutil.which,
) -> PreflightReport:
    """
    Check ``gh`` auth, ``jq`` presence, and config validity.

    ``config`` is the already-loaded config (or ``None`` if loading failed, which
    is itself reported as a failed check). ``which`` is injected so tests can
    simulate a missing ``jq`` without touching the real ``PATH``.
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

    jq_path = which("jq")
    checks.append(
        Check(
            name="jq",
            ok=jq_path is not None,
            detail=jq_path or "not found on PATH (install jq)",
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

    return PreflightReport(checks=tuple(checks))
