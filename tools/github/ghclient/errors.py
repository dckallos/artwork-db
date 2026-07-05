"""
Typed, actionable errors for the GitHub client.

Mirrors the orchestration loader's discipline: configuration problems are raised as
:class:`ConfigError` scoped to the offending *file* and *field* (e.g.
``config/github-client-config.yml: branch_protection.branches.main.policy: file not
found``) -- never a bare ``KeyError``. Runtime failures talking to ``gh`` raise
:class:`GhError`, which carries the parsed HTTP status when one is known so callers
(notably the H1 fail-closed export path) can distinguish a verified 404 from every
other failure.

Import-safe: this module has no side effects and no third-party imports.
"""
from __future__ import annotations

from typing import Optional


class GhClientError(Exception):
    """
    Base class for every error raised by :mod:`ghclient`.
    """


class ConfigError(GhClientError):
    """
    A configuration problem, scoped to a source file and a dotted field path.

    The string form is always ``"<source>: <field>: <message>"`` (the ``field`` is
    omitted when unknown) so error text is greppable and points a reader straight at
    the line to fix.
    """

    def __init__(self, source: str, field: Optional[str], message: str) -> None:
        """
        Build a file/field-scoped configuration error.
        """
        self.source = source
        self.field = field
        self.message = message
        if field:
            super().__init__(f"{source}: {field}: {message}")
        else:
            super().__init__(f"{source}: {message}")


class GhError(GhClientError):
    """
    A failure invoking or interpreting the ``gh`` CLI.

    ``status_code`` is the HTTP status parsed from ``gh`` output when the failure was
    an API response (e.g. ``404``/``403``/``500``); it is ``None`` for transport-level
    failures (missing binary, timeout, unauthenticated) where no HTTP status exists.
    """

    def __init__(self, message: str, *, status_code: Optional[int] = None) -> None:
        """
        Build a ``gh`` invocation/interpretation error.
        """
        self.status_code = status_code
        super().__init__(message)


class GhApiError(GhError):
    """
    A failed or unusable ``gh api`` response.

    Extends :class:`GhError` with the captured ``stderr`` so callers can surface the
    underlying ``gh`` diagnostic (e.g. in a fail-closed export) without re-invoking the
    process. ``status_code`` carries the verified HTTP status when one was parsed.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        stderr: Optional[str] = None,
    ) -> None:
        """
        Build a ``gh api`` error carrying the parsed status and captured stderr.
        """
        self.stderr = stderr
        super().__init__(message, status_code=status_code)
