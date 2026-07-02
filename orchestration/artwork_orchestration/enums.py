"""Enumerations for the framework config — the string literals that used to be validated
ad-hoc in :mod:`artwork_orchestration.loader`.

Dependency-free leaf (stdlib only) so ``model.py``, ``spec.py``, ``loader.py``, and
``policies.py`` can all import it without any import cycle. Every member is a ``str``
subclass so YAML values map straight onto members, dict lookups keyed by plain strings
keep working, and ``.value`` round-trips to the original YAML token.
"""
from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    """Asset-check severity for non-empty and custom health checks."""

    ERROR = "ERROR"
    WARN = "WARN"


class BackoffStrategy(str, Enum):
    """Retry backoff shape (maps to ``dagster.Backoff`` in ``policies.py``)."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"


class JitterStrategy(str, Enum):
    """Retry jitter (maps to ``dagster.Jitter`` / ``None`` in ``policies.py``)."""

    PLUS_MINUS = "plus_minus"
    NONE = "none"


class StepKind(str, Enum):
    """Step kind — selects the per-run wall-clock timeout in ``framework.yaml``."""

    SNAPSHOT = "snapshot"
    SEED = "seed"
    BATCH = "batch"


class StepMode(str, Enum):
    """Step execution mode. ``BATCHED`` appends the framework batch flags to the CLI."""

    SIMPLE = "simple"
    BATCHED = "batched"
