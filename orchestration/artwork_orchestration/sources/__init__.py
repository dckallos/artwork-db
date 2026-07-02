"""The source registry: built by SCANNING ``sources/*.yaml`` -- never a hardcoded list.

Adding a source means dropping a new ``<key>.yaml`` in this directory (see
``../SCHEMA.md`` and ``../ADDING_A_SOURCE.md``). Nothing in the orchestration layer's
Python changes: :func:`~artwork_orchestration.loader.load_source_specs` discovers the
file, validates it, and turns it into a :class:`~artwork_orchestration.spec.SourceSpec`.
"""
from __future__ import annotations

from typing import Tuple

from ..loader import load_source_specs
from ..spec import SourceSpec

# The registry IS the directory listing (deterministically sorted by source key).
REGISTRY: Tuple[SourceSpec, ...] = tuple(load_source_specs())

__all__ = ["REGISTRY", "SourceSpec"]
