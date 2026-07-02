"""Typed in-memory model for the framework (Layer A) configuration.

These dataclasses are the internal representation the engine reads. They are LOADED
from ``framework.yaml`` by :mod:`artwork_orchestration.loader` -- never authored in
Python. Keeping them here (a dependency-free leaf module) lets both ``config.py`` and
``policies.py`` import the typed config without any import cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Mapping


@dataclass(frozen=True)
class ConnectionCfg:
    """How the orchestration layer opens ad-hoc Snowflake queries for metadata/checks.

    It reuses the dbt PROFILE as the single connection identity, so there is no second
    place credentials live. ``profiles_dir`` is resolved relative to the repo root.
    """

    profile: str
    target: str
    profiles_dir: str


@dataclass(frozen=True)
class BronzeCfg:
    """Location of the raw (Bronze) landing tables in Snowflake."""

    database: str
    schema: str

    def fqn(self, table: str) -> str:
        """Fully-qualified name for a Bronze table, e.g. ``ARTWORK_DB.BRONZE.RAW_X``."""
        return f"{self.database}.{self.schema}.{table.upper()}"


@dataclass(frozen=True)
class RetryCfg:
    max_retries: int
    delay_seconds: int
    backoff: str            # "exponential" | "linear"
    jitter: str             # "plus_minus" | "none"


@dataclass(frozen=True)
class TimeoutsCfg:
    """Per-run wall-clock ceilings (seconds), keyed by step ``kind`` with a default."""

    default: int
    by_kind: Mapping[str, int] = field(default_factory=dict)

    def for_kind(self, kind: str) -> int:
        return int(self.by_kind.get(kind, self.default))


@dataclass(frozen=True)
class BatchingCfg:
    """Sizing for steps declared ``mode: batched`` (one materialization drains up to
    ``size * max_batches`` rows)."""

    size: int
    max_batches: int


@dataclass(frozen=True)
class RateLimitCfg:
    """Aggregate request budget shared across concurrent rate-limited workers, and the
    max workers run at once (mirror in dagster.yaml tag_concurrency_limits)."""

    rps_budget: float
    concurrency: int

    def per_worker_rps(self) -> float:
        return max(self.rps_budget / max(self.concurrency, 1), 1.0)


@dataclass(frozen=True)
class DefaultsCfg:
    retry: RetryCfg
    timeouts: TimeoutsCfg
    batching: BatchingCfg
    rate_limit: RateLimitCfg


@dataclass(frozen=True)
class TagsCfg:
    """Dagster run/op tag keys the coordinator and daemon gate on."""

    rate_limit_key: str
    max_runtime_key: str


@dataclass(frozen=True)
class FreshnessCfg:
    """dbt Gold marts that get a daily-cadence freshness check (not source-specific)."""

    gold_marts: List[str]
    gold_lag_hours: float


@dataclass(frozen=True)
class FrameworkConfig:
    """The whole Layer-A engine config, parsed + validated from ``framework.yaml``."""

    connection: ConnectionCfg
    bronze: BronzeCfg
    defaults: DefaultsCfg
    tags: TagsCfg
    freshness: FreshnessCfg
