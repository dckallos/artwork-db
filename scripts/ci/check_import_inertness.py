#!/usr/bin/env python3
"""
Import-inertness gate for the ingestion platform (roadmap issue #11).

Importing a module must be a pure, side-effect-free act: no network calls, no
Snowflake connection, no dbt/subprocess shell-out, and no ``dotenv.load_dotenv()``
at import time. Runtime side effects belong in explicit CLI/config functions,
Dagster asset bodies, or setup scripts -- never at module scope.

This script imports each target module in a FRESH interpreter with guards
installed BEFORE the import, so an import-time side effect is caught precisely.
Per module the child reports:

- ``OK``        -- imported with no guarded side effect (exit 0).
- ``VIOLATION`` -- the import tripped a guard (exit 3) -> gate FAILS.
- ``SKIP``      -- a third-party dependency is not installed (exit 2). This is an
                   environment limitation (e.g. a bare sandbox without Dagster or
                   the Snowflake connector), not a regression.
- ``ERROR``     -- the import failed for another reason (exit 1) -> gate FAILS.

The gate exits non-zero if any target VIOLATES inertness or ERRORs; SKIPs are
reported but tolerated so the check is runnable offline.

Usage:
    python scripts/ci/check_import_inertness.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Import names as they resolve on sys.path. ``artwork_orchestration`` is the
# package installed from ``orchestration/`` (not ``orchestration.*``).
TARGETS = (
    "extraction.met.config",
    "extraction.met.run",
    "extraction.aic.config",
    "extraction.aic.run",
    "artwork_orchestration.definitions",
    "artwork_orchestration.definition_factory",
    "artwork_orchestration.resources",
)

# Program run in a fresh interpreter, one target per invocation. Guards are
# installed before the target import so import-time side effects are caught.
_CHILD = r"""
import importlib
import sys


class _InertnessViolation(RuntimeError):
    pass


def _install_guards():
    import socket
    import subprocess

    def _net(*a, **k):
        raise _InertnessViolation("network access at import time")

    socket.socket.connect = _net
    socket.create_connection = _net
    socket.getaddrinfo = _net

    def _popen(self, *a, **k):
        raise _InertnessViolation("subprocess/shell-out (e.g. dbt) at import time")

    subprocess.Popen.__init__ = _popen

    try:
        import dotenv

        def _dot(*a, **k):
            raise _InertnessViolation("dotenv.load_dotenv() at import time")

        dotenv.load_dotenv = _dot
        if hasattr(dotenv, "main"):
            dotenv.main.load_dotenv = _dot
    except ImportError:
        pass

    try:
        import snowflake.connector as _sc

        def _sf(*a, **k):
            raise _InertnessViolation("snowflake.connector.connect() at import time")

        _sc.connect = _sf
    except ImportError:
        pass


def main():
    target = sys.argv[1]
    _install_guards()
    try:
        importlib.import_module(target)
    except _InertnessViolation as exc:
        print("VIOLATION %s: %s" % (target, exc))
        return 3
    except ModuleNotFoundError as exc:
        print("SKIP %s: missing dependency (%s)" % (target, exc))
        return 2
    except Exception as exc:  # noqa: BLE001 -- surface any unexpected import failure
        print("ERROR %s: %r" % (target, exc))
        return 1
    print("OK %s" % target)
    return 0


sys.exit(main())
"""


def _child_env() -> dict:
    """
    Environment for the child: repo root and the orchestration package dir on
    ``PYTHONPATH`` so both ``extraction.*`` and ``artwork_orchestration.*``
    resolve without requiring an editable install.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT), str(REPO_ROOT / "orchestration")]
    )
    # Belt and braces: keep dbt prepare inert even if a target reaches for it.
    env.setdefault("ARTWORK_SKIP_DBT_PREPARE", "1")
    return env


def check(target: str) -> int:
    """
    Import one target in a fresh interpreter; return its child exit code.
    """
    proc = subprocess.run(
        [sys.executable, "-c", _CHILD, target],
        cwd=str(REPO_ROOT),
        env=_child_env(),
        capture_output=True,
        text=True,
    )
    line = (proc.stdout or proc.stderr).strip().splitlines()
    print(line[-1] if line else f"ERROR {target}: no output (rc={proc.returncode})")
    return proc.returncode


def main() -> int:
    """
    Run the inertness gate over every target module.
    """
    violations, errors, skips = [], [], []
    for target in TARGETS:
        rc = check(target)
        if rc == 3:
            violations.append(target)
        elif rc == 1:
            errors.append(target)
        elif rc == 2:
            skips.append(target)
    print(
        "\nimport-inertness: %d ok/skip-clean, %d violation(s), %d error(s), %d skip(s)"
        % (len(TARGETS) - len(violations) - len(errors) - len(skips),
           len(violations), len(errors), len(skips))
    )
    if skips:
        print("skipped (missing deps -- env limitation): " + ", ".join(skips))
    if violations or errors:
        print("FAIL: import-time side effects or import errors detected.")
        return 1
    print("PASS: no import-time side effects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
