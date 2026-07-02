"""The source registry: the single list the factories iterate over.

Register a new museum by importing its ``SourceSpec`` and adding it to ``REGISTRY``.
Nothing else in the orchestration layer needs to change.
"""
from __future__ import annotations

from typing import Tuple

from .aic import AIC_SPEC
from .met import MET_SPEC
from .spec import SourceSpec

REGISTRY: Tuple[SourceSpec, ...] = (MET_SPEC, AIC_SPEC)


def source_keys() -> list[str]:
    return [spec.key for spec in REGISTRY]


__all__ = ["REGISTRY", "SourceSpec", "MET_SPEC", "AIC_SPEC", "source_keys"]
