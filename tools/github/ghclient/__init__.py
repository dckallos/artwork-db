"""
ghclient -- a YAML-driven, testable GitHub governance client for artwork-db.

The package is import-safe in a bare test process: importing any module here does
NOT touch the network, mutate disk, or read credentials (plan / AGENTS.md
non-negotiables). Behavior is configured in ``config/github-client-config.yml``
and executed through a single injectable subprocess seam (:mod:`ghclient.gh`).
"""
from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
