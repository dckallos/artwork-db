"""
The ``ghclient`` command-line entrypoint: verb dispatch over the config + gh seam.

The user-facing surface is built with ``typer``, but ``typer`` is imported *defensively*
so that importing this module in a bare test process (or on a machine without typer
installed) never fails -- honoring the "import-safe" non-negotiable. The actual command
logic lives in small pure functions (``run_preflight`` etc.) that take an injected
:class:`~ghclient.gh.GhRunner`; the typer layer is a thin wrapper. Tests drive the pure
functions with a fake runner and never require typer to exercise behavior.

Mutation safety: every mutating verb is dry-run by default and prints the exact plan;
only an explicit ``--apply`` performs a change (plan §12.2.2). ``ghclient`` must never be
wired into CI with ``--apply``.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .config import load_config
from .errors import ConfigError, GhClientError
from .gh import GhRunner, SubprocessGhRunner

try:  # typer is a real dependency, but import-safety must not depend on it being present.
    import typer

    _HAS_TYPER = True
except ImportError:  # pragma: no cover - exercised only where typer is absent.
    typer = None  # type: ignore[assignment]
    _HAS_TYPER = False


# --------------------------------------------------------------------------- #
# Pure command implementations (no typer; injected runner; return (code, lines)).
# --------------------------------------------------------------------------- #
def run_preflight(
    runner: GhRunner,
    *,
    config_path: Optional[Path] = None,
    jq_present: Optional[bool] = None,
) -> Tuple[int, List[str]]:
    """
    Verify the client's preconditions: config validity, ``gh`` auth, and ``jq``.

    Returns ``(exit_code, lines)`` where a non-zero code means at least one check failed.
    ``jq_present`` is injectable so the check is deterministic in tests; when ``None`` it
    is probed from ``PATH``.
    """
    lines: List[str] = []
    ok = True

    try:
        cfg = load_config(config_path)
        lines.append(f"config: OK (repo={cfg.repo}, branches={cfg.branch_protection.names()})")
    except ConfigError as exc:
        ok = False
        lines.append(f"config: FAIL: {exc}")

    auth = runner.run(["auth", "status"])
    if auth.ok:
        lines.append("gh auth: OK")
    else:
        ok = False
        lines.append("gh auth: FAIL (run `gh auth login` as a repo admin)")

    has_jq = jq_present if jq_present is not None else shutil.which("jq") is not None
    if has_jq:
        lines.append("jq: OK")
    else:
        ok = False
        lines.append("jq: FAIL (install jq)")

    return (0 if ok else 1, lines)


# --------------------------------------------------------------------------- #
# typer wiring (thin). Built only when typer is importable.
# --------------------------------------------------------------------------- #
def _echo(lines: Sequence[str]) -> None:
    """
    Print result lines (typer.echo when available, else plain print).
    """
    for line in lines:
        if _HAS_TYPER:
            typer.echo(line)
        else:  # pragma: no cover
            print(line)


def build_app():  # noqa: ANN201 - returns a typer.Typer; annotated loosely to avoid a hard dep.
    """
    Construct and return the typer application. Requires typer to be installed.
    """
    if not _HAS_TYPER:  # pragma: no cover
        raise GhClientError("typer is not installed; run `pip install -e tools/github`")

    app = typer.Typer(
        add_completion=False,
        help="YAML-driven GitHub governance client for artwork-db.",
        no_args_is_help=True,
    )
    bp = typer.Typer(help="Classic branch-protection: apply / export / rollback (dry-run default).")
    app.add_typer(bp, name="branch-protection")

    @app.command()
    def preflight() -> None:
        """
        Verify gh auth, jq, and config validity.
        """
        code, lines = run_preflight(SubprocessGhRunner())
        _echo(lines)
        raise typer.Exit(code)

    @app.command()
    def audit(
        branch: Optional[str] = typer.Option(None, "--branch", help="Limit to one branch."),
    ) -> None:
        """
        Read classic protection + rulesets and report overlap (mutates nothing).
        """
        from . import branch_protection as _bp

        code, lines = _bp.run_audit(SubprocessGhRunner(), load_config(), branch=branch)
        _echo(lines)
        raise typer.Exit(code)

    @bp.command("apply")
    def bp_apply(
        branch: Optional[str] = typer.Option(None, "--branch", help="Limit to one branch."),
        apply: bool = typer.Option(False, "--apply", help="Perform the change (default: dry-run)."),
    ) -> None:
        """
        Apply the desired-state policy (dry-run unless --apply).
        """
        from . import branch_protection as _bp

        code, lines = _bp.run_apply(SubprocessGhRunner(), load_config(), branch=branch, apply=apply)
        _echo(lines)
        raise typer.Exit(code)

    @bp.command("export")
    def bp_export(
        branch: Optional[str] = typer.Option(None, "--branch", help="Limit to one branch."),
    ) -> None:
        """
        Snapshot current live protection to policies/exports/ (fail-closed, H1).
        """
        from . import branch_protection as _bp

        code, lines = _bp.run_export(SubprocessGhRunner(), load_config(), branch=branch)
        _echo(lines)
        raise typer.Exit(code)

    @bp.command("rollback")
    def bp_rollback(
        branch: Optional[str] = typer.Option(None, "--branch", help="Limit to one branch."),
        apply: bool = typer.Option(False, "--apply", help="Perform the change (default: dry-run)."),
    ) -> None:
        """
        Restore protection from the last snapshot (dry-run unless --apply).
        """
        from . import branch_protection as _bp

        code, lines = _bp.run_rollback(SubprocessGhRunner(), load_config(), branch=branch, apply=apply)
        _echo(lines)
        raise typer.Exit(code)

    return app


def main() -> None:
    """
    Console-script entrypoint (``ghclient``): build the typer app and run it.
    """
    if not _HAS_TYPER:  # pragma: no cover
        raise SystemExit("ghclient requires typer; install with `pip install -e tools/github`")
    build_app()()


app = build_app() if _HAS_TYPER else None
