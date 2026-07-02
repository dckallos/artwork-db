"""Jobs -- named selections over the asset graph.

Jobs are how you trigger runs (from the UI or a schedule). We define three:
  * met_ingest_job    -- run only the Met extraction chain.
  * dbt_build_job     -- run only the dbt models + tests.
  * full_pipeline_job -- extraction + dbt, end to end.
"""
from __future__ import annotations

from dagster import AssetSelection, define_asset_job

from .assets_dbt import artwork_dbt_assets

# All dbt models/tests in the project.
dbt_selection = AssetSelection.assets(artwork_dbt_assets)

# Everything under the Met extraction group.
met_selection = AssetSelection.groups("extraction_met")

met_ingest_job = define_asset_job(
    name="met_ingest_job",
    selection=met_selection,
    description="Run the Met extraction chain (snapshot -> seed -> enrich).",
)

dbt_build_job = define_asset_job(
    name="dbt_build_job",
    selection=dbt_selection,
    description="Run dbt build (models + tests) for the whole project.",
)

full_pipeline_job = define_asset_job(
    name="full_pipeline_job",
    selection=AssetSelection.all(),
    description="End-to-end: extraction assets then dbt build.",
)
