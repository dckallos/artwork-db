"""Asset factory: turn a :class:`SourceSpec` into Dagster asset definitions.

One :class:`ExtractionStep` becomes one ``@asset`` -- or a ``@multi_asset`` when the
step produces more than one dbt-source table (the multi-table snapshot case). Steps are
chained: each depends on the asset(s) produced by the previous step, reproducing the
``snapshot -> control -> enrich -> verify`` lineage without any per-museum code.
"""
from __future__ import annotations

from typing import List

from dagster import (
    AssetOut,
    AssetsDefinition,
    MaterializeResult,
    asset,
    multi_asset,
)

from .._runner import run_module
from .._snowflake import render, sf_scalars
from ..config import BRONZE
from ..policies import (
    EXTRACTION_RETRY_POLICY,
    BATCH_SIZE,
    MAX_BATCHES,
    RATE_LIMIT_TAG_KEY,
    per_worker_rps,
    timeout_tags,
)
from ..spec import ExtractionStep, SourceSpec


def _op_tags(spec: SourceSpec, step: ExtractionStep) -> dict:
    tags = dict(timeout_tags(step.timeout_s))
    if step.rate_limited and spec.rate_tag_value:
        # Cosmetic/visibility only -- the coordinator gates on the RUN tag (jobs.py).
        tags[RATE_LIMIT_TAG_KEY] = spec.rate_tag_value
    return tags


def _make_compute(spec: SourceSpec, step: ExtractionStep):
    """Build the closure that runs one step's CLI (if any) and reports metadata."""

    def _compute(context):
        partition_value = ""
        if step.partition is not None:
            partition_value = step.partition.value_for(context.partition_key)

        # 1) Run the extraction CLI subcommand (verify-only steps skip this).
        if step.subcommand is not None:
            argv: List[str] = [step.subcommand, *step.static_args]
            if step.partition is not None:
                argv += [step.partition.cli_flag, partition_value]
            if step.uses_batch_flags:
                argv += [
                    "--batch-size", str(BATCH_SIZE),
                    "--max-batches", str(MAX_BATCHES),
                ]
            extra_env = None
            if step.rate_limited:
                # Divide the global rps budget across concurrent workers.
                extra_env = {spec.rps_env_var: f"{per_worker_rps():.3f}"}
            run_module(context, spec.cli_module, argv, extra_env)

        # 2) Collect metadata: auto row-counts for real tables + declared extras.
        queries = {}
        for produced in step.produces:
            if produced.dbt_source or produced.physical is not None:
                queries[f"{produced.table}_rows"] = (
                    f"SELECT COUNT(*) FROM {BRONZE.fqn(produced.physical_table())}"
                )
        for label, template in step.extra_metadata_sql.items():
            queries[label] = render(template, partition_value)
        scalars = sf_scalars(context, queries) if queries else {}

        base = {"phase": step.name}
        if step.partition is not None:
            base[step.partition.name] = partition_value
        if step.uses_batch_flags:
            base["batch_size"] = BATCH_SIZE
            base["max_batches"] = MAX_BATCHES

        # 3) Emit result(s). Multi-table steps yield one result per output.
        if step.is_multi:
            return tuple(
                MaterializeResult(
                    asset_key=produced.asset_key(spec.key),
                    metadata={**base, "rows": scalars.get(f"{produced.table}_rows")},
                )
                for produced in step.produces
            )
        return MaterializeResult(metadata={**base, **scalars})

    _compute.__name__ = f"{spec.key}__{step.name}"
    return _compute


def _build_step_asset(
    spec: SourceSpec, step: ExtractionStep, deps: List
) -> AssetsDefinition:
    compute = _make_compute(spec, step)
    retry = EXTRACTION_RETRY_POLICY if step.api_bound else None
    partitions_def = step.partition.partitions_def() if step.partition else None
    op_tags = _op_tags(spec, step)
    common = dict(
        group_name=spec.group_name,
        compute_kind=step.compute_kind,
        retry_policy=retry,
        op_tags=op_tags,
    )

    if step.is_multi:
        return multi_asset(
            name=f"{spec.key}__{step.name}",
            outs={
                produced.table: AssetOut(key=produced.asset_key(spec.key))
                for produced in step.produces
            },
            deps=deps or None,
            partitions_def=partitions_def,
            **common,
        )(compute)

    (only,) = step.produces
    return asset(
        key=only.asset_key(spec.key),
        deps=deps or None,
        partitions_def=partitions_def,
        **common,
    )(compute)


def build_source_assets(spec: SourceSpec) -> List[AssetsDefinition]:
    """All Dagster assets for one source, chained in declaration order."""
    assets: List[AssetsDefinition] = []
    prev_keys: List = []
    for step in spec.steps:
        assets.append(_build_step_asset(spec, step, deps=prev_keys))
        prev_keys = step.asset_keys(spec.key)
    return assets
