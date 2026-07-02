"""The Dagster code location: assembles assets, jobs, schedules, resources.

Entry point referenced by pyproject.toml ([tool.dagster] module_name).
Load in the UI with:  scripts/orchestration/run_dagster_dev.sh
"""
from __future__ import annotations

from dagster import Definitions

from . import assets_extraction
from .assets_dbt import artwork_dbt_assets
from .jobs import (
    dbt_build_job,
    full_pipeline_job,
    ingest_all_job,
    met_ingest_job,
)
from .resources import dbt_resource
from .schedules import daily_dbt_schedule, weekly_full_pipeline_schedule

# Collect the module-level asset defs from assets_extraction.
extraction_assets = [
    assets_extraction.met_csv_snapshot,
    assets_extraction.met_enrichment_control,
    assets_extraction.raw_met_objects,
    assets_extraction.aic_snapshot,
]

defs = Definitions(
    assets=[*extraction_assets, artwork_dbt_assets],
    jobs=[met_ingest_job, ingest_all_job, dbt_build_job, full_pipeline_job],
    schedules=[daily_dbt_schedule, weekly_full_pipeline_schedule],
    resources={"dbt": dbt_resource},
)
