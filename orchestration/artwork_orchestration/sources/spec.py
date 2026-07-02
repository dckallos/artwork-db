"""Declarative description of a museum source pipeline.

These dataclasses are the ONE abstraction the whole orchestration layer is built
from. A source (museum) is described as *data* -- a list of :class:`ExtractionStep`
that each produce one or more Bronze tables -- and the factories in
``artwork_orchestration.factories`` turn that data into Dagster assets, checks,
jobs, and schedules. Adding a museum means writing one more ``SourceSpec``; no
factory, job, check, or definitions code changes.

Nothing here talks to Snowflake or runs anything; it is pure structure plus a few
key/partition helpers so the factories stay small.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator, Mapping, Optional, Tuple

from dagster import AssetKey, StaticPartitionsDefinition

from ..policies import TIMEOUT_SNAPSHOT
from ..translator import dbt_source_asset_key


@dataclass(frozen=True)
class PartitionDim:
    """A static partition dimension for a step (e.g. Met curatorial departments).

    ``values`` maps a slug-safe partition KEY (Dagster forbids commas/brackets in
    keys) to the exact value the CLI expects behind ``cli_flag``.
    """

    name: str                     # human name, e.g. "department"
    cli_flag: str                 # CLI flag that selects a slice, e.g. "--department"
    values: Mapping[str, str]     # partition-key (slug) -> real CLI value

    def partition_keys(self) -> list[str]:
        return sorted(self.values)

    def partitions_def(self) -> StaticPartitionsDefinition:
        return StaticPartitionsDefinition(self.partition_keys())

    def value_for(self, partition_key: str) -> str:
        try:
            return self.values[partition_key]
        except KeyError as exc:  # pragma: no cover - defensive
            raise KeyError(
                f"Unknown {self.name} partition {partition_key!r}. "
                f"Known: {self.partition_keys()}"
            ) from exc


@dataclass(frozen=True)
class Produces:
    """A Bronze table a step writes (or, for a verify step, reads and reports)."""

    table: str                          # logical name, e.g. "raw_met_objects" / "csv_snapshot"
    dbt_source: bool = False            # True -> keyed via translator (dbt lineage terminal)
    physical: Optional[str] = None      # physical Bronze table; default UPPER(table)
    nonempty: bool = False              # emit a COUNT(*) > 0 asset check on this table
    nonempty_severity: str = "ERROR"
    freshness_days: Optional[float] = None  # emit a last-update freshness check if set

    def physical_table(self) -> str:
        return (self.physical or self.table).upper()

    def asset_key(self, source_key: str) -> AssetKey:
        """dbt-source terminals share the translator's key scheme; internals get
        ``[source, table]``. Either way the key is stable and lineage-safe."""
        if self.dbt_source:
            return dbt_source_asset_key(source_key, self.table)
        return AssetKey([source_key, self.table])


@dataclass(frozen=True)
class ExtractionStep:
    """One phase of a source pipeline -> becomes one Dagster asset (or a multi_asset
    when it produces more than one dbt-source table)."""

    name: str                                   # "snapshot","seed_control","enrich","verify"
    produces: Tuple[Produces, ...]
    subcommand: Optional[str] = None            # CLI subcommand; None => verify-only (no CLI call)
    static_args: Tuple[str, ...] = ()           # extra CLI args appended verbatim
    partition: Optional[PartitionDim] = None    # static-partition this step
    uses_batch_flags: bool = False              # append --batch-size/--max-batches from policies
    rate_limited: bool = False                  # per-worker rps env + rate-limit run tag on jobs
    api_bound: bool = True                      # attach EXTRACTION_RETRY_POLICY
    timeout_s: int = TIMEOUT_SNAPSHOT
    compute_kind: str = "python"
    # Optional richer metadata: label -> scalar SQL template. Placeholders filled by
    # the factory: {db}, {schema}, {partition_value} (single-quote-escaped).
    extra_metadata_sql: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_multi(self) -> bool:
        return len(self.produces) > 1

    def asset_keys(self, source_key: str) -> list[AssetKey]:
        return [p.asset_key(source_key) for p in self.produces]


@dataclass(frozen=True)
class HealthCheck:
    """A custom data-quality check beyond the auto-generated non-empty checks
    (e.g. 'no worklist leases older than the TTL'). Attaches to the asset that
    produces ``attach_table``."""

    name: str
    attach_table: str                     # logical table whose asset this check hangs off
    sql: str                              # scalar query; {db}/{schema} placeholders allowed
    passes: Callable[[int], bool]         # verdict from the scalar value
    severity: str = "WARN"
    description: str = ""


@dataclass(frozen=True)
class SourceSpec:
    """Everything the factories need to build a museum's Dagster objects."""

    key: str                              # "met","aic" -- also the dbt source name
    cli_module: str                       # "extraction.met.run"
    steps: Tuple[ExtractionStep, ...]
    checks: Tuple[HealthCheck, ...] = ()
    rate_limit_value: Optional[str] = None  # tag value; defaults to key when a step is rate_limited
    rps_env_var: str = "MET_API_RPS"        # env var the CLI reads for per-worker rps

    @property
    def group_name(self) -> str:
        return f"extraction_{self.key}"

    @property
    def has_rate_limited_step(self) -> bool:
        return any(s.rate_limited for s in self.steps)

    @property
    def rate_tag_value(self) -> Optional[str]:
        """The value for the ``artwork/rate_limited_api`` tag, or None if this source
        has no rate-limited step."""
        if not self.has_rate_limited_step:
            return None
        return self.rate_limit_value or self.key

    def enrich_step(self) -> Optional[ExtractionStep]:
        """The bounded, partitioned, rate-limited step (if any) that a per-source
        'process next batch' job/schedule should target."""
        for step in self.steps:
            if step.rate_limited and step.partition is not None:
                return step
        return None

    def iter_produces(self) -> Iterator[Tuple[ExtractionStep, Produces]]:
        for step in self.steps:
            for produced in step.produces:
                yield step, produced

    def find_produce(self, table: str) -> Optional[Produces]:
        for _step, produced in self.iter_produces():
            if produced.table == table:
                return produced
        return None
