"""dbt models exposed as Dagster assets.

`@dbt_assets` reads the compiled manifest and turns every model/test into an
asset. Because sources are keyed via ArtworkDbtTranslator to match the
extraction assets, the staging/mart models automatically depend on the Python
ingestion that produces their Bronze sources.
"""
from __future__ import annotations

from dagster import OpExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from .resources import artwork_dbt_project
from .translator import ArtworkDbtTranslator


@dbt_assets(
    manifest=artwork_dbt_project.manifest_path,
    dagster_dbt_translator=ArtworkDbtTranslator(),
)
def artwork_dbt_assets(context: OpExecutionContext, dbt: DbtCliResource):
    """Run `dbt build` (models + tests) for the whole project."""
    yield from dbt.cli(["build"], context=context).stream()
