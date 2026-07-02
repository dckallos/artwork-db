"""Typed in-memory model for the framework (Layer A) configuration.

These dataclasses are the internal representation the engine reads. They are LOADED
from ``framework.yaml`` by :mod:`artwork_orchestration.loader` -- never authored in
Python. Keeping them here (a dependency-free leaf module) lets both ``config.py`` and
``policies.py`` import the typed config without any import cycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Union

from .enums import BackoffStrategy, JitterStrategy, StepKind


@dataclass(frozen=True)
class ConnectionCfg:
    """How the orchestration layer opens ad-hoc Snowflake queries for metadata/checks.

    It reuses the dbt PROFILE as the single connection identity, so there is no second
    place credentials live. ``project_dir`` (where ``dbt_project.yml`` lives) and
    ``profiles_dir`` (where ``profiles.yml`` lives) are both resolved relative to the repo
    root; they are usually the same directory but dbt permits them to differ, so we keep
    them distinct rather than inferring one from the other.

    ``profile`` is OPTIONAL: when omitted it is derived from ``<project_dir>/dbt_project.yml``
    (``profile:``) so the profile name is single-sourced in the dbt project and never
    drifts from a duplicate in ``framework.yaml``.
    """

    target: str
    profiles_dir: str
    project_dir: str
    profile: Optional[str] = None


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
    backoff: BackoffStrategy       # exponential | linear
    jitter: JitterStrategy         # plus_minus | none


@dataclass(frozen=True)
class ProfileConfig:
    """The resolved dbt profile output block (``profiles.yml`` -> profile -> target).

    Replaces the ad-hoc dict previously passed around in ``_connection.py``. Every field
    is optional because a profile only sets the keys it needs (e.g. key-pair auth omits
    ``password``); ``connect()`` builds connector kwargs from the fields that are set.
    """

    account: Optional[str] = None
    user: Optional[str] = None
    role: Optional[str] = None
    warehouse: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    password: Optional[str] = None
    authenticator: Optional[str] = None
    token: Optional[str] = None
    host: Optional[str] = None

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "ProfileConfig":
        """Build from a rendered profile mapping, ignoring keys we do not model."""
        return cls(
            account=m.get("account"),
            user=m.get("user"),
            role=m.get("role"),
            warehouse=m.get("warehouse"),
            database=m.get("database"),
            schema=m.get("schema"),
            private_key_path=m.get("private_key_path"),
            private_key_passphrase=m.get("private_key_passphrase"),
            password=m.get("password"),
            authenticator=m.get("authenticator"),
            token=m.get("token"),
            host=m.get("host"),
        )


@dataclass(frozen=True)
class TimeoutsCfg:
    """Per-run wall-clock ceilings (seconds), keyed by step ``kind`` with a default."""

    default: int
    by_kind: Mapping[str, int] = field(default_factory=dict)

    def for_kind(self, kind: Union[StepKind, str]) -> int:
        """Timeout for a step ``kind``. Accepts a :class:`StepKind` or a raw string;
        both resolve against the ``by_kind`` map (keyed by the YAML kind tokens)."""
        key = kind.value if isinstance(kind, StepKind) else str(kind)
        return int(self.by_kind.get(key, self.default))


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
