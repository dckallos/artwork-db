"""Job factory (generated from the registry).

Per source:
  * ``{key}_ingest_job``           -- the whole source group (snapshot -> ... -> verify).
  * ``{key}_enrich_next_batch_job``-- ONLY the bounded, partitioned enrichment step
                                      (if the source has one). Run repeatedly / on a
                                      schedule to drain the worklist a slice at a time.

Global:
  * ``ingest_all_job``    -- every source's Bronze ingest, EXCLUDING enrichment + dbt.
  * ``dbt_build_job``     -- dbt models + tests only.
  * ``full_pipeline_job`` -- everything EXCEPT bounded enrichment (snapshots/seeds/verify + dbt).

Enrichment is deliberately kept OUT of the end-to-end / ingest-all jobs. It is the
long, per-museum, rate-limited drain and is driven by its own job/schedule. This also
avoids the single-valued run-tag problem at scale: a run can carry only ONE
``artwork/rate_limited_api`` value, so mixing several museums' enrichment in one run
would break per-museum concurrency capping. Each enrichment job instead carries
exactly one value (its own source key), so the coordinator caps every museum's API
independently.
"""
from __future__ import annotations

from typing import List

from dagster import AssetKey, AssetSelection, define_asset_job

from ..policies import MAX_RUNTIME_TAG_KEY, RATE_LIMIT_TAG_KEY, TIMEOUT_SNAPSHOT
from ..sources.spec import SourceSpec


def _source_runtime(spec: SourceSpec) -> int:
    """Generous per-source ceiling: sum of step timeouts + 1h slack."""
    return sum(step.timeout_s for step in spec.steps) + 60 * 60


def _enrich_keys(registry) -> List[AssetKey]:
    keys: List[AssetKey] = []
    for spec in registry:
        step = spec.enrich_step()
        if step is not None:
            keys += step.asset_keys(spec.key)
    return keys


def build_jobs(registry) -> List:
    # Lazy import: keeps the module importable without the dbt manifest present.
    from ..assets_dbt import artwork_dbt_assets

    jobs: List = []

    for spec in registry:
        ingest_tags = {MAX_RUNTIME_TAG_KEY: _source_runtime(spec)}
        if spec.rate_tag_value:
            ingest_tags[RATE_LIMIT_TAG_KEY] = spec.rate_tag_value
        jobs.append(
            define_asset_job(
                name=f"{spec.key}_ingest_job",
                selection=AssetSelection.groups(spec.group_name),
                tags=ingest_tags,
                description=f"Full {spec.key} extraction chain (snapshot -> ... -> verify).",
            )
        )

        enrich = spec.enrich_step()
        if enrich is not None:
            keys = enrich.asset_keys(spec.key)
            enrich_tags = {MAX_RUNTIME_TAG_KEY: enrich.timeout_s}
            if spec.rate_tag_value:
                enrich_tags[RATE_LIMIT_TAG_KEY] = spec.rate_tag_value
            jobs.append(
                define_asset_job(
                    name=f"{spec.key}_enrich_next_batch_job",
                    selection=AssetSelection.assets(*keys),
                    tags=enrich_tags,
                    description=(
                        f"Process the NEXT bounded {spec.key} enrichment batch (one "
                        "partition). Idempotent + resumable; run repeatedly / on a schedule."
                    ),
                )
            )

    all_groups = [spec.group_name for spec in registry]
    enrich_keys = _enrich_keys(registry)

    non_enrich = AssetSelection.groups(*all_groups)
    if enrich_keys:
        non_enrich = non_enrich - AssetSelection.assets(*enrich_keys)
    jobs.append(
        define_asset_job(
            name="ingest_all_job",
            selection=non_enrich,
            tags={MAX_RUNTIME_TAG_KEY: TIMEOUT_SNAPSHOT * 2},
            description="Collect + ingest ALL sources into Bronze (no enrichment, no dbt).",
        )
    )
    jobs.append(
        define_asset_job(
            name="dbt_build_job",
            selection=AssetSelection.assets(artwork_dbt_assets),
            tags={MAX_RUNTIME_TAG_KEY: 60 * 60},
            description="Run dbt build (models + tests) for the whole project.",
        )
    )

    full = AssetSelection.all()
    if enrich_keys:
        full = full - AssetSelection.assets(*enrich_keys)
    jobs.append(
        define_asset_job(
            name="full_pipeline_job",
            selection=full,
            tags={MAX_RUNTIME_TAG_KEY: sum(_source_runtime(s) for s in registry)},
            description="End-to-end: snapshots + seeds + verify + dbt (excludes bounded enrichment).",
        )
    )
    return jobs
