"""
URL-path helpers shared by every verb that splices a name into a ``gh api`` path.

A branch or GitHub-environment name may contain ``/`` or other characters that must be
percent-encoded before it is placed into a REST path (e.g.
``repos/{owner}/{repo}/environments/{env}``). Centralizing the encoding here keeps every
caller consistent and makes the "encode path segments" rule (review item A4) testable in
one place. Import-safe: no side effects, no third-party imports.
"""
from __future__ import annotations

from urllib.parse import quote

__all__ = ["quote_segment"]


def quote_segment(segment: str) -> str:
    """
    Percent-encode a single URL path segment, encoding ``/`` and every reserved char.

    ``safe=""`` means nothing is left unescaped, so a branch like ``release/1.0`` or an
    environment name with spaces becomes one safe path segment rather than smuggling in an
    extra path level.
    """
    return quote(segment, safe="")
