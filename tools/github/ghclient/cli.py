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

from typing import List, Optional, Sequence

from .config import load_config
from .errors import GhClientError
from .gh import SubprocessGhRunner

try:  # typer is a real dependency, but import-safety must not depend on it being present.
    import typer

    _HAS_TYPER = True
except ImportError:  # pragma: no cover - exercised only where typer is absent.
    typer = None  # type: ignore[assignment]
    _HAS_TYPER = False


# --------------------------------------------------------------------------- #
# typer wiring (thin). Built only when typer is importable.
# The pure command implementations live in their modules (``preflight``, ``ci``,
# ``branch_protection``, ``secrets``); each takes an injected :class:`GhRunner` and
# returns ``(code, lines)``. Tests drive those directly, never through typer.
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
    ci_app = typer.Typer(help="CI governance: reconcile required checks to the aggregate (dry-run default).")
    app.add_typer(ci_app, name="ci")
    secrets_app = typer.Typer(
        help="Publish dbt Snowflake credentials to GitHub Environment secrets/variables (dry-run default)."
    )
    app.add_typer(secrets_app, name="secrets")

    @app.command()
    def preflight() -> None:
        """
        Verify gh auth, config validity, and repo admin permission.
        """
        from .preflight import run_preflight

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
        allow_ruleset_overlap: bool = typer.Option(
            False,
            "--allow-ruleset-overlap",
            help="Proceed even when a repo/org ruleset also governs the branch (A3).",
        ),
    ) -> None:
        """
        Apply the desired-state policy (dry-run unless --apply).
        """
        from . import branch_protection as _bp

        code, lines = _bp.run_apply(
            SubprocessGhRunner(),
            load_config(),
            branch=branch,
            apply=apply,
            allow_ruleset_overlap=allow_ruleset_overlap,
        )
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

    @ci_app.command("reconcile")
    def ci_reconcile(
        branch: Optional[str] = typer.Option(None, "--branch", help="Limit to one branch."),
        apply: bool = typer.Option(False, "--apply", help="Perform the change (default: dry-run)."),
    ) -> None:
        """
        Reconcile required checks to the aggregate ci-required context (dry-run unless --apply).
        """
        from . import ci as _ci

        code, lines = _ci.run_reconcile(SubprocessGhRunner(), load_config(), branch=branch, apply=apply)
        _echo(lines)
        raise typer.Exit(code)

    @secrets_app.command("publish")
    def secrets_publish(
        profile_set: str = typer.Option(
            ..., "--profile-set", "--profile", help="Config publish set (snowflake_secrets.profiles.<name>)."
        ),
        env: Optional[str] = typer.Option(None, "--env", help="Override the target GitHub Environment name."),
        apply: bool = typer.Option(False, "--apply", help="Perform the change (default: dry-run)."),
        no_overwrite: bool = typer.Option(
            True, "--no-overwrite/--overwrite", help="Never clobber existing items (default); --force overrides."
        ),
        force: bool = typer.Option(False, "--force", help="Update items that already exist."),
        delete_missing: bool = typer.Option(
            False, "--delete-missing", help="Delete managed items absent from the mapping."
        ),
        allow_role: List[str] = typer.Option(
            [], "--allow-role", help="Explicitly permit a role, overriding the H3 allowlist (repeatable)."
        ),
    ) -> None:
        """
        Publish mapped connection fields to a GitHub Environment (dry-run unless --apply).
        """
        import getpass

        from . import secrets as _secrets

        code, lines = _secrets.run_publish(
            SubprocessGhRunner(),
            load_config(),
            profile_set=profile_set,
            env=env,
            apply=apply,
            no_overwrite=no_overwrite,
            force=force,
            delete_missing=delete_missing,
            allow_roles=tuple(allow_role),
            local_user=getpass.getuser(),
        )
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
